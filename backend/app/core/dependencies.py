from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import get_settings
from app.core.database import Database, get_database
from app.core.security import TokenError, decode_access_token
from app.repositories.users import UserRepository
from app.repositories.companies import CompanyRepository
from app.services.storage import StorageService

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")


@lru_cache
def get_storage() -> StorageService:
    current = get_settings()
    return StorageService(current.storage_dir, current.max_upload_mb)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Database = Depends(get_database),
) -> dict:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_access_token(token)
    except TokenError as exc:
        raise credentials_error from exc

    user = UserRepository(db).find_by_id(user_id)
    if not user or not user.get("is_active", False):
        raise credentials_error
    return user


def get_current_company(
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_database),
) -> dict:
    company = CompanyRepository(db).find_by_id(user["company_id"])
    if not company:
        raise HTTPException(status_code=403, detail="Company account is unavailable.")
    return company
