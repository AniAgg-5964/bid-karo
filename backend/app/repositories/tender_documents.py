from __future__ import annotations

from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class TenderDocumentRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.tender_documents

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

    def list_for_tender(self, company_id: str, tender_id: str) -> list[dict]:
        cursor = self.collection.find(
            {"company_id": company_id, "tender_id": tender_id}
        ).sort("created_at", 1)
        return [with_id(item) for item in cursor]

    def find_for_company(self, document_id: str, company_id: str) -> dict | None:
        return with_id(
            self.collection.find_one({"_id": document_id, "company_id": company_id})
        )

    def find_by_hash(self, company_id: str, tender_id: str, sha256: str) -> dict | None:
        return with_id(
            self.collection.find_one(
                {"company_id": company_id, "tender_id": tender_id, "sha256": sha256}
            )
        )

    def update(self, document_id: str, company_id: str, changes: dict) -> dict | None:
        if changes:
            changes = {**changes, "updated_at": utcnow()}
            self.collection.update_one(
                {"_id": document_id, "company_id": company_id}, {"$set": changes}
            )
        return self.find_for_company(document_id, company_id)

    def delete(self, document_id: str, company_id: str) -> bool:
        result = self.collection.delete_one({"_id": document_id, "company_id": company_id})
        return result.deleted_count == 1

    def count_for_tender(self, company_id: str, tender_id: str) -> int:
        return self.collection.count_documents(
            {"company_id": company_id, "tender_id": tender_id}
        )


class TenderPageRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.tender_pages

    def replace_for_document(
        self,
        *,
        company_id: str,
        tender_id: str,
        document_id: str,
        pages: list[dict],
    ) -> None:
        self.collection.delete_many({"document_id": document_id, "company_id": company_id})
        if not pages:
            return
        now = utcnow()
        payload = [
            {
                "_id": uuid4().hex,
                "company_id": company_id,
                "tender_id": tender_id,
                "document_id": document_id,
                "created_at": now,
                **page,
            }
            for page in pages
        ]
        self.collection.insert_many(payload)

    def list_for_document(self, document_id: str, company_id: str) -> list[dict]:
        cursor = self.collection.find(
            {"document_id": document_id, "company_id": company_id}
        ).sort("page_index", 1)
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
        result = self.collection.delete_many(
            {"document_id": document_id, "company_id": company_id}
        )
        return result.deleted_count


class RequirementRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.requirements

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

    def exists(self, document_id: str, page_index: int, excerpt_key: str) -> bool:
        return (
            self.collection.count_documents(
                {
                    "document_id": document_id,
                    "page_index": page_index,
                    "excerpt_key": excerpt_key,
                },
                limit=1,
            )
            > 0
        )

    def list_for_tender(
        self,
        company_id: str,
        tender_id: str,
        *,
        category: str | None = None,
        verification_status: str | None = None,
        mandatory: str | None = None,
        document_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        query: dict = {"company_id": company_id, "tender_id": tender_id}
        if category:
            query["category"] = category
        if verification_status:
            query["verification_status"] = verification_status
        if mandatory:
            query["mandatory"] = mandatory
        if document_id:
            query["document_id"] = document_id
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort([("page_index", 1), ("created_at", 1)])
            .skip(max(offset, 0))
            .limit(min(max(limit, 1), 300))
        )
        return [with_id(item) for item in cursor], total

    def find_for_company(self, requirement_id: str, company_id: str) -> dict | None:
        return with_id(
            self.collection.find_one({"_id": requirement_id, "company_id": company_id})
        )

    def update_review(self, requirement_id: str, company_id: str, changes: dict) -> dict | None:
        if changes:
            changes = {**changes, "updated_at": utcnow()}
            self.collection.update_one(
                {"_id": requirement_id, "company_id": company_id}, {"$set": changes}
            )
        return self.find_for_company(requirement_id, company_id)

    def delete_for_document(self, document_id: str, company_id: str) -> int:
        result = self.collection.delete_many(
            {"document_id": document_id, "company_id": company_id}
        )
        return result.deleted_count

    def delete_ai_for_document(self, document_id: str, company_id: str) -> int:
        result = self.collection.delete_many(
            {"document_id": document_id, "company_id": company_id, "origin": "ai"}
        )
        return result.deleted_count

    def backup_ai_for_document(self, document_id: str, company_id: str) -> list[dict]:
        cursor = self.collection.find(
            {"document_id": document_id, "company_id": company_id, "origin": "ai"}
        )
        return [dict(item) for item in cursor]

    def restore(self, documents: list[dict]) -> None:
        if documents:
            self.collection.insert_many(documents)

    def count_for_tender(self, company_id: str, tender_id: str) -> int:
        return self.collection.count_documents(
            {"company_id": company_id, "tender_id": tender_id}
        )

    def summary_for_tender(self, company_id: str, tender_id: str) -> dict[str, int]:
        base = {"company_id": company_id, "tender_id": tender_id}

        def count(extra: dict) -> int:
            return self.collection.count_documents({**base, **extra})

        return {
            "total": count({}),
            "verified": count({"verification_status": "verified"}),
            "unverified": count({"verification_status": "unverified"}),
        }
