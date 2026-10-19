from __future__ import annotations

from app.core.database import Database
from app.core.exceptions import ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.auth import AuthResponse, LoginRequest, RegisterRequest, SessionResponse, UserOut
from app.repositories.audit import AuditRepository
from app.repositories.companies import CompanyRepository
from app.repositories.users import UserRepository
from app.services.company_service import company_to_out


class AuthService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.companies = CompanyRepository(db)
        self.audit = AuditRepository(db)

    def register(self, payload: RegisterRequest) -> AuthResponse:
        if self.users.find_by_email(payload.email):
            raise ConflictError("An account with this email already exists.")

        company = self.companies.create(name=payload.company_name)
        user = self.users.create(
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            company_id=company["id"],
        )
        self.audit.log(
            company_id=company["id"],
            actor_user_id=user["id"],
            action="auth.registered",
            entity_type="user",
            entity_id=user["id"],
            metadata={"company_name": company["name"]},
        )
        return self._auth_response(user, company)

    def login(self, payload: LoginRequest) -> AuthResponse:
        user = self.users.find_by_email(payload.email)
        if not user or not verify_password(payload.password, user["password_hash"]):
            from app.core.exceptions import AppError

            raise AppError(401, "Incorrect email or password.")
        if not user.get("is_active"):
            from app.core.exceptions import AppError

            raise AppError(403, "This account is inactive.")

        company = self.companies.find_by_id(user["company_id"])
        if not company:
            from app.core.exceptions import AppError

            raise AppError(403, "Company account is unavailable.")
        return self._auth_response(user, company)

    def session(self, user: dict, company: dict) -> SessionResponse:
        return SessionResponse(user=UserOut.model_validate(user), company=company_to_out(company))

    def _auth_response(self, user: dict, company: dict) -> AuthResponse:
        return AuthResponse(
            access_token=create_access_token(user["id"]),
            user=UserOut.model_validate(user),
            company=company_to_out(company),
        )
