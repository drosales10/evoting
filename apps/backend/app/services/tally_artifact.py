from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.padding import MGF1, PSS
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey


def canonicalize_artifact(artifact: Mapping[str, Any]) -> bytes:
    return json.dumps(
        artifact,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def artifact_sha256(artifact: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonicalize_artifact(artifact)).hexdigest()


def encode_signature(signature: bytes) -> str:
    return base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")


def decode_signature(value: str) -> bytes:
    try:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)
    except ValueError as exc:
        raise ValueError("Invalid tally signature encoding") from exc


def sign_artifact(artifact: Mapping[str, Any], private_key: RSAPrivateKey) -> str:
    signature = private_key.sign(
        canonicalize_artifact(artifact),
        PSS(mgf=MGF1(hashes.SHA256()), salt_length=PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return encode_signature(signature)


def verify_artifact(
    artifact: Mapping[str, Any],
    signature: str,
    public_key: RSAPublicKey,
) -> bool:
    try:
        public_key.verify(
            decode_signature(signature),
            canonicalize_artifact(artifact),
            PSS(mgf=MGF1(hashes.SHA256()), salt_length=PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True
