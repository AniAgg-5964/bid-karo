from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company, get_current_user, get_email_service
from app.models.auth import (
    AuthResponse,
    LoginRequest,
    OtpChallenge,
    OtpResendRequest,
    OtpVerifyRequest,
    RegisterRequest,
    SecuritySettingsRequest,
    SessionResponse,
    UserOut,
)
from app.services.auth_service import AuthService
from app.services.email import EmailService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=OtpChallenge, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Database = Depends(get_database),
    email: EmailService = Depends(get_email_service),
) -> OtpChallenge:
    return AuthService(db, email=email).register(payload)


@router.post("/login", response_model=AuthResponse | OtpChallenge)
def login(
    payload: LoginRequest,
    db: Database = Depends(get_database),
    email: EmailService = Depends(get_email_service),
) -> AuthResponse | OtpChallenge:
    return AuthService(db, email=email).login(payload)


@router.post("/verify-otp", response_model=AuthResponse)
def verify_otp(
    payload: OtpVerifyRequest,
    db: Database = Depends(get_database),
    email: EmailService = Depends(get_email_service),
) -> AuthResponse:
    return AuthService(db, email=email).verify_otp(payload)


@router.post("/resend-otp", response_model=OtpChallenge)
def resend_otp(
    payload: OtpResendRequest,
    db: Database = Depends(get_database),
    email: EmailService = Depends(get_email_service),
) -> OtpChallenge:
    return AuthService(db, email=email).resend(payload)


@router.post("/security", response_model=UserOut)
def update_security(
    payload: SecuritySettingsRequest,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_database),
    email: EmailService = Depends(get_email_service),
) -> UserOut:
    return AuthService(db, email=email).update_security(user=user, payload=payload)


@router.get("/me", response_model=SessionResponse)
def me(
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> SessionResponse:
    return AuthService(db).session(user, company)
