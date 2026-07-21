from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMfaEnrollmentResponse,
    AdminMfaEnrollRequest,
    AdminMfaVerifyRequest,
    AuthContractResponse,
    OtpAcceptedResponse,
    VoterOtpRequest,
    VoterOtpVerifyRequest,
)
from app.auth.passwords import hash_password, verify_password
from app.auth.realms import (
    ADMIN_ACCESS_COOKIE,
    ADMIN_REFRESH_COOKIE,
    VOTER_ACCESS_COOKIE,
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
from app.repositories.admin_users import AdminUserRecord, AdminUserRepository

router = APIRouter(prefix="/auth", tags=["auth"])
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


@router.post("/voter/request-otp", response_model=OtpAcceptedResponse, status_code=202)
async def request_voter_otp(_: VoterOtpRequest, response: Response) -> OtpAcceptedResponse:
    """Return an anti-enumeration response while delivery is not configured."""
    response.headers["Cache-Control"] = "no-store"
    return OtpAcceptedResponse()


@router.post("/voter/verify-otp", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
async def verify_voter_otp(_: VoterOtpVerifyRequest) -> None:
    """Keep OTP verification disabled until a delivery provider is configured."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Voter OTP delivery is not configured",
    )
