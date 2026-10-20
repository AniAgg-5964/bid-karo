from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class OtpRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.otp_codes

    def create(
        self,
        *,
        email: str,
        purpose: str,
        code_hash: str,
        expires_at: datetime,
        user_id: str | None = None,
    ) -> dict:
        now = utcnow()
        document = {
            "_id": uuid4().hex,
            "email": email.lower().strip(),
            "purpose": purpose,
            "user_id": user_id,
            "code_hash": code_hash,
            "attempts": 0,
            "consumed_at": None,
            "expires_at": expires_at,
            "created_at": now,
        }
        self.collection.insert_one(document)
        return with_id(document)

    def latest_any(self, email: str, purpose: str) -> dict | None:
        return with_id(
            self.collection.find_one(
                {"email": email.lower().strip(), "purpose": purpose},
                sort=[("created_at", -1)],
            )
        )

    def find_active(self, email: str, purpose: str, now: datetime) -> dict | None:
        return with_id(
            self.collection.find_one(
                {
                    "email": email.lower().strip(),
                    "purpose": purpose,
                    "consumed_at": None,
                    "expires_at": {"$gt": now},
                },
                sort=[("created_at", -1)],
            )
        )

    def count_since(self, email: str, purpose: str, since: datetime) -> int:
        return self.collection.count_documents(
            {
                "email": email.lower().strip(),
                "purpose": purpose,
                "created_at": {"$gte": since},
            }
        )

    def increment_attempts(self, otp_id: str) -> int:
        result = self.collection.find_one_and_update(
            {"_id": otp_id},
            {"$inc": {"attempts": 1}},
            return_document=True,
        )
        return int((result or {}).get("attempts", 0))

    def consume(self, otp_id: str) -> None:
        self.collection.update_one({"_id": otp_id}, {"$set": {"consumed_at": utcnow()}})

    def invalidate_active(self, email: str, purpose: str) -> None:
        self.collection.update_many(
            {
                "email": email.lower().strip(),
                "purpose": purpose,
                "consumed_at": None,
            },
            {"$set": {"consumed_at": utcnow()}},
        )

    def delete_for_email(self, email: str) -> None:
        self.collection.delete_many({"email": email.lower().strip()})
