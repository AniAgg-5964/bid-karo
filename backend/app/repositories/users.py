from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class UserRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.users

    def create(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        company_id: str,
        role: str = "owner",
        email_verified: bool = False,
        otp_login_enabled: bool = True,
    ) -> dict:
        now = utcnow()
        document = {
            "_id": uuid4().hex,
            "email": email.lower().strip(),
            "password_hash": password_hash,
            "full_name": full_name.strip(),
            "company_id": company_id,
            "role": role,
            "is_active": True,
            "email_verified": email_verified,
            "otp_login_enabled": otp_login_enabled,
            "created_at": now,
            "updated_at": now,
        }
        self.collection.insert_one(document)
        return with_id(document)

    def find_by_email(self, email: str) -> dict | None:
        return with_id(self.collection.find_one({"email": email.lower().strip()}))

    def find_by_id(self, user_id: str) -> dict | None:
        return with_id(self.collection.find_one({"_id": user_id}))

    def mark_email_verified(self, user_id: str) -> None:
        self.collection.update_one(
            {"_id": user_id},
            {"$set": {"email_verified": True, "updated_at": utcnow()}},
        )

    def set_otp_login_enabled(self, user_id: str, enabled: bool) -> None:
        self.collection.update_one(
            {"_id": user_id},
            {"$set": {"otp_login_enabled": enabled, "updated_at": utcnow()}},
        )

    def count_for_company(self, company_id: str) -> int:
        return self.collection.count_documents({"company_id": company_id})

    def list_for_company(self, company_id: str) -> list[dict]:
        cursor = self.collection.find(
            {"company_id": company_id, "is_active": True}
        ).sort("created_at", 1)
        return [with_id(item) for item in cursor]
