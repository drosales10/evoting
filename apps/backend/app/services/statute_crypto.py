"""Statute ballot envelope checks and statute-integrity-v1 proofs.

The plaintext is a single ballot covering every frozen article. The server does
not read it at cast time. After the offline tally decrypts it, each decision is
published with the member stored on the ballot row.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.asymmetric.padding import MGF1, OAEP
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256

from app.services.ballot_crypto import (
    REQUIRED_PAYLOAD_FIELDS,
    SUPPORTED_ALGORITHM,
    is_development_stub_proof,
    parse_encrypted_payload,
)

COMMENT_MAX_LENGTH = 2000
PROOF_VERSION = "statute-integrity-v1"


class StatuteCryptoError(ValueError):
    pass


def article_set_hash(article_ids: list[str]) -> str:
    canonical = ",".join(sorted(article_id.lower() for article_id in article_ids))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _b64url_decode(value: Any, field_name: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise StatuteCryptoError(f"Falta el campo cifrado {field_name}")
    try:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)
    except ValueError as exc:
        raise StatuteCryptoError(f"Base64url inválido en {field_name}") from exc


def canonical_statute_plaintext(decisions: list[dict[str, Any]], nonce: str) -> str:
    """Canonical JSON shared with the browser sealer. Keys are sorted."""
    rows: list[dict[str, Any]] = []
    for item in decisions:
        row: dict[str, Any] = {
            "approved": bool(item["approved"]),
            "article_id": str(item["article_id"]).lower(),
        }
        comment = item.get("comment")
        if comment:
            row["comment"] = comment
        rows.append(row)
    rows.sort(key=lambda row: row["article_id"])
    body = {"decisions": rows, "nonce": nonce}
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_decisions(
    decisions: Any,
    expected_article_ids: list[str] | set[str],
) -> list[dict[str, Any]]:
    """Require exactly one decision per frozen article. Comment only on rejection."""
    if not isinstance(decisions, list):
        raise StatuteCryptoError("La boleta no trae la lista de decisiones")
    expected = {article_id.lower() for article_id in expected_article_ids}
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for item in decisions:
        if not isinstance(item, dict):
            raise StatuteCryptoError("Cada decisión debe ser un objeto")
        article_id = item.get("article_id")
        approved = item.get("approved")
        if not isinstance(article_id, str) or not article_id:
            raise StatuteCryptoError("Cada decisión necesita article_id")
        if not isinstance(approved, bool):
            raise StatuteCryptoError("Cada decisión necesita approved booleano")
        article_key = article_id.lower()
        if article_key in seen:
            raise StatuteCryptoError("La boleta repite un artículo")
        seen.add(article_key)
        raw_comment = item.get("comment")
        if approved:
            if isinstance(raw_comment, str) and raw_comment.strip():
                raise StatuteCryptoError(
                    "Un artículo aprobado no lleva comentario"
                )
            comment: str | None = None
        else:
            if not isinstance(raw_comment, str) or not raw_comment.strip():
                raise StatuteCryptoError(
                    "Rechazar un artículo exige un comentario"
                )
            comment = raw_comment.strip()
            if len(comment) > COMMENT_MAX_LENGTH:
                raise StatuteCryptoError(
                    f"El comentario supera {COMMENT_MAX_LENGTH} caracteres"
                )
        normalized.append(
            {
                "article_id": article_key,
                "approved": approved,
                "comment": comment,
            }
        )
    if seen != expected:
        raise StatuteCryptoError(
            "La boleta debe incluir cada artículo congelado exactamente una vez"
        )
    normalized.sort(key=lambda row: row["article_id"])
    return normalized


def parse_statute_proof(zkp_proof: str) -> dict[str, Any]:
    try:
        padding = "=" * (-len(zkp_proof) % 4)
        raw = base64.urlsafe_b64decode(zkp_proof + padding)
        proof = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise StatuteCryptoError("La prueba de integridad no es válida") from exc
    if not isinstance(proof, dict) or proof.get("version") != PROOF_VERSION:
        raise StatuteCryptoError("Versión de prueba no soportada")
    for field in ("commitment", "payload_binding", "article_set_hash"):
        value = proof.get(field)
        if not isinstance(value, str) or len(value) != 64:
            raise StatuteCryptoError(f"La prueba no trae el campo {field}")
    return proof


def encode_statute_proof(
    *,
    commitment: str,
    payload_binding: str,
    article_set_hash_value: str,
) -> str:
    raw = json.dumps(
        {
            "version": PROOF_VERSION,
            "commitment": commitment,
            "payload_binding": payload_binding,
            "article_set_hash": article_set_hash_value,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def verify_statute_proof_at_cast(
    *,
    encrypted_payload: str,
    zkp_proof: str,
    article_set_hash_value: str,
    require_integrity_proof: bool,
    allow_dev_stub: bool,
) -> None:
    if is_development_stub_proof(zkp_proof):
        if not allow_dev_stub:
            raise StatuteCryptoError("Las pruebas de desarrollo no se aceptan")
        return
    if not require_integrity_proof:
        if len(zkp_proof) < 16:
            raise StatuteCryptoError("La prueba de integridad es demasiado corta")
        return
    proof = parse_statute_proof(zkp_proof)
    if proof["article_set_hash"].lower() != article_set_hash_value.lower():
        raise StatuteCryptoError("La prueba no corresponde al estatuto congelado")
    expected_binding = hashlib.sha256(
        f"{encrypted_payload}:{proof['commitment']}".encode()
    ).hexdigest()
    if expected_binding != proof["payload_binding"].lower():
        raise StatuteCryptoError("La prueba no ata el sobre cifrado")


def verify_statute_proof_after_decrypt(
    *,
    zkp_proof: str | None,
    plaintext: str,
    encrypted_payload: str,
    article_set_hash_value: str,
    require_integrity_proof: bool,
) -> None:
    if not require_integrity_proof:
        return
    if not zkp_proof or is_development_stub_proof(zkp_proof):
        raise StatuteCryptoError("La prueba de desarrollo no pasa el escrutinio auditado")
    proof = parse_statute_proof(zkp_proof)
    expected_commitment = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    if expected_commitment != proof["commitment"].lower():
        raise StatuteCryptoError("El compromiso no coincide con el texto descifrado")
    if proof["article_set_hash"].lower() != article_set_hash_value.lower():
        raise StatuteCryptoError("La prueba no corresponde al estatuto congelado")
    expected_binding = hashlib.sha256(
        f"{encrypted_payload}:{proof['commitment']}".encode()
    ).hexdigest()
    if expected_binding != proof["payload_binding"].lower():
        raise StatuteCryptoError("La prueba no ata el sobre cifrado")


def decrypt_statute_plaintext(
    *,
    encrypted_payload: str,
    receipt_hash: str,
    key_version: str | None,
    private_key: RSAPrivateKey,
) -> str:
    """Return the UTF-8 plaintext. Raises StatuteCryptoError if the envelope fails."""
    try:
        payload = parse_encrypted_payload(encrypted_payload)
    except ValueError as exc:
        raise StatuteCryptoError(str(exc)) from exc
    for field in REQUIRED_PAYLOAD_FIELDS:
        if field not in payload:
            raise StatuteCryptoError(f"Falta el campo {field}")
    if payload.get("algorithm") != SUPPORTED_ALGORITHM:
        raise StatuteCryptoError("Algoritmo de cifrado no soportado")
    if key_version != "v1" or payload.get("key_version") != "v1":
        raise StatuteCryptoError("Versión de clave no soportada")
    expected_receipt = hashlib.sha256(encrypted_payload.encode("utf-8")).hexdigest()
    if expected_receipt != receipt_hash.lower():
        raise StatuteCryptoError("El recibo no coincide con el sobre")
    wrapped_key = _b64url_decode(payload.get("wrapped_key"), "wrapped_key")
    iv = _b64url_decode(payload.get("iv"), "iv")
    ciphertext = _b64url_decode(payload.get("ciphertext"), "ciphertext")
    try:
        aes_key = private_key.decrypt(
            wrapped_key,
            OAEP(mgf=MGF1(algorithm=SHA256()), algorithm=SHA256(), label=None),
        )
        plaintext = AESGCM(aes_key).decrypt(iv, ciphertext, None)
        return plaintext.decode("utf-8")
    except (ValueError, TypeError, UnicodeDecodeError, InvalidTag) as exc:
        raise StatuteCryptoError("No se pudo descifrar la boleta") from exc


def parse_statute_plaintext(
    plaintext: str,
    expected_article_ids: list[str] | set[str],
) -> tuple[list[dict[str, Any]], str]:
    try:
        body = json.loads(plaintext)
    except json.JSONDecodeError as exc:
        raise StatuteCryptoError("El texto descifrado no es JSON") from exc
    if not isinstance(body, dict):
        raise StatuteCryptoError("El texto descifrado no es un objeto")
    nonce = body.get("nonce")
    if not isinstance(nonce, str) or len(nonce) < 16:
        raise StatuteCryptoError("La boleta no trae un nonce válido")
    decisions = validate_decisions(body.get("decisions"), expected_article_ids)
    return decisions, nonce
