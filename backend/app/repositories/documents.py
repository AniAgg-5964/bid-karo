from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


def normalize_bson_dates(changes: dict) -> dict:
    """MongoDB stores dates as datetimes; keep the public contract as date."""
    for field in ("issue_date", "expiry_date"):
        value = changes.get(field)
        if isinstance(value, date) and not isinstance(value, datetime):
            changes[field] = datetime.combine(value, time.min, tzinfo=timezone.utc)
    return changes


class DocumentRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.company_documents

    def create(self, document: dict) -> dict:
        now = utcnow()
        payload = normalize_bson_dates(
            {
                "_id": uuid4().hex,
                **document,
                "verification_status": document.get("verification_status", "self_declared"),
                "created_at": now,
                "updated_at": now,
            }
        )
        self.collection.insert_one(payload)
        return with_id(payload)

    def list_for_company(
        self,
        company_id: str,
        *,
        document_type: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        query: dict = {"company_id": company_id}
        if document_type:
            query["document_type"] = document_type
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"original_filename": {"$regex": search, "$options": "i"}},
                {"issuer": {"$regex": search, "$options": "i"}},
            ]
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .skip(max(offset, 0))
            .limit(min(max(limit, 1), 200))
        )
        return [with_id(item) for item in cursor], total

    def find_for_company(self, document_id: str, company_id: str) -> dict | None:
        return with_id(self.collection.find_one({"_id": document_id, "company_id": company_id}))

    def update_for_company(self, document_id: str, company_id: str, changes: dict) -> dict | None:
        if changes:
            changes = normalize_bson_dates(changes)
            changes["updated_at"] = utcnow()
            self.collection.update_one(
                {"_id": document_id, "company_id": company_id}, {"$set": changes}
            )
        return self.find_for_company(document_id, company_id)

    def delete_for_company(self, document_id: str, company_id: str) -> bool:
        result = self.collection.delete_one({"_id": document_id, "company_id": company_id})
        return result.deleted_count == 1

    def count_for_company(self, company_id: str) -> int:
        return self.collection.count_documents({"company_id": company_id})

    def expiring_for_company(self, company_id: str, before: date) -> list[dict]:
        before_dt = datetime.combine(before, time.max, tzinfo=timezone.utc)
        cursor = self.collection.find(
            {
                "company_id": company_id,
                "expiry_date": {"$ne": None, "$lte": before_dt},
            }
        ).sort("expiry_date", 1)
        return [with_id(item) for item in cursor]


class CompanyPageRepository:
    """The extracted pages of a company document."""

    def __init__(self, db: Database) -> None:
        self.collection = db.company_pages

    def replace_for_document(
        self, *, company_id: str, document_id: str, pages: list[dict]
    ) -> None:
        self.collection.delete_many({"document_id": document_id, "company_id": company_id})
        if not pages:
            return
        now = utcnow()
        payload = [
            {
                "_id": uuid4().hex,
                "company_id": company_id,
                "document_id": document_id,
                "created_at": now,
                **page,
            }
            for page in pages
        ]
        self.collection.insert_many(payload)

    def list_for_document(self, document_id: str, company_id: str) -> list[dict]:
        cursor = self.collection.find({"document_id": document_id, "company_id": company_id}).sort(
            "page_index", 1
        )
        return [with_id(item) for item in cursor]

    def find_page(self, document_id: str, company_id: str, page_index: int) -> dict | None:
        return with_id(
            self.collection.find_one(
                {
                    "document_id": document_id,
                    "company_id": company_id,
                    "page_index": page_index,
                }
            )
        )

    def delete_for_document(self, document_id: str, company_id: str) -> int:
        result = self.collection.delete_many({"document_id": document_id, "company_id": company_id})
        return result.deleted_count
