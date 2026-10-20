from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pymongo import ReturnDocument

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class SnapshotRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.tender_snapshots

    def create(self, values: dict) -> dict:
        now = utcnow()
        document = {
            "_id": uuid4().hex,
            "created_at": now,
            **values,
        }
        self.collection.insert_one(document)
        return with_id(document)

    def latest(self, company_id: str, tender_id: str) -> dict | None:
        return with_id(
            self.collection.find_one(
                {"company_id": company_id, "tender_id": tender_id},
                sort=[("captured_at", -1)],
            )
        )

    def list_for_tender(
        self, company_id: str, tender_id: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[dict], int]:
        query = {"company_id": company_id, "tender_id": tender_id}
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("captured_at", -1)
            .skip(max(offset, 0))
            .limit(min(max(limit, 1), 100))
        )
        return [with_id(item) for item in cursor], total

    def find(self, snapshot_id: str, company_id: str) -> dict | None:
        return with_id(
            self.collection.find_one({"_id": snapshot_id, "company_id": company_id})
        )


class ChangeRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.changes

    def create_many(self, values: list[dict]) -> list[dict]:
        if not values:
            return []
        now = utcnow()
        documents = [
            {
                "_id": uuid4().hex,
                "created_at": now,
                **item,
            }
            for item in values
        ]
        self.collection.insert_many(documents)
        return [with_id(item) for item in documents]

    def list_for_company(
        self,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
        *,
        tender_id: str | None = None,
        review_status: str | None = None,
    ) -> tuple[list[dict], int]:
        query: dict = {"company_id": company_id}
        if tender_id:
            query["tender_id"] = tender_id
        if review_status:
            query["review_status"] = review_status
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("detected_at", -1)
            .skip(max(offset, 0))
            .limit(min(max(limit, 1), 200))
        )
        return [with_id(item) for item in cursor], total

    def find(self, change_id: str, company_id: str) -> dict | None:
        return with_id(
            self.collection.find_one({"_id": change_id, "company_id": company_id})
        )

    def update_review(
        self, change_id: str, company_id: str, review_status: str
    ) -> dict | None:
        now = utcnow()
        self.collection.update_one(
            {"_id": change_id, "company_id": company_id},
            {"$set": {"review_status": review_status, "reviewed_at": now, "updated_at": now}},
        )
        return self.find(change_id, company_id)

    def count_pending(self, company_id: str) -> int:
        return self.collection.count_documents(
            {"company_id": company_id, "review_status": "pending"}
        )


class ReminderRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.reminders

    def find_by_key(self, company_id: str, reminder_key: str) -> dict | None:
        return with_id(
            self.collection.find_one(
                {"company_id": company_id, "reminder_key": reminder_key}
            )
        )

    def upsert_generated(self, values: dict) -> dict:
        now = utcnow()
        existing = self.find_by_key(values["company_id"], values["reminder_key"])
        if existing:
            update = {
                key: value
                for key, value in values.items()
                if key not in {"status", "created_at", "sent_at"}
            }
            update["active"] = True
            update["updated_at"] = now
            # A changed deadline or task due date must re-open a reminder even if
            # the previous one was acknowledged, dismissed or already emailed.
            due_changed = existing.get("due_at") != values.get("due_at")
            if existing.get("status") == "cancelled" or due_changed:
                update["status"] = "pending"
                update["sent_at"] = None
                update["last_error"] = None
                update["attempts"] = 0
            self.collection.update_one({"_id": existing["id"]}, {"$set": update})
            return self.find_by_key(values["company_id"], values["reminder_key"]) or existing

        document = {
            "_id": uuid4().hex,
            "status": "pending",
            "active": True,
            "attempts": 0,
            "sent_at": None,
            "last_attempt_at": None,
            "last_error": None,
            "created_at": now,
            "updated_at": now,
            **values,
        }
        self.collection.insert_one(document)
        return with_id(document)

    def mark_inactive_except(self, company_id: str, reminder_keys: set[str]) -> int:
        query: dict = {"company_id": company_id, "active": True}
        if reminder_keys:
            query["reminder_key"] = {"$nin": sorted(reminder_keys)}
        result = self.collection.update_many(
            query,
            {
                "$set": {
                    "active": False,
                    "status": "cancelled",
                    "updated_at": utcnow(),
                }
            },
        )
        return result.modified_count

    def list_for_company(
        self,
        company_id: str,
        limit: int = 100,
        offset: int = 0,
        *,
        status: str | None = None,
    ) -> tuple[list[dict], int]:
        query: dict = {"company_id": company_id, "active": True}
        if status:
            query["status"] = status
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("due_at", 1)
            .skip(max(offset, 0))
            .limit(min(max(limit, 1), 500))
        )
        return [with_id(item) for item in cursor], total

    def find(self, reminder_id: str, company_id: str) -> dict | None:
        return with_id(
            self.collection.find_one({"_id": reminder_id, "company_id": company_id})
        )

    def update_status(
        self, reminder_id: str, company_id: str, status: str
    ) -> dict | None:
        now = utcnow()
        self.collection.update_one(
            {"_id": reminder_id, "company_id": company_id, "active": True},
            {"$set": {"status": status, "updated_at": now}},
        )
        return self.find(reminder_id, company_id)

    def list_due_for_company(
        self, company_id: str, now: datetime, limit: int = 100
    ) -> list[dict]:
        cursor = (
            self.collection.find(
                {
                    "company_id": company_id,
                    "active": True,
                    "status": "pending",
                    "sent_at": None,
                    "due_at": {"$lte": now},
                }
            )
            .sort("due_at", 1)
            .limit(min(max(limit, 1), 500))
        )
        return [with_id(item) for item in cursor]

    def claim_due_for_company(
        self, company_id: str, now: datetime
    ) -> dict | None:
        return with_id(
            self.collection.find_one_and_update(
                {
                    "company_id": company_id,
                    "active": True,
                    "status": "pending",
                    "sent_at": None,
                    "due_at": {"$lte": now},
                },
                {
                    "$set": {"last_attempt_at": now, "updated_at": now},
                    "$inc": {"attempts": 1},
                },
                sort=[("due_at", 1)],
                return_document=ReturnDocument.AFTER,
            )
        )

    def mark_sent(self, reminder_id: str, company_id: str, now: datetime) -> None:
        self.collection.update_one(
            {"_id": reminder_id, "company_id": company_id},
            {
                "$set": {
                    "status": "sent",
                    "sent_at": now,
                    "last_error": None,
                    "updated_at": now,
                }
            },
        )

    def mark_failed(self, reminder_id: str, company_id: str, error: str, now: datetime) -> None:
        self.collection.update_one(
            {"_id": reminder_id, "company_id": company_id},
            {
                "$set": {
                    "status": "pending",
                    "last_error": error[:500],
                    "updated_at": now,
                }
            },
        )

    def count_pending(self, company_id: str) -> int:
        return self.collection.count_documents(
            {"company_id": company_id, "active": True, "status": "pending"}
        )
