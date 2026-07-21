import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMfaEnrollmentResponse,
    AdminMfaEnrollRequest,
    AdminMfaVerifyRequest,
    AuthContractResponse,
    OtpAcceptedResponse,
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
from app.services.mailtrap_email import is_mailtrap_configured, send_voter_otp_email

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
DUMMY_PASSWORD_HASH = hash_password("invalid-password-placeholder")


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
    response.set_cookie(
        ADMIN_ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        max_age=settings.access_token_minutes * 60,
        path="/",
    )
    response.set_cookie(
        ADMIN_REFRESH_COOKIE,
        credentials.refresh_token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path="/api/v1/auth",
    )
    return AdminLoginResponse(status="AUTHENTICATED", mfa_required=False)


@router.get("/contract", response_model=AuthContractResponse)
async def auth_contract() -> AuthContractResponse:
    """Expose the versioned auth surface without exposing session state."""
    return AuthContractResponse(
        admin_login="/api/v1/auth/admin/login",
        voter_request_otp="/api/v1/auth/voter/request-otp",
        voter_verify_otp="/api/v1/auth/voter/verify-otp",
        note=(
            f"ADMIN and VOTER use separate HttpOnly cookies: {ADMIN_ACCESS_COOKIE} and "
            f"{VOTER_ACCESS_COOKIE}. Admin MFA uses encrypted TOTP credentials; voter OTP "
            "delivery remains required before issuing voter sessions."
        ),
    )


@router.post("/admin/login", response_model=AdminLoginResponse)
async def admin_login(
    payload: AdminLoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminLoginResponse:
    """Authenticate an ADMIN identity without accepting VOTER cookies."""
    response.headers["Cache-Control"] = "no-store"
    repository, user = await _authenticate_admin(payload, session)

    if settings.admin_mfa_required and (user.mfa_enabled or settings.environment != "development"):
        return AdminLoginResponse(status="MFA_REQUIRED", mfa_required=True)
    return await _issue_admin_session(response, session, repository, user)


@router.post(
    "/admin/mfa/enroll",
    response_model=AdminMfaEnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def enroll_admin_mfa(
    payload: AdminMfaEnrollRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminMfaEnrollmentResponse:
    """Enroll a TOTP factor once using the administrator's password."""
    response.headers["Cache-Control"] = "no-store"
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
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminLoginResponse:
    """Complete ADMIN login with a current, non-replayed TOTP code."""
    response.headers["Cache-Control"] = "no-store"
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code",
        )
    return await _issue_admin_session(response, session, repository, user)


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


@router.post("/voter/request-otp", response_model=OtpAcceptedResponse, status_code=202)
async def request_voter_otp(
    payload: VoterOtpRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OtpAcceptedResponse:
    """Create an OTP challenge and deliver it through the configured provider."""
    response.headers["Cache-Control"] = "no-store"
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
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VoterLoginResponse:
    """Verify a one-time development OTP and issue a separate VOTER session."""
    response.headers["Cache-Control"] = "no-store"
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
        csrf_token_hash=_hash_voter_value(csrf_token),
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
    response.set_cookie(
        VOTER_ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        max_age=settings.access_token_minutes * 60,
        path="/",
    )
    response.set_cookie(
        VOTER_REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path="/api/v1/auth",
    )
    return VoterLoginResponse(status="AUTHENTICATED", csrf_token=csrf_token)
