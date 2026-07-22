"""Decrypt and tally pilot ballots locally without persisting the private key or results."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.padding import MGF1, OAEP
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)
from sqlalchemy import func, select

from app.db.session import dispose_engine, get_session_factory
from app.models import Election, EncryptedBallot, MemberElectionStatus, Slate
from app.services.tally_artifact import artifact_sha256, sign_artifact


class TallyError(RuntimeError):
    pass


def _decode_base64url(value: Any, field_name: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise TallyError(f"Missing encrypted payload field: {field_name}")
    try:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)
    except ValueError as exc:
        raise TallyError(f"Invalid base64url field: {field_name}") from exc


def _load_private_key(path: Path) -> RSAPrivateKey:
    password_value = os.environ.get("EVOTING_PRIVATE_KEY_PASSWORD")
    password = password_value.encode("utf-8") if password_value else None
    try:
        key = load_pem_private_key(path.read_bytes(), password=password)
    except (OSError, ValueError, TypeError) as exc:
        raise TallyError(f"Unable to load private key: {path}") from exc
    if not isinstance(key, RSAPrivateKey):
        raise TallyError("The private key must be RSA")
    return key


def _decrypt_ballot(
    ballot: EncryptedBallot, private_key: RSAPrivateKey
) -> tuple[str, str | None]:
    try:
        payload = json.loads(ballot.encrypted_payload)
    except json.JSONDecodeError as exc:
        raise TallyError(f"Ballot {ballot.id} has invalid JSON") from exc
    if not isinstance(payload, dict) or payload.get("algorithm") != "RSA-OAEP-256/AES-256-GCM":
        raise TallyError(f"Ballot {ballot.id} uses an unsupported encryption format")
    if ballot.key_version != "v1" or payload.get("key_version") != "v1":
        raise TallyError(f"Ballot {ballot.id} uses an unsupported key version")
    expected_receipt = hashlib.sha256(ballot.encrypted_payload.encode("utf-8")).hexdigest()
    if expected_receipt != ballot.receipt_hash.lower():
        raise TallyError(f"Ballot {ballot.id} receipt hash does not match its payload")

    wrapped_key = _decode_base64url(payload.get("wrapped_key"), "wrapped_key")
    iv = _decode_base64url(payload.get("iv"), "iv")
    ciphertext = _decode_base64url(payload.get("ciphertext"), "ciphertext")
    try:
        aes_key = private_key.decrypt(
            wrapped_key,
            OAEP(mgf=MGF1(algorithm=SHA256()), algorithm=SHA256(), label=None),
        )
        plaintext = AESGCM(aes_key).decrypt(iv, ciphertext, None)
        decoded = json.loads(plaintext.decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise TallyError(f"Ballot {ballot.id} could not be decrypted") from exc
    if not isinstance(decoded, dict):
        raise TallyError(f"Ballot {ballot.id} has no valid slate selection")
    slate_id = decoded.get("slate_id")
    if not isinstance(slate_id, str):
        raise TallyError(f"Ballot {ballot.id} has no valid slate selection")
    nonce = decoded.get("nonce")
    return slate_id, nonce if isinstance(nonce, str) else None


def _assert_encryption_key_matches(election: Election, private_key: RSAPrivateKey) -> None:
    if not election.public_key:
        raise TallyError("Election has no stored public key")
    stored_public_key = load_pem_public_key(election.public_key.encode("utf-8"))
    derived_public_key = private_key.public_key()
    stored_der = stored_public_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    derived_der = derived_public_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    if stored_der != derived_der:
        raise TallyError("Encryption private key does not match the election public key")


def _signing_key_hash(election: Election, signing_key: RSAPrivateKey) -> str:
    pem = election.signing_public_key or election.public_key
    if not pem:
        raise TallyError("Election has no signing/public key")
    stored = load_pem_public_key(pem.encode("utf-8"))
    derived = signing_key.public_key()
    stored_der = stored.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    derived_der = derived.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    if stored_der != derived_der:
        raise TallyError("Signing private key does not match the election signing public key")
    return hashlib.sha256(pem.encode("utf-8")).hexdigest()


async def tally_encrypted_ballots(
    election_id: UUID,
    private_key_path: Path,
    signing_key_path: Path | None = None,
) -> dict[str, Any]:
    from app.core.config import settings
    from app.services.ballot_crypto import BallotCryptoError, verify_proof_after_decrypt

    factory = get_session_factory()
    async with factory() as session:
        election = await session.scalar(select(Election).where(Election.id == election_id))
        if election is None:
            raise TallyError("Election not found")
        if election.status not in {"CLOSED", "TALLIED"}:
            raise TallyError("Election must be CLOSED before local tally")

        private_key = _load_private_key(private_key_path)
        _assert_encryption_key_matches(election, private_key)
        signing_key = (
            _load_private_key(signing_key_path) if signing_key_path else private_key
        )
        public_key_sha256 = _signing_key_hash(election, signing_key)
        slates = list(
            (
                await session.scalars(
                    select(Slate)
                    .where(Slate.election_id == election.id)
                    .order_by(Slate.created_at.asc())
                )
            ).all()
        )
        slate_names = {str(slate.id): slate.name for slate in slates}
        counts = {slate_id: 0 for slate_id in slate_names}
        ballots = list(
            (
                await session.scalars(
                    select(EncryptedBallot)
                    .where(EncryptedBallot.election_id == election.id)
                    .order_by(EncryptedBallot.created_at.asc())
                )
            ).all()
        )
        for ballot in ballots:
            slate_id, nonce = _decrypt_ballot(ballot, private_key)
            if slate_id not in counts:
                raise TallyError(f"Ballot {ballot.id} references an unknown slate")
            if ballot.zkp_proof:
                try:
                    verify_proof_after_decrypt(
                        zkp_proof=ballot.zkp_proof,
                        slate_id=slate_id,
                        nonce=nonce or "",
                        encrypted_payload=ballot.encrypted_payload,
                        require_integrity_proof=settings.zkp_verification_enabled,
                    )
                except BallotCryptoError as exc:
                    raise TallyError(f"Ballot {ballot.id} ZKP failed: {exc}") from exc
            counts[slate_id] += 1

        eligible_member_count, voted_member_count = (
            int(value)
            for value in (
                await session.execute(
                    select(
                        func.count(MemberElectionStatus.id),
                        func.count(MemberElectionStatus.id).filter(
                            MemberElectionStatus.has_voted.is_(True)
                        ),
                    ).where(
                        MemberElectionStatus.election_id == election.id,
                        MemberElectionStatus.organization_id == election.organization_id,
                        MemberElectionStatus.eligible.is_(True),
                    )
                )
            ).one()
        )
        quorum_required = int(
            (
                Decimal(eligible_member_count) * election.quorum_threshold_pct / Decimal("100")
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        artifact = {
            "artifact_version": "pilot-tally-v1",
            "election_id": str(election.id),
            "public_key_sha256": public_key_sha256,
            "generated_at": datetime.now(UTC).isoformat(),
            "eligible_member_count": eligible_member_count,
            "voted_member_count": voted_member_count,
            "quorum_threshold_pct": str(election.quorum_threshold_pct),
            "quorum_required": quorum_required,
            "quorum_met": voted_member_count >= quorum_required,
            "ballot_count": len(ballots),
            "receipt_hashes": sorted(ballot.receipt_hash.lower() for ballot in ballots),
            "counts": [
                {
                    "slate_id": slate_id,
                    "slate_name": slate_names[slate_id],
                    "votes": count,
                }
                for slate_id, count in counts.items()
            ],
        }
        signature = sign_artifact(artifact, signing_key)
        return {
            "artifact": artifact,
            "signature": signature,
            "artifact_sha256": artifact_sha256(artifact),
            "persisted": False,
            "note": (
                "Tally was computed locally; no private key or result was written "
                "to the database."
            ),
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--election-id", required=True, type=UUID)
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument(
        "--signing-key",
        type=Path,
        default=None,
        help="Optional distinct RSA private key used to sign the tally artifact",
    )
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    try:
        result = await tally_encrypted_ballots(
            args.election_id, args.private_key, args.signing_key
        )
    except TallyError as exc:
        print(f"Tally failed: {exc}")
        return 1
    finally:
        await dispose_engine()
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
