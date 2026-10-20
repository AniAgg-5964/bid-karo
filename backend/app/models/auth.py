from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

OtpPurpose = Literal["verify_email", "login"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    company_name: str = Field(min_length=2, max_length=200)

    @field_validator("password")
    @classmethod
    def password_is_usable(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes.")
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("Password must include at least one letter and one number.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    email: EmailStr
    full_name: str
    company_id: str
    role: str
    is_active: bool
    # Older accounts predate email verification and are treated as verified;
    # new accounts always store an explicit flag.
    email_verified: bool = True
    otp_login_enabled: bool = False
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    company: "CompanyOut"


class SessionResponse(BaseModel):
    user: UserOut
    company: "CompanyOut"


class OtpChallenge(BaseModel):
    otp_required: bool = True
    purpose: OtpPurpose
    email: EmailStr
    message: str
    expires_in_seconds: int
    resend_after_seconds: int


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    purpose: OtpPurpose = "login"


class OtpResendRequest(BaseModel):
    email: EmailStr
    purpose: OtpPurpose = "login"


class SecuritySettingsRequest(BaseModel):
    otp_login_enabled: bool
    current_password: str = Field(min_length=1, max_length=128)


from app.models.company import CompanyOut  # noqa: E402  (resolves forward reference)

AuthResponse.model_rebuild()
SessionResponse.model_rebuild()
