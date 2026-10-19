from __future__ import annotations

from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class TenderRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.tenders

    def create(self, values: dict) -> dict:
        now = utcnow()
        document = {
            "_id": uuid4().hex,
            "created_at": now,
            "updated_at": now,
            **values,
        }
        self.collection.insert_one(document)
        return with_id(document)

    def find_by_discovered(self, discovered_id: str, company_id: str) -> dict | None:
        return with_id(
            self.collection.find_one({"company_id": company_id, "discovered_tender_id": discovered_id})
        )

    def list_for_company(self, company_id: str, limit: int = 10, offset: int = 0) -> tuple[list[dict], int]:
        query = {"company_id": company_id}
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .skip(max(offset, 0))
            .limit(min(max(limit, 1), 100))
        )
        return [with_id(item) for item in cursor], total

    def find_for_company(self, tender_id: str, company_id: str) -> dict | None:
        return with_id(self.collection.find_one({"_id": tender_id, "company_id": company_id}))

    def count_active(self, company_id: str) -> int:
        return self.collection.count_documents(
            {"company_id": company_id, "status": {"$in": ["saved", "preparing", "submitted"]}}
        )

    def count_upcoming(self, company_id: str, start, end) -> int:
        return self.collection.count_documents(
            {
                "company_id": company_id,
                "status": {"$in": ["saved", "preparing", "submitted"]},
                "deadline": {"$gte": start, "$lte": end},
            }
        )

    def upcoming_for_company(self, company_id: str, start, end, limit: int = 5) -> list[dict]:
        cursor = (
            self.collection.find(
                {
                    "company_id": company_id,
                    "status": {"$in": ["saved", "preparing", "submitted"]},
                    "deadline": {"$gte": start, "$lte": end},
                }
            )
            .sort("deadline", 1)
            .limit(max(limit, 1))
        )
        return [with_id(item) for item in cursor]


class ChecklistRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.checklist_tasks

    def list_for_company(self, company_id: str, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        query = {"company_id": company_id}
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("due_at", 1)
            .skip(max(offset, 0))
            .limit(min(max(limit, 1), 500))
        )
        return [with_id(item) for item in cursor], total

    def count_open(self, company_id: str) -> int:
        return self.collection.count_documents(
            {"company_id": company_id, "status": {"$in": ["missing", "incomplete", "needs_verification", "in_progress"]}}
        )

    def upcoming_for_company(self, company_id: str, start, end, limit: int = 5) -> list[dict]:
        cursor = (
            self.collection.find(
                {
                    "company_id": company_id,
                    "due_at": {"$gte": start, "$lte": end},
                    "status": {"$nin": ["complete", "not_applicable"]},
                }
            )
            .sort("due_at", 1)
            .limit(limit)
        )
        return [with_id(item) for item in cursor]

    def count_upcoming(self, company_id: str, start, end) -> int:
        return self.collection.count_documents(
            {
                "company_id": company_id,
                "due_at": {"$gte": start, "$lte": end},
                "status": {"$nin": ["complete", "not_applicable"]},
            }
        )


class ChangeRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.changes

    def list_for_company(self, company_id: str, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
        query = {"company_id": company_id}
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("detected_at", -1)
            .skip(max(offset, 0))
            .limit(min(max(limit, 1), 200))
        )
        return [with_id(item) for item in cursor], total

    def count_pending(self, company_id: str) -> int:
        return self.collection.count_documents(
            {"company_id": company_id, "review_status": {"$in": ["pending", "needs_review"]}}
        )
