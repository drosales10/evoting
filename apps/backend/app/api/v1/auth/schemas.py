from typing import Literal

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    organization_slug: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=256)


class AdminMfaEnrollRequest(AdminLoginRequest):
    pass


class AdminMfaVerifyRequest(AdminLoginRequest):
    code: str = Field(pattern=r"^\d{6}$")


class AdminMfaEnrollmentResponse(BaseModel):
    status: Literal["ENROLLED"]
    secret: str
    otpauth_uri: str


class AdminLoginResponse(BaseModel):
    status: Literal["AUTHENTICATED", "MFA_REQUIRED"]
    mfa_required: bool


class VoterOtpRequest(BaseModel):
    organization_slug: str = Field(min_length=2, max_length=100)
    identifier: str = Field(min_length=3, max_length=255)


class VoterOtpVerifyRequest(BaseModel):
    challenge_id: str = Field(min_length=36, max_length=36)
    code: str = Field(min_length=6, max_length=6)


class OtpAcceptedResponse(BaseModel):
    accepted: bool = True
    message: str = "If the voter is eligible, an OTP will be delivered."
    challenge_id: str | None = None


class VoterLoginResponse(BaseModel):
    status: Literal["AUTHENTICATED"]
    csrf_token: str


class AuthContractResponse(BaseModel):
    admin_login: str
    voter_request_otp: str
    voter_verify_otp: str
    note: str
