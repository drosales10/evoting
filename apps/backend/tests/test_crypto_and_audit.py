"""Unit tests for ballot crypto, tally artifact and audit hashing."""

from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.audit import compute_entry_hash
from app.services.ballot_crypto import (
    BallotCryptoError,
    encode_integrity_proof,
    parse_encrypted_payload,
    slate_set_hash,
    verify_proof_after_decrypt,
    verify_proof_at_cast,
)
from app.services.tally_acta import build_official_acta
from app.services.tally_artifact import artifact_sha256, sign_artifact, verify_artifact


def test_parse_encrypted_payload_rejects_opaque_string() -> None:
    with pytest.raises(BallotCryptoError):
        parse_encrypted_payload("not-json-ciphertext-value-long-enough")


def test_parse_encrypted_payload_accepts_structure() -> None:
    payload = (
        '{"algorithm":"RSA-OAEP-256/AES-256-GCM",'
        '"wrapped_key":"YWJjZGVmZ2hpamtsbW5vcA",'
        '"iv":"YWJjZGVmZ2hpamts",'
        '"ciphertext":"YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXo",'
        '"key_version":"v1"}'
    )
    parsed = parse_encrypted_payload(payload)
    assert parsed["algorithm"] == "RSA-OAEP-256/AES-256-GCM"


def test_integrity_proof_roundtrip() -> None:
    slate_id = str(uuid4())
    nonce = "abc123"
    encrypted = (
        '{"algorithm":"RSA-OAEP-256/AES-256-GCM",'
        '"wrapped_key":"YWJjZGVmZ2hpamtsbW5vcA",'
        '"iv":"YWJjZGVmZ2hpamts",'
        '"ciphertext":"YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXo",'
        '"key_version":"v1"}'
    )
    commitment = hashlib.sha256(f"{slate_id}:{nonce}".encode()).hexdigest()
    binding = hashlib.sha256(f"{encrypted}:{commitment}".encode()).hexdigest()
    set_hash = slate_set_hash([slate_id, str(uuid4())])
    proof = encode_integrity_proof(
        commitment=commitment,
        payload_binding=binding,
        slate_set_hash_value=set_hash,
    )
    verify_proof_at_cast(
        encrypted_payload=encrypted,
        zkp_proof=proof,
        slate_set_hash=set_hash,
        require_integrity_proof=True,
        allow_dev_stub=False,
    )
    verify_proof_after_decrypt(
        zkp_proof=proof,
        slate_id=slate_id,
        nonce=nonce,
        encrypted_payload=encrypted,
        require_integrity_proof=True,
    )


def test_stub_proof_rejected_outside_dev() -> None:
    with pytest.raises(BallotCryptoError):
        verify_proof_at_cast(
            encrypted_payload="x" * 40,
            zkp_proof="development-pilot-proof-" + ("a" * 64),
            slate_set_hash="b" * 64,
            require_integrity_proof=False,
            allow_dev_stub=False,
        )


def test_artifact_sign_and_verify() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    artifact = {
        "artifact_version": "pilot-tally-v1",
        "election_id": str(uuid4()),
        "ballot_count": 2,
        "counts": [{"slate_id": str(uuid4()), "slate_name": "A", "votes": 2}],
    }
    signature = sign_artifact(artifact, key)
    assert verify_artifact(artifact, signature, key.public_key())
    tampered = {**artifact, "ballot_count": 3}
    assert not verify_artifact(tampered, signature, key.public_key())
    assert len(artifact_sha256(artifact)) == 64


def test_audit_hash_chain_changes_with_prev() -> None:
    org = uuid4()
    first = compute_entry_hash(
        organization_id=org,
        event_type="ADMIN_LOGIN",
        actor_id_hash="a" * 64,
        details={"ok": True},
        prev_hash=None,
    )
    second = compute_entry_hash(
        organization_id=org,
        event_type="ADMIN_LOGIN",
        actor_id_hash="a" * 64,
        details={"ok": True},
        prev_hash=first,
    )
    assert first != second


def test_official_acta_contains_hash() -> None:
    artifact = {"election_id": str(uuid4()), "ballot_count": 220, "quorum_met": True, "counts": []}
    acta = build_official_acta(
        artifact=artifact,
        signature="sig",
        artifact_sha256_hex="c" * 64,
        dual_approval={"required": True},
    )
    assert acta["acta_version"] == "official-acta-v1"
    assert len(acta["acta_sha256"]) == 64


def test_public_key_pem_roundtrip_for_verify_cli() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    assert b"BEGIN PUBLIC KEY" in pem
