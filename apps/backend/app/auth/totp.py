from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_SECRET_BYTES = 20
_SECRET_LENGTH = 32
_TOTP_STEP_SECONDS = 30
_TOTP_DIGITS = 6
_TOTP_WINDOW = 1
_NONCE_BYTES = 12
_AAD = b"evoting-admin-totp-v1"
_CIPHERTEXT_PREFIX = "v1."


class MfaConfigurationError(RuntimeError):
    """Raised when the server cannot protect an MFA secret safely."""


def _encryption_key() -> bytes:
    encoded = settings.mfa_encryption_key
    if not encoded:
        raise MfaConfigurationError("MFA_ENCRYPTION_KEY is not configured")
    try:
        encoded_value = encoded.encode("ascii")
        padded_value = encoded_value + b"=" * ((4 - len(encoded_value) % 4) % 4)
        key = base64.urlsafe_b64decode(padded_value)
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise MfaConfigurationError("MFA_ENCRYPTION_KEY must be URL-safe base64") from exc
    if len(key) != 32:
        raise MfaConfigurationError("MFA_ENCRYPTION_KEY must decode to 32 bytes")
    return key


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(_SECRET_BYTES)).decode("ascii").rstrip("=")


def encrypt_totp_secret(secret: str) -> str:
    nonce = secrets.token_bytes(_NONCE_BYTES)
    encrypted = AESGCM(_encryption_key()).encrypt(nonce, secret.encode("ascii"), _AAD)
    payload = base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")
    return _CIPHERTEXT_PREFIX + payload


def decrypt_totp_secret(ciphertext: str) -> str:
    if not ciphertext.startswith(_CIPHERTEXT_PREFIX):
        raise MfaConfigurationError("Unsupported MFA secret encryption version")
    try:
        payload = base64.urlsafe_b64decode(ciphertext[len(_CIPHERTEXT_PREFIX) :].encode("ascii"))
        plaintext = AESGCM(_encryption_key()).decrypt(
            payload[:_NONCE_BYTES], payload[_NONCE_BYTES:], _AAD
        )
        secret = plaintext.decode("ascii")
        _decode_secret(secret)
        return secret
    except (InvalidTag, ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise MfaConfigurationError("Stored MFA secret could not be decrypted") from exc


def _decode_secret(secret: str) -> bytes:
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    try:
        decoded = base64.b32decode(padded, casefold=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid TOTP secret") from exc
    if len(decoded) != _SECRET_BYTES:
        raise ValueError("Invalid TOTP secret length")
    return decoded


def _hotp(secret: bytes, counter: int) -> str:
    digest = hmac.new(secret, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10**_TOTP_DIGITS)).zfill(_TOTP_DIGITS)


def verify_totp(secret: str, code: str, now: int | None = None) -> int | None:
    """Return the accepted counter, or None for an invalid code."""
    if len(code) != _TOTP_DIGITS or not code.isdecimal():
        return None
    secret_bytes = _decode_secret(secret)
    current_counter = int((time.time() if now is None else now) // _TOTP_STEP_SECONDS)
    for offset in range(-_TOTP_WINDOW, _TOTP_WINDOW + 1):
        counter = current_counter + offset
        if counter >= 0 and hmac.compare_digest(_hotp(secret_bytes, counter), code):
            return counter
    return None


def build_totp_uri(secret: str, email: str, organization_slug: str) -> str:
    label = quote(f"{organization_slug}:{email}", safe="")
    issuer = quote("eVoting Admin", safe="")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={issuer}"
        f"&algorithm=SHA1&digits={_TOTP_DIGITS}&period={_TOTP_STEP_SECONDS}"
    )
