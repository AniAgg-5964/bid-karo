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
            "created_at": now,
            "updated_at": now,
        }
        self.collection.insert_one(document)
        return with_id(document)

    def find_by_email(self, email: str) -> dict | None:
        return with_id(self.collection.find_one({"email": email.lower().strip()}))

    def find_by_id(self, user_id: str) -> dict | None:
        return with_id(self.collection.find_one({"_id": user_id}))

    def count_for_company(self, company_id: str) -> int:
        return self.collection.count_documents({"company_id": company_id})
