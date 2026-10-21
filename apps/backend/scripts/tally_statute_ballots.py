"""Decrypt statute ballots locally and sign a statute-tally-v1 artifact.

The private key is not stored. Each response in the artifact keeps the member
name because the ballot row is nominal. Run after the consultation is CLOSED:

    python -m scripts.tally_statute_ballots --consultation-id UUID --private-key encryption.pem
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)
from sqlalchemy import func, select

from app.db.session import dispose_engine, get_session_factory
from app.models import Member, StatuteArticle, StatuteBallot, StatuteChapter, StatuteConsultation
from app.models import StatuteMemberStatus, StatuteTitle
from app.services.statute_crypto import (
    StatuteCryptoError,
    decrypt_statute_plaintext,
    parse_statute_plaintext,
    verify_statute_proof_after_decrypt,
)
from app.services.statute_tally import (
    DecodedStatuteBallot,
    StatuteArticleView,
    build_statute_tally_artifact,
    required_quorum_votes,
)
from app.services.tally_artifact import artifact_sha256, sign_artifact


class TallyError(RuntimeError):
    pass


def _load_private_key(path: Path) -> RSAPrivateKey:
    password_value = os.environ.get("EVOTING_PRIVATE_KEY_PASSWORD")
    password = password_value.encode("utf-8") if password_value else None
    try:
        key = load_pem_private_key(path.read_bytes(), password=password)
    except (OSError, ValueError, TypeError) as exc:
        raise TallyError(f"No se pudo leer la clave privada: {path}") from exc
    if not isinstance(key, RSAPrivateKey):
        raise TallyError("La clave privada debe ser RSA")
    return key


def _assert_key_matches(pem: str | None, private_key: RSAPrivateKey, label: str) -> str:
    if not pem:
        raise TallyError(f"La consulta no tiene {label}")
    stored = load_pem_public_key(pem.encode("utf-8"))
    derived = private_key.public_key()
    stored_der = stored.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    derived_der = derived.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    if stored_der != derived_der:
        raise TallyError(f"La clave privada no corresponde a {label}")
    return hashlib.sha256(pem.encode("utf-8")).hexdigest()


async def tally_statute_ballots(
    consultation_id: UUID,
    private_key_path: Path,
    signing_key_path: Path | None = None,
) -> dict[str, Any]:
    from app.core.config import settings

    factory = get_session_factory()
    async with factory() as session:
        consultation = await session.scalar(
            select(StatuteConsultation).where(StatuteConsultation.id == consultation_id)
        )
        if consultation is None:
            raise TallyError("Consulta no encontrada")
        if consultation.status not in {"CLOSED", "TALLIED"}:
            raise TallyError("La consulta debe estar CLOSED antes del escrutinio local")
        if not consultation.article_set_hash:
            raise TallyError("El estatuto no tiene huella de artículos")

        private_key = _load_private_key(private_key_path)
        _assert_key_matches(consultation.public_key, private_key, "la clave de cifrado")
        signing_key = _load_private_key(signing_key_path) if signing_key_path else private_key
        signing_pem = consultation.signing_public_key or consultation.public_key
        public_key_sha256 = _assert_key_matches(signing_pem, signing_key, "la clave de firma")

        rows = (
            await session.execute(
                select(StatuteArticle, StatuteChapter, StatuteTitle)
                .join(StatuteChapter, StatuteChapter.id == StatuteArticle.chapter_id)
                .join(StatuteTitle, StatuteTitle.id == StatuteChapter.title_id)
                .where(StatuteArticle.consultation_id == consultation.id)
                .order_by(
                    StatuteTitle.number.asc(),
                    StatuteChapter.number.asc(),
                    StatuteArticle.number.asc(),
                )
            )
        ).all()
        articles = [
            StatuteArticleView(
                article_id=str(article.id),
                number=article.number,
                content=article.content,
                title_number=title.number,
                title_description=title.description,
                chapter_number=chapter.number,
                chapter_description=chapter.description,
            )
            for article, chapter, title in rows
        ]
        expected_ids = [article.article_id for article in articles]
        ballots = list(
            (
                await session.scalars(
                    select(StatuteBallot)
                    .where(StatuteBallot.consultation_id == consultation.id)
                    .order_by(StatuteBallot.created_at.asc())
                )
            ).all()
        )
        member_ids = [ballot.member_id for ballot in ballots]
        members = {
            member.id: member
            for member in (
                await session.scalars(select(Member).where(Member.id.in_(member_ids)))
            ).all()
        } if member_ids else {}

        decoded: list[DecodedStatuteBallot] = []
        for ballot in ballots:
            try:
                plaintext = decrypt_statute_plaintext(
                    encrypted_payload=ballot.encrypted_payload,
                    receipt_hash=ballot.receipt_hash,
                    key_version=ballot.key_version,
                    private_key=private_key,
                )
                verify_statute_proof_after_decrypt(
                    zkp_proof=ballot.zkp_proof,
                    plaintext=plaintext,
                    encrypted_payload=ballot.encrypted_payload,
                    article_set_hash_value=consultation.article_set_hash,
                    require_integrity_proof=settings.zkp_verification_enabled,
                )
                decisions, _nonce = parse_statute_plaintext(plaintext, expected_ids)
            except StatuteCryptoError as exc:
                raise TallyError(f"Boleta {ballot.id}: {exc}") from exc
            member = members.get(ballot.member_id)
            if member is None:
                raise TallyError(f"La boleta {ballot.id} no tiene miembro")
            decoded.append(
                DecodedStatuteBallot(
                    member_id=str(member.id),
                    full_name=member.full_name,
                    registry_code=member.registry_code,
                    receipt_hash=ballot.receipt_hash,
                    decisions=decisions,
                )
            )

        eligible_member_count, voted_member_count = (
            int(value)
            for value in (
                await session.execute(
                    select(
                        func.count(StatuteMemberStatus.id),
                        func.count(StatuteMemberStatus.id).filter(
                            StatuteMemberStatus.has_voted.is_(True)
                        ),
                    ).where(
                        StatuteMemberStatus.consultation_id == consultation.id,
                        StatuteMemberStatus.organization_id == consultation.organization_id,
                        StatuteMemberStatus.eligible.is_(True),
                    )
                )
            ).one()
        )
        quorum_required = required_quorum_votes(
            eligible_member_count, consultation.quorum_threshold_pct
        )
        artifact = build_statute_tally_artifact(
            consultation_id=str(consultation.id),
            public_key_sha256=public_key_sha256,
            generated_at=datetime.now(UTC),
            eligible_member_count=eligible_member_count,
            voted_member_count=voted_member_count,
            quorum_threshold_pct=consultation.quorum_threshold_pct,
            approval_threshold_pct=consultation.approval_threshold_pct,
            quorum_required=quorum_required,
            articles=articles,
            ballots=decoded,
        )
        signature = sign_artifact(artifact, signing_key)
        return {
            "artifact": artifact,
            "signature": signature,
            "artifact_sha256": artifact_sha256(artifact),
            "persisted": False,
            "note": (
                "Escrutinio calculado en local. La clave privada y el acta "
                "no se escribieron en la base."
            ),
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consultation-id", required=True, type=UUID)
    parser.add_argument("--private-key", required=True, type=Path)
    parser.add_argument("--signing-key", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args()


async def _run() -> int:
    args = _parse_args()
    try:
        result = await tally_statute_ballots(
            args.consultation_id, args.private_key, args.signing_key
        )
    except TallyError as exc:
        print(f"Escrutinio fallido: {exc}")
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
