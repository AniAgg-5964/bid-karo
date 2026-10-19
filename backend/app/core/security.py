from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import get_settings


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {"sub": user_id, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise TokenError("Invalid or expired token.") from exc
    user_id = payload.get("sub")
    if not user_id or not isinstance(user_id, str):
        raise TokenError("Token is missing a subject.")
    return user_id
