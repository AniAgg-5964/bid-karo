from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company, get_current_user
from app.models.auth import AuthResponse, LoginRequest, RegisterRequest, SessionResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Database = Depends(get_database)) -> AuthResponse:
    return AuthService(db).register(payload)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Database = Depends(get_database)) -> AuthResponse:
    return AuthService(db).login(payload)


@router.get("/me", response_model=SessionResponse)
def me(
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> SessionResponse:
    return AuthService(db).session(user, company)
