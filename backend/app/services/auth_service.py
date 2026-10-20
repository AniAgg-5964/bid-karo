from __future__ import annotations

import hashlib
import hmac
import math
import secrets
from datetime import timedelta

from app.core.config import get_settings
from app.core.database import Database, utcnow
from app.core.exceptions import AppError, ConflictError, NotConfiguredError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.auth import (
    AuthResponse,
    LoginRequest,
    OtpChallenge,
    OtpPurpose,
    OtpResendRequest,
    OtpVerifyRequest,
    RegisterRequest,
    SecuritySettingsRequest,
    SessionResponse,
    UserOut,
)
from app.repositories.audit import AuditRepository
from app.repositories.companies import CompanyRepository
from app.repositories.otp import OtpRepository
from app.repositories.users import UserRepository
from app.services.company_service import company_to_out
from app.services.email import EmailService


def _code_hash(email: str, purpose: str, code: str) -> str:
    secret = get_settings().jwt_secret.encode("utf-8")
    message = f"{email.lower().strip()}:{purpose}:{code}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


class OtpService:
    def __init__(self, db: Database, email: EmailService) -> None:
        self.settings = get_settings()
        self.repository = OtpRepository(db)
        self.email = email

    def _challenge(
        self, email: str, purpose: OtpPurpose, message: str, resend_after: int | None = None
    ) -> OtpChallenge:
        return OtpChallenge(
            purpose=purpose,
            email=email,
            message=message,
            expires_in_seconds=self.settings.otp_expire_minutes * 60,
            resend_after_seconds=(
                self.settings.otp_resend_cooldown_seconds
                if resend_after is None
                else max(resend_after, 0)
            ),
        )

    def ensure(self, *, email: str, purpose: OtpPurpose, user_id: str | None) -> OtpChallenge:
        """Return an existing unexpired challenge without sending another email."""
        active = self.repository.find_active(email, purpose, utcnow())
        if active:
            return self._challenge(
                email,
                purpose,
                "A code was already sent. Check your inbox, or resend it when the timer ends.",
            )
        return self.issue(email=email, purpose=purpose, user_id=user_id)

    def issue(
        self, *, email: str, purpose: OtpPurpose, user_id: str | None = None
    ) -> OtpChallenge:
        if not self.email.configured:
            raise NotConfiguredError(
                "Email sign-in is not configured. Set SMTP_USERNAME and SMTP_APP_PASSWORD "
                "on the server (use a Google App Password, not the Gmail password)."
            )

        now = utcnow()
        latest = self.repository.latest_any(email, purpose)
        if latest:
            elapsed = (now - latest["created_at"]).total_seconds()
            wait = math.ceil(self.settings.otp_resend_cooldown_seconds - elapsed)
            if wait > 0:
                raise AppError(429, f"Please wait {wait} seconds before requesting another code.")

        sent_last_hour = self.repository.count_since(
            email, purpose, now - timedelta(hours=1)
        )
        if sent_last_hour >= self.settings.otp_max_sends_per_hour:
            raise AppError(
                429,
                "Too many codes were requested for this email. Try again in an hour.",
            )

        code = f"{secrets.randbelow(900000) + 100000:06d}"
        otp = self.repository.create(
            email=email,
            purpose=purpose,
            code_hash=_code_hash(email, purpose, code),
            expires_at=now + timedelta(minutes=self.settings.otp_expire_minutes),
            user_id=user_id,
        )
        try:
            self.email.send_otp(
                to=email,
                code=code,
                purpose=purpose,
                expires_minutes=self.settings.otp_expire_minutes,
            )
        except Exception:
            # Never keep a code the user never received.
            self.repository.collection.delete_one({"_id": otp["id"]})
            raise

        return self._challenge(
            email,
            purpose,
            "We emailed a 6-digit code. It expires in 10 minutes.",
        )

    def verify(self, *, email: str, purpose: OtpPurpose, code: str) -> None:
        now = utcnow()
        active = self.repository.find_active(email, purpose, now)
        if not active:
            raise AppError(400, "This code has expired or was already used. Request a new one.")

        attempts = self.repository.increment_attempts(active["id"])
        if not hmac.compare_digest(active["code_hash"], _code_hash(email, purpose, code)):
            remaining = max(self.settings.otp_max_attempts - attempts, 0)
            if remaining == 0:
                self.repository.invalidate_active(email, purpose)
                raise AppError(429, "Too many incorrect attempts. Request a new code.")
            raise AppError(400, f"Incorrect code. {remaining} attempts left.")

        self.repository.consume(active["id"])


class AuthService:
    def __init__(self, db: Database, email: EmailService | None = None) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.companies = CompanyRepository(db)
        self.audit = AuditRepository(db)
        self.email = email or EmailService()
        self.otp = OtpService(db, self.email)

    def register(self, payload: RegisterRequest) -> OtpChallenge:
        if self.users.find_by_email(payload.email):
            raise ConflictError("An account with this email already exists.")
        if not self.email.configured:
            raise NotConfiguredError(
                "Email verification is not configured. Set SMTP_USERNAME and "
                "SMTP_APP_PASSWORD on the server first."
            )

        company = self.companies.create(name=payload.company_name)
        user = self.users.create(
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            company_id=company["id"],
            email_verified=False,
            otp_login_enabled=True,
        )
        try:
            challenge = self.otp.issue(
                email=user["email"], purpose="verify_email", user_id=user["id"]
            )
        except Exception:
            self.users.collection.delete_one({"_id": user["id"]})
            self.companies.delete(company["id"])
            raise

        self.audit.log(
            company_id=company["id"],
            actor_user_id=user["id"],
            action="auth.registered_unverified",
            entity_type="user",
            entity_id=user["id"],
            metadata={"company_name": company["name"]},
        )
        return challenge

    def login(self, payload: LoginRequest) -> AuthResponse | OtpChallenge:
        user = self.users.find_by_email(payload.email)
        if not user or not verify_password(payload.password, user["password_hash"]):
            raise AppError(401, "Incorrect email or password.")
        if not user.get("is_active"):
            raise AppError(403, "This account is inactive.")

        company = self.companies.find_by_id(user["company_id"])
        if not company:
            raise AppError(403, "Company account is unavailable.")

        if not user.get("email_verified", True):
            return self.otp.ensure(
                email=user["email"], purpose="verify_email", user_id=user["id"]
            )
        if user.get("otp_login_enabled", False):
            return self.otp.ensure(
                email=user["email"], purpose="login", user_id=user["id"]
            )
        return self._auth_response(user, company)

    def verify_otp(self, payload: OtpVerifyRequest) -> AuthResponse:
        user = self.users.find_by_email(payload.email)
        if not user or not user.get("is_active"):
            raise AppError(400, "Invalid or expired code.")

        if payload.purpose == "login":
            if not user.get("email_verified", True):
                raise AppError(403, "Verify your email address before signing in.")
            if not user.get("otp_login_enabled", False):
                raise AppError(403, "Email sign-in is not enabled for this account.")

        self.otp.verify(email=payload.email, purpose=payload.purpose, code=payload.code)

        if payload.purpose == "verify_email":
            self.users.mark_email_verified(user["id"])
            user = self.users.find_by_id(user["id"]) or user

        company = self.companies.find_by_id(user["company_id"])
        if not company:
            raise AppError(403, "Company account is unavailable.")

        self.audit.log(
            company_id=company["id"],
            actor_user_id=user["id"],
            action="auth.otp_verified",
            entity_type="user",
            entity_id=user["id"],
            metadata={"purpose": payload.purpose},
        )
        return self._auth_response(user, company)

    def resend(self, payload: OtpResendRequest) -> OtpChallenge:
        user = self.users.find_by_email(payload.email)
        can_send = bool(user) and user.get("is_active", False)
        if payload.purpose == "verify_email":
            can_send = can_send and not user.get("email_verified", True)
        else:
            can_send = (
                can_send
                and user.get("email_verified", True)
                and user.get("otp_login_enabled", False)
            )

        if not can_send:
            # Same shape and wording for unknown or ineligible accounts.
            return self.otp._challenge(
                payload.email,
                payload.purpose,
                "If this account can receive a code, it will arrive shortly.",
            )
        return self.otp.issue(
            email=user["email"], purpose=payload.purpose, user_id=user["id"]
        )

    def update_security(
        self, *, user: dict, payload: SecuritySettingsRequest
    ) -> UserOut:
        if not verify_password(payload.current_password, user["password_hash"]):
            raise AppError(401, "Current password is incorrect.")
        if payload.otp_login_enabled and not user.get("email_verified", True):
            raise AppError(422, "Verify your email address before enabling email sign-in.")

        self.users.set_otp_login_enabled(user["id"], payload.otp_login_enabled)
        self.audit.log(
            company_id=user["company_id"],
            actor_user_id=user["id"],
            action="auth.otp_login_changed",
            entity_type="user",
            entity_id=user["id"],
            metadata={"enabled": payload.otp_login_enabled},
        )
        updated = self.users.find_by_id(user["id"]) or user
        return UserOut.model_validate(updated)

    def session(self, user: dict, company: dict) -> SessionResponse:
        return SessionResponse(user=UserOut.model_validate(user), company=company_to_out(company))

    def _auth_response(self, user: dict, company: dict) -> AuthResponse:
        return AuthResponse(
            access_token=create_access_token(user["id"]),
            user=UserOut.model_validate(user),
            company=company_to_out(company),
        )
