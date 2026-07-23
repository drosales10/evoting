"""Ballot ciphertext structure checks and ballot-integrity-v1 proofs."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any


class BallotCryptoError(ValueError):
    pass


REQUIRED_PAYLOAD_FIELDS = ("algorithm", "wrapped_key", "iv", "ciphertext", "key_version")
SUPPORTED_ALGORITHM = "RSA-OAEP-256/AES-256-GCM"
PROOF_VERSION = "ballot-integrity-v1"


def _b64url_ok(value: Any) -> bool:
    if not isinstance(value, str) or len(value) < 8:
        return False
    try:
        padding = "=" * (-len(value) % 4)
        base64.urlsafe_b64decode(value + padding)
    except ValueError:
        return False
    return True


def parse_encrypted_payload(encrypted_payload: str) -> dict[str, Any]:
    try:
        payload = json.loads(encrypted_payload)
    except json.JSONDecodeError as exc:
        raise BallotCryptoError("encrypted_payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise BallotCryptoError("encrypted_payload must be a JSON object")
    for field in REQUIRED_PAYLOAD_FIELDS:
        if field not in payload:
            raise BallotCryptoError(f"encrypted_payload missing field: {field}")
    if payload.get("algorithm") != SUPPORTED_ALGORITHM:
        raise BallotCryptoError("unsupported encryption algorithm")
    if not all(_b64url_ok(payload[field]) for field in ("wrapped_key", "iv", "ciphertext")):
        raise BallotCryptoError("encrypted_payload contains invalid base64url fields")
    return payload


def is_development_stub_proof(zkp_proof: str) -> bool:
    return zkp_proof.startswith("development-pilot-proof-")


def parse_integrity_proof(zkp_proof: str) -> dict[str, Any]:
    try:
        padding = "=" * (-len(zkp_proof) % 4)
        raw = base64.urlsafe_b64decode(zkp_proof + padding)
        proof = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BallotCryptoError("zkp_proof is not a valid ballot-integrity-v1 token") from exc
    if not isinstance(proof, dict) or proof.get("version") != PROOF_VERSION:
        raise BallotCryptoError("unsupported zkp_proof version")
    for field in ("commitment", "payload_binding", "slate_set_hash"):
        if not isinstance(proof.get(field), str) or len(proof[field]) != 64:
            raise BallotCryptoError(f"zkp_proof missing hex field: {field}")
    return proof


def verify_proof_at_cast(
    *,
    encrypted_payload: str,
    zkp_proof: str,
    slate_set_hash: str,
    require_integrity_proof: bool,
    allow_dev_stub: bool,
) -> None:
    if is_development_stub_proof(zkp_proof):
        if not allow_dev_stub:
            raise BallotCryptoError("development stub proofs are not accepted")
        return
    if not require_integrity_proof:
        # Structural minimum: reject empty-looking proofs outside stub path.
        if len(zkp_proof) < 16:
            raise BallotCryptoError("zkp_proof too short")
        return
    proof = parse_integrity_proof(zkp_proof)
    if proof["slate_set_hash"].lower() != slate_set_hash.lower():
        raise BallotCryptoError("zkp_proof slate_set_hash does not match election")
    expected_binding = hashlib.sha256(
        f"{encrypted_payload}:{proof['commitment']}".encode()
    ).hexdigest()
    if expected_binding != proof["payload_binding"].lower():
        raise BallotCryptoError("zkp_proof payload_binding mismatch")


def verify_proof_after_decrypt(
    *,
    zkp_proof: str,
    slate_id: str,
    nonce: str,
    encrypted_payload: str,
    require_integrity_proof: bool,
) -> None:
    if not require_integrity_proof:
        return
    if is_development_stub_proof(zkp_proof):
        raise BallotCryptoError("development stub proof cannot pass audited verification")
    proof = parse_integrity_proof(zkp_proof)
    expected_commitment = hashlib.sha256(f"{slate_id}:{nonce}".encode()).hexdigest()
    if expected_commitment != proof["commitment"].lower():
        raise BallotCryptoError("zkp_proof commitment does not match decrypted selection")
    expected_binding = hashlib.sha256(
        f"{encrypted_payload}:{proof['commitment']}".encode()
    ).hexdigest()
    if expected_binding != proof["payload_binding"].lower():
        raise BallotCryptoError("zkp_proof payload_binding mismatch after decrypt")


def slate_set_hash(slate_ids: list[str]) -> str:
    canonical = ",".join(sorted(sid.lower() for sid in slate_ids))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def encode_integrity_proof(
    *,
    commitment: str,
    payload_binding: str,
    slate_set_hash_value: str,
) -> str:
    raw = json.dumps(
        {
            "version": PROOF_VERSION,
            "commitment": commitment,
            "payload_binding": payload_binding,
            "slate_set_hash": slate_set_hash_value,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
