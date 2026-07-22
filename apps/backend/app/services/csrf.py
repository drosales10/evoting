"""Shared CSRF helpers for ADMIN and VOTER realms."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import AccessClaims
from app.core.config import settings
from app.models import AuthSession


def hash_csrf_token(token: str) -> str:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    return hashlib.sha256(f"{settings.jwt_secret}:{token}".encode()).hexdigest()


async def require_csrf(
    session: AsyncSession,
    claims: AccessClaims,
    csrf_token: str | None,
    *,
    realm: str,
) -> AuthSession:
    if not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token required",
        )
    auth_session = await session.scalar(
        select(AuthSession).where(
            AuthSession.id == claims.session_id,
            AuthSession.organization_id == claims.org_id,
            AuthSession.principal_id == claims.sub,
            AuthSession.realm == realm,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    if auth_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is not active",
        )
    expected = hash_csrf_token(csrf_token)
    if not hmac.compare_digest(expected, auth_session.csrf_token_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )
    return auth_session
