"""Statute consultation protocol: sealed nominal ballots, without touching slate tallies."""

from __future__ import annotations

import base64
import hashlib
import json
from decimal import Decimal
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.padding import MGF1, OAEP
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from fastapi.testclient import TestClient

from app.main import app
from app.models import EncryptedBallot, StatuteBallot
from app.services.statute_crypto import (
    StatuteCryptoError,
    article_set_hash,
    canonical_statute_plaintext,
    decrypt_statute_plaintext,
    encode_statute_proof,
    parse_statute_plaintext,
    validate_decisions,
    verify_statute_proof_after_decrypt,
    verify_statute_proof_at_cast,
)
from app.services.statute_flow import StatuteFlowError, require_can_cast, require_editable
from app.services.statute_tally import (
    DecodedStatuteBallot,
    StatuteArticleView,
    build_statute_tally_artifact,
)

client = TestClient(app)

ARTICLE_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ARTICLE_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
NONCE = "ab" * 16


def test_structure_locks_after_freeze() -> None:
    require_editable("DRAFT")
    require_editable("REGISTRATION")
    for status in ("FREEZE", "ACTIVE", "CLOSED", "TALLIED"):
        with pytest.raises(StatuteFlowError):
            require_editable(status)


def test_second_cast_is_rejected() -> None:
    require_can_cast(eligible=True, has_voted=False, reason=None)
    with pytest.raises(StatuteFlowError) as caught:
        require_can_cast(eligible=True, has_voted=True, reason=None)
    assert caught.value.status_code == 409


def test_ballot_requires_every_article_and_comment_only_on_rejection() -> None:
    with pytest.raises(StatuteCryptoError):
        validate_decisions([{"article_id": ARTICLE_A, "approved": True}], [ARTICLE_A, ARTICLE_B])
    with pytest.raises(StatuteCryptoError):
        validate_decisions(
            [
                {"article_id": ARTICLE_A, "approved": False, "comment": "   "},
                {"article_id": ARTICLE_B, "approved": True},
            ],
            [ARTICLE_A, ARTICLE_B],
        )
    with pytest.raises(StatuteCryptoError):
        validate_decisions(
            [
                {"article_id": ARTICLE_A, "approved": True, "comment": "de más"},
                {"article_id": ARTICLE_B, "approved": True},
            ],
            [ARTICLE_A, ARTICLE_B],
        )
    decisions = validate_decisions(
        [
            {"article_id": ARTICLE_B, "approved": True, "comment": ""},
            {"article_id": ARTICLE_A, "approved": False, "comment": "  No acepto el texto  "},
        ],
        [ARTICLE_A, ARTICLE_B],
    )
    assert decisions[0]["article_id"] == ARTICLE_A
    assert decisions[0]["comment"] == "No acepto el texto"
    assert decisions[1]["comment"] is None
    assert (
        canonical_statute_plaintext(decisions, NONCE)
        == '{"decisions":[{"approved":false,"article_id":"'
        + ARTICLE_A
        + '","comment":"No acepto el texto"},{"approved":true,"article_id":"'
        + ARTICLE_B
        + '"}],"nonce":"'
        + NONCE
        + '"}'
    )


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _seal(public_key, plaintext: str) -> str:  # type: ignore[no-untyped-def]
    aes_key = AESGCM.generate_key(bit_length=256)
    iv = b"\x01" * 12
    ciphertext = AESGCM(aes_key).encrypt(iv, plaintext.encode("utf-8"), None)
    wrapped = public_key.encrypt(
        aes_key,
        OAEP(mgf=MGF1(algorithm=SHA256()), algorithm=SHA256(), label=None),
    )
    return json.dumps(
        {
            "algorithm": "RSA-OAEP-256/AES-256-GCM",
            "wrapped_key": _b64(wrapped),
            "iv": _b64(iv),
            "ciphertext": _b64(ciphertext),
            "key_version": "v1",
        },
        separators=(",", ":"),
    )


def test_envelope_hides_comment_until_private_key() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    decisions = validate_decisions(
        [
            {"article_id": ARTICLE_A, "approved": False, "comment": "comentario secreto"},
            {"article_id": ARTICLE_B, "approved": True},
        ],
        [ARTICLE_A, ARTICLE_B],
    )
    plaintext = canonical_statute_plaintext(decisions, NONCE)
    encrypted = _seal(private_key.public_key(), plaintext)
    assert "comentario secreto" not in encrypted
    with pytest.raises(StatuteCryptoError):
        decrypt_statute_plaintext(
            encrypted_payload=encrypted,
            receipt_hash="0" * 64,
            key_version="v1",
            private_key=rsa.generate_private_key(public_exponent=65537, key_size=2048),
        )
    receipt = hashlib.sha256(encrypted.encode("utf-8")).hexdigest()
    opened = decrypt_statute_plaintext(
        encrypted_payload=encrypted,
        receipt_hash=receipt,
        key_version="v1",
        private_key=private_key,
    )
    parsed, nonce = parse_statute_plaintext(opened, [ARTICLE_A, ARTICLE_B])
    assert nonce == NONCE
    assert parsed[0]["comment"] == "comentario secreto"
    binding = hashlib.sha256(
        f"{encrypted}:{hashlib.sha256(opened.encode()).hexdigest()}".encode()
    ).hexdigest()
    proof = encode_statute_proof(
        commitment=hashlib.sha256(opened.encode()).hexdigest(),
        payload_binding=binding,
        article_set_hash_value=article_set_hash([ARTICLE_A, ARTICLE_B]),
    )
    verify_statute_proof_at_cast(
        encrypted_payload=encrypted,
        zkp_proof=proof,
        article_set_hash_value=article_set_hash([ARTICLE_B, ARTICLE_A]),
        require_integrity_proof=True,
        allow_dev_stub=False,
    )
    verify_statute_proof_after_decrypt(
        zkp_proof=proof,
        plaintext=opened,
        encrypted_payload=encrypted,
        article_set_hash_value=article_set_hash([ARTICLE_A, ARTICLE_B]),
        require_integrity_proof=True,
    )


def test_tally_names_the_member_on_each_comment() -> None:
    member_id = str(uuid4())
    artifact = build_statute_tally_artifact(
        consultation_id=str(uuid4()),
        public_key_sha256="ab" * 32,
        eligible_member_count=1,
        voted_member_count=1,
        quorum_threshold_pct=Decimal("30.00"),
        approval_threshold_pct=Decimal("50.00"),
        quorum_required=1,
        articles=[
            StatuteArticleView(
                article_id=ARTICLE_A,
                number=1,
                content="Texto del artículo",
                title_number=1,
                title_description="DISPOSICIONES",
                chapter_number=1,
                chapter_description="General",
                ),
        ],
        ballots=[
            DecodedStatuteBallot(
                member_id=member_id,
                full_name="Ana Pérez",
                registry_code="REG-1",
                receipt_hash="cd" * 32,
                decisions=[
                    {
                        "article_id": ARTICLE_A,
                        "approved": False,
                        "comment": "Propongo otro redacción",
                    }
                ],
            )
        ],
    )
    article = artifact["articles"][0]
    assert article["meets_threshold"] is False
    assert article["responses"][0]["full_name"] == "Ana Pérez"
    assert article["responses"][0]["registry_code"] == "REG-1"
    assert article["responses"][0]["comment"] == "Propongo otro redacción"
    assert artifact["artifact_version"] == "statute-tally-v1"


def test_election_urn_stays_anonymous() -> None:
    assert "member_id" not in EncryptedBallot.__table__.columns
    assert "member_id" in StatuteBallot.__table__.columns


def test_statute_cast_requires_voter_auth() -> None:
    response = client.post(
        "/api/v1/voter/statutes/00000000-0000-0000-0000-000000000001/ballots",
        json={
            "encrypted_payload": "x" * 40,
            "receipt_hash": "a" * 64,
            "zkp_proof": "b" * 40,
            "key_version": "v1",
        },
    )
    assert response.status_code == 401


def test_admin_statute_requires_auth() -> None:
    response = client.get("/api/v1/admin/statutes")
    assert response.status_code == 401
