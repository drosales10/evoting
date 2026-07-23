import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMfaEnrollmentResponse,
    AdminMfaEnrollRequest,
    AdminMfaVerifyRequest,
    AuthContractResponse,
    LogoutResponse,
    OtpAcceptedResponse,
    RefreshResponse,
    VoterLoginResponse,
    VoterOtpRequest,
    VoterOtpVerifyRequest,
)
from app.auth.passwords import hash_password, verify_password
from app.auth.realms import (
    ADMIN_ACCESS_COOKIE,
    ADMIN_REFRESH_COOKIE,
    VOTER_ACCESS_COOKIE,
    VOTER_REFRESH_COOKIE,
)
from app.auth.tokens import create_access_token
from app.auth.totp import (
    MfaConfigurationError,
    build_totp_uri,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_totp_secret,
    verify_totp,
)
from app.core.config import settings
from app.db.session import get_db_session
from app.models import AuthSession, Member, Organization, VoterOtpChallenge
from app.repositories.admin_users import AdminUserRecord, AdminUserRepository
from app.services.audit import append_audit_event
from app.services.csrf import hash_csrf_token
from app.services.mailtrap_email import is_mailtrap_configured, send_voter_otp_email
from app.services.rate_limit import client_key, rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
DUMMY_PASSWORD_HASH = hash_password("invalid-password-placeholder")


def _hash_refresh(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_voter_value(value: str) -> str:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voter authentication is not configured",
        )
    return hashlib.sha256(f"{settings.jwt_secret}:{value}".encode()).hexdigest()


def _mask_voter_identifier(value: str) -> str:
    normalized = value.strip()
    if "@" in normalized:
        local_part, _, domain = normalized.partition("@")
        return f"{local_part[:1]}***@{domain}"
    if len(normalized) <= 4:
        return "***"
    return f"{normalized[:2]}***{normalized[-2:]}"


def _actor_hash(principal_id: UUID) -> str:
    return hashlib.sha256(str(principal_id).encode("utf-8")).hexdigest()


def _set_access_cookie(response: Response, *, realm: Literal["ADMIN", "VOTER"], token: str) -> None:
    name = ADMIN_ACCESS_COOKIE if realm == "ADMIN" else VOTER_ACCESS_COOKIE
    response.set_cookie(
        name,
        token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        max_age=settings.access_token_minutes * 60,
        path="/",
    )


def _set_refresh_cookie(
    response: Response, *, realm: Literal["ADMIN", "VOTER"], token: str
) -> None:
    name = ADMIN_REFRESH_COOKIE if realm == "ADMIN" else VOTER_REFRESH_COOKIE
    response.set_cookie(
        name,
        token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path="/api/v1/auth",
    )


def _clear_auth_cookies(response: Response, realm: Literal["ADMIN", "VOTER"]) -> None:
    if realm == "ADMIN":
        response.delete_cookie(ADMIN_ACCESS_COOKIE, path="/")
        response.delete_cookie(ADMIN_REFRESH_COOKIE, path="/api/v1/auth")
    else:
        response.delete_cookie(VOTER_ACCESS_COOKIE, path="/")
        response.delete_cookie(VOTER_REFRESH_COOKIE, path="/api/v1/auth")


async def _authenticate_admin(
    payload: AdminLoginRequest,
    session: AsyncSession,
) -> tuple[AdminUserRepository, AdminUserRecord]:
    repository = AdminUserRepository()
    user = await repository.find_by_credentials(
        session,
        organization_slug=payload.organization_slug,
        email=payload.email,
    )

    if user is None:
        verify_password(payload.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not verify_password(payload.password, user.password_hash) or user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has no assigned role",
        )
    return repository, user


async def _issue_admin_session(
    response: Response,
    session: AsyncSession,
    repository: AdminUserRepository,
    user: AdminUserRecord,
) -> AdminLoginResponse:
    credentials = await repository.create_session(session, user)
    access_token = create_access_token(
        subject=user.id,
        realm="ADMIN",
        organization_id=user.organization_id,
        roles=list(user.roles),
        session_id=credentials.session.id,
    )
    _set_access_cookie(response, realm="ADMIN", token=access_token)
    _set_refresh_cookie(response, realm="ADMIN", token=credentials.refresh_token)
    await append_audit_event(
        session,
        organization_id=user.organization_id,
        event_type="ADMIN_LOGIN",
        actor_id_hash=_actor_hash(user.id),
        details={"session_id": str(credentials.session.id)},
    )
    await session.commit()
    return AdminLoginResponse(
        status="AUTHENTICATED",
        mfa_required=False,
        csrf_token=credentials.csrf_token,
    )


async def _rotate_session(
    session: AsyncSession,
    auth_session: AuthSession,
    *,
    realm: Literal["ADMIN", "VOTER"],
    roles: list[str],
) -> tuple[str, str, str]:
    now = datetime.now(UTC)
    auth_session.revoked_at = now
    refresh_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    new_session = AuthSession(
        id=uuid4(),
        organization_id=auth_session.organization_id,
        principal_id=auth_session.principal_id,
        realm=realm,
        refresh_token_hash=(
            _hash_refresh(refresh_token) if realm == "ADMIN" else _hash_voter_value(refresh_token)
        ),
        csrf_token_hash=hash_csrf_token(csrf_token),
        expires_at=now + timedelta(days=settings.refresh_token_days),
    )
    session.add(new_session)
    access_token = create_access_token(
        subject=auth_session.principal_id,
        realm=realm,
        organization_id=auth_session.organization_id,
        roles=roles,
        session_id=new_session.id,
    )
    await session.commit()
    return access_token, refresh_token, csrf_token


@router.get("/contract", response_model=AuthContractResponse)
async def auth_contract() -> AuthContractResponse:
    """Expose the versioned auth surface without exposing session state."""
    return AuthContractResponse(
        admin_login="/api/v1/auth/admin/login",
        admin_refresh="/api/v1/auth/admin/refresh",
        admin_logout="/api/v1/auth/admin/logout",
        voter_request_otp="/api/v1/auth/voter/request-otp",
        voter_verify_otp="/api/v1/auth/voter/verify-otp",
        voter_refresh="/api/v1/auth/voter/refresh",
        voter_logout="/api/v1/auth/voter/logout",
        note=(
            f"ADMIN and VOTER use separate HttpOnly cookies: {ADMIN_ACCESS_COOKIE} and "
            f"{VOTER_ACCESS_COOKIE}. Refresh cookies rotate on use. CSRF tokens are returned "
            "on login/refresh and required on authenticated mutations."
        ),
    )


@router.post("/admin/login", response_model=AdminLoginResponse)
async def admin_login(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminLoginResponse:
    """Authenticate an ADMIN identity without accepting VOTER cookies."""
    response.headers["Cache-Control"] = "no-store"
    rate_limiter.hit(
        client_key(request, "admin-login"),
        limit=settings.rate_limit_login_per_minute,
        window_seconds=60,
    )
    repository, user = await _authenticate_admin(payload, session)

    mfa_required = settings.admin_mfa_required and (
        user.mfa_enabled or settings.environment != "development"
    )
    if mfa_required:
        return AdminLoginResponse(status="MFA_REQUIRED", mfa_required=True, csrf_token=None)
    return await _issue_admin_session(response, session, repository, user)


@router.post(
    "/admin/mfa/enroll",
    response_model=AdminMfaEnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_admin_mfa(
    payload: AdminMfaEnrollRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminMfaEnrollmentResponse:
    """Enroll a TOTP factor once using the administrator's password."""
    response.headers["Cache-Control"] = "no-store"
    rate_limiter.hit(
        client_key(request, "admin-mfa-enroll"),
        limit=settings.rate_limit_login_per_minute,
        window_seconds=60,
    )
    repository, user = await _authenticate_admin(payload, session)
    if not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is disabled for this account",
        )
    if await repository.find_mfa_credential(session, user.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MFA is already enrolled",
        )

    secret = generate_totp_secret()
    try:
        encrypted_secret = encrypt_totp_secret(secret)
    except MfaConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MFA encryption is not configured",
        ) from exc

    if not await repository.enroll_mfa(session, user, encrypted_secret):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MFA is already enrolled",
        )
    return AdminMfaEnrollmentResponse(
        status="ENROLLED",
        secret=secret,
        otpauth_uri=build_totp_uri(secret, payload.email, payload.organization_slug),
    )


@router.post("/admin/mfa/verify", response_model=AdminLoginResponse)
async def verify_admin_mfa(
    payload: AdminMfaVerifyRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminLoginResponse:
    """Complete ADMIN login with a current, non-replayed TOTP code."""
    response.headers["Cache-Control"] = "no-store"
    rate_limiter.hit(
        client_key(request, "admin-mfa-verify"),
        limit=settings.rate_limit_login_per_minute,
        window_seconds=60,
    )
    repository, user = await _authenticate_admin(payload, session)
    if not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is disabled for this account",
        )
    credential = await repository.find_mfa_credential(session, user.id)
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MFA is not enrolled for this account",
        )

    try:
        secret = decrypt_totp_secret(credential.encrypted_secret)
    except MfaConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MFA encryption is not configured correctly",
        ) from exc

    counter = verify_totp(secret, payload.code)
    if counter is None or not await repository.consume_mfa_counter(session, user.id, counter):
        await append_audit_event(
            session,
            organization_id=user.organization_id,
            event_type="ADMIN_MFA_FAILED",
            actor_id_hash=_actor_hash(user.id),
            details={},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code",
        )
    return await _issue_admin_session(response, session, repository, user)


@router.post("/admin/refresh", response_model=RefreshResponse)
async def refresh_admin_session(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RefreshResponse:
    response.headers["Cache-Control"] = "no-store"
    rate_limiter.hit(
        client_key(request, "admin-refresh"),
        limit=settings.rate_limit_login_per_minute,
        window_seconds=60,
    )
    refresh_token = request.cookies.get(ADMIN_REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh required")
    token_hash = _hash_refresh(refresh_token)
    auth_session = await session.scalar(
        select(AuthSession)
        .where(
            AuthSession.refresh_token_hash == token_hash,
            AuthSession.realm == "ADMIN",
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
        .with_for_update()
    )
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh")
    from app.models import AdminUserRole

    roles = list(
        await session.scalars(
            select(AdminUserRole.role).where(
                AdminUserRole.admin_user_id == auth_session.principal_id
            )
        )
    )
    access, refresh, csrf = await _rotate_session(
        session, auth_session, realm="ADMIN", roles=roles or ["ELECTORAL_JUSTICE"]
    )
    _set_access_cookie(response, realm="ADMIN", token=access)
    _set_refresh_cookie(response, realm="ADMIN", token=refresh)
    return RefreshResponse(status="AUTHENTICATED", realm="ADMIN", csrf_token=csrf)


@router.post("/admin/logout", response_model=LogoutResponse)
async def logout_admin(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogoutResponse:
    response.headers["Cache-Control"] = "no-store"
    refresh_token = request.cookies.get(ADMIN_REFRESH_COOKIE)
    if refresh_token:
        auth_session = await session.scalar(
            select(AuthSession).where(
                AuthSession.refresh_token_hash == _hash_refresh(refresh_token),
                AuthSession.realm == "ADMIN",
            )
        )
        if auth_session and auth_session.revoked_at is None:
            auth_session.revoked_at = datetime.now(UTC)
            await append_audit_event(
                session,
                organization_id=auth_session.organization_id,
                event_type="ADMIN_LOGOUT",
                actor_id_hash=_actor_hash(auth_session.principal_id),
                details={},
            )
            await session.commit()
    _clear_auth_cookies(response, "ADMIN")
    return LogoutResponse(status="LOGGED_OUT")


@router.post("/voter/request-otp", response_model=OtpAcceptedResponse, status_code=202)
async def request_voter_otp(
    payload: VoterOtpRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OtpAcceptedResponse:
    """Create an OTP challenge and deliver it through the configured provider."""
    response.headers["Cache-Control"] = "no-store"
    rate_limiter.hit(
        client_key(request, "voter-otp-request"),
        limit=settings.rate_limit_otp_per_minute,
        window_seconds=60,
    )
    if settings.voter_test_mode:
        test_code = settings.voter_test_code
        if not test_code:
            return OtpAcceptedResponse()
        if len(test_code) != 6 or not test_code.isdigit():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="VOTER_TEST_CODE must contain exactly six digits",
            )
    elif not is_mailtrap_configured():
        return OtpAcceptedResponse()
    else:
        test_code = None

    organization = await session.scalar(
        select(Organization).where(Organization.slug == payload.organization_slug.strip())
    )
    if organization is None:
        return OtpAcceptedResponse()
    identifier = payload.identifier.strip().lower()
    member = await session.scalar(
        select(Member).where(
            Member.organization_id == organization.id,
            or_(Member.email == identifier, Member.dni == payload.identifier.strip()),
        )
    )
    if member is None:
        return OtpAcceptedResponse()

    otp_code = test_code or f"{secrets.randbelow(1_000_000):06d}"
    recipient = member.email
    if not recipient:
        return OtpAcceptedResponse()
    challenge = VoterOtpChallenge(
        organization_id=organization.id,
        member_id=member.id,
        code_hash=_hash_voter_value(otp_code),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        purpose="LOGIN",
    )
    session.add(challenge)
    await session.commit()
    delivery_fallback = settings.voter_test_mode and not is_mailtrap_configured()
    if is_mailtrap_configured():
        try:
            await send_voter_otp_email(recipient, otp_code, challenge.expires_at)
        except Exception as exc:
            if settings.environment == "development" and settings.voter_test_mode:
                delivery_fallback = True
                logger.warning(
                    "[DEV ONLY] Mailtrap OTP delivery failed; using terminal fallback "
                    "for challenge_id=%s: %s",
                    challenge.id,
                    exc,
                )
            else:
                logger.exception(
                    "VOTER OTP email delivery failed for organization=%s",
                    organization.slug,
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="OTP delivery is temporarily unavailable",
                ) from exc
    if settings.environment == "development" and settings.voter_test_mode:
        logger.warning(
            "[DEV ONLY] VOTER OTP issued: challenge_id=%s code=%s expires_at=%s "
            "organization=%s identifier=%s",
            challenge.id,
            otp_code,
            challenge.expires_at.isoformat(),
            organization.slug,
            _mask_voter_identifier(payload.identifier),
        )
    elif settings.is_production:
        # Never log OTP material outside controlled development + test mode.
        logger.info("VOTER OTP challenge created challenge_id=%s", challenge.id)
    message = (
        "OTP challenge created; use the development code in the backend terminal."
        if delivery_fallback
        else "OTP challenge created; use the code delivered to the voter."
    )
    return OtpAcceptedResponse(
        challenge_id=str(challenge.id),
        message=message,
    )


@router.post("/voter/verify-otp", response_model=VoterLoginResponse)
async def verify_voter_otp(
    payload: VoterOtpVerifyRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VoterLoginResponse:
    """Verify a one-time OTP and issue a separate VOTER session."""
    response.headers["Cache-Control"] = "no-store"
    rate_limiter.hit(
        client_key(request, "voter-otp-verify"),
        limit=settings.rate_limit_otp_per_minute,
        window_seconds=60,
    )
    if not settings.voter_test_mode and not is_mailtrap_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voter OTP delivery is not configured",
        )
    try:
        challenge_id = UUID(payload.challenge_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP challenge",
        ) from exc

    challenge = await session.scalar(
        select(VoterOtpChallenge).where(VoterOtpChallenge.id == challenge_id).with_for_update()
    )
    now = datetime.now(UTC)
    if (
        challenge is None
        or challenge.consumed_at is not None
        or challenge.expires_at <= now
        or challenge.attempts >= 5
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP challenge",
        )
    submitted_hash = _hash_voter_value(payload.code)
    if not hmac.compare_digest(submitted_hash, challenge.code_hash):
        challenge.attempts += 1
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP code",
        )

    challenge.consumed_at = now
    csrf_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(48)
    auth_session = AuthSession(
        id=uuid4(),
        organization_id=challenge.organization_id,
        principal_id=challenge.member_id,
        realm="VOTER",
        refresh_token_hash=_hash_voter_value(refresh_token),
        csrf_token_hash=hash_csrf_token(csrf_token),
        expires_at=now + timedelta(days=settings.refresh_token_days),
    )
    session.add(auth_session)
    access_token = create_access_token(
        subject=challenge.member_id,
        realm="VOTER",
        organization_id=challenge.organization_id,
        roles=["MEMBER"],
        session_id=auth_session.id,
    )
    await session.commit()
    _set_access_cookie(response, realm="VOTER", token=access_token)
    _set_refresh_cookie(response, realm="VOTER", token=refresh_token)
    return VoterLoginResponse(status="AUTHENTICATED", csrf_token=csrf_token)


@router.post("/voter/refresh", response_model=RefreshResponse)
async def refresh_voter_session(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RefreshResponse:
    response.headers["Cache-Control"] = "no-store"
    rate_limiter.hit(
        client_key(request, "voter-refresh"),
        limit=settings.rate_limit_login_per_minute,
        window_seconds=60,
    )
    refresh_token = request.cookies.get(VOTER_REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh required")
    auth_session = await session.scalar(
        select(AuthSession)
        .where(
            AuthSession.refresh_token_hash == _hash_voter_value(refresh_token),
            AuthSession.realm == "VOTER",
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
        .with_for_update()
    )
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh")
    access, refresh, csrf = await _rotate_session(
        session, auth_session, realm="VOTER", roles=["MEMBER"]
    )
    _set_access_cookie(response, realm="VOTER", token=access)
    _set_refresh_cookie(response, realm="VOTER", token=refresh)
    return RefreshResponse(status="AUTHENTICATED", realm="VOTER", csrf_token=csrf)


@router.post("/voter/logout", response_model=LogoutResponse)
async def logout_voter(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogoutResponse:
    response.headers["Cache-Control"] = "no-store"
    refresh_token = request.cookies.get(VOTER_REFRESH_COOKIE)
    if refresh_token and settings.jwt_secret:
        auth_session = await session.scalar(
            select(AuthSession).where(
                AuthSession.refresh_token_hash == _hash_voter_value(refresh_token),
                AuthSession.realm == "VOTER",
            )
        )
        if auth_session and auth_session.revoked_at is None:
            auth_session.revoked_at = datetime.now(UTC)
            await session.commit()
    _clear_auth_cookies(response, "VOTER")
    return LogoutResponse(status="LOGGED_OUT")
