from fastapi import APIRouter, HTTPException, Response, status

from app.api.v1.auth.schemas import (
    AuthContractResponse,
    OtpAcceptedResponse,
    VoterOtpRequest,
    VoterOtpVerifyRequest,
)
from app.auth.realms import ADMIN_ACCESS_COOKIE, VOTER_ACCESS_COOKIE

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/contract", response_model=AuthContractResponse)
async def auth_contract() -> AuthContractResponse:
    """Expose the versioned auth surface without exposing session state."""
    return AuthContractResponse(
        admin_login="/api/v1/auth/admin/login",
        voter_request_otp="/api/v1/auth/voter/request-otp",
        voter_verify_otp="/api/v1/auth/voter/verify-otp",
        note=(
            f"ADMIN and VOTER use separate HttpOnly cookies: {ADMIN_ACCESS_COOKIE} and "
            f"{VOTER_ACCESS_COOKIE}. The persistence migration is pending."
        ),
    )


@router.post("/admin/login", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
async def admin_login_unavailable() -> None:
    """Keep the route explicit until the auth persistence migration is activated."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Admin authentication store is not initialized",
    )


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
