from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from jose import JWTError, jwt  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from app.auth.realms import Realm
from app.core.config import settings

ALGORITHM = "HS256"


class AccessClaims(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sub: UUID
    realm: Realm
    org_id: UUID
    roles: list[str]
    session_id: UUID
    token_type: str
    iat: datetime
    exp: datetime


def _jwt_secret() -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")
    return settings.jwt_secret


def create_access_token(
    *,
    subject: UUID,
    realm: Realm,
    organization_id: UUID,
    roles: list[str],
    session_id: UUID | None = None,
) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(subject),
        "realm": realm,
        "org_id": str(organization_id),
        "roles": roles,
        "session_id": str(session_id or uuid4()),
        "token_type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return cast(str, jwt.encode(claims, _jwt_secret(), algorithm=ALGORITHM))


def decode_access_token(token: str, expected_realm: Realm) -> AccessClaims:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
        claims = AccessClaims.model_validate(payload)
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid access token") from exc

    if claims.realm != expected_realm or claims.token_type != "access":
        raise ValueError("Invalid access token realm")
    return claims
