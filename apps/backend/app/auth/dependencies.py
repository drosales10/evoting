from typing import Annotated

from fastapi import Cookie, HTTPException, status

from app.auth.realms import ADMIN_ACCESS_COOKIE, VOTER_ACCESS_COOKIE
from app.auth.tokens import AccessClaims, decode_access_token


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_admin(
    token: Annotated[str | None, Cookie(alias=ADMIN_ACCESS_COOKIE)] = None,
) -> AccessClaims:
    if not token:
        raise _unauthorized()
    try:
        return decode_access_token(token, "ADMIN")
    except ValueError as exc:
        raise _unauthorized() from exc


async def require_voter(
    token: Annotated[str | None, Cookie(alias=VOTER_ACCESS_COOKIE)] = None,
) -> AccessClaims:
    if not token:
        raise _unauthorized()
    try:
        return decode_access_token(token, "VOTER")
    except ValueError as exc:
        raise _unauthorized() from exc
