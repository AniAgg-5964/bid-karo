"""The memory of the official pages we have read.

A page that was read from an official source is kept, with the text as it was
read, the URL and the time it was read. The passages of the page are indexed
so it can be found again by meaning rather than by URL.

The record is the reason the memory is honest: a reading that is old can be
seen to be old, and a reading can always be checked against the page it came
from.
"""

from __future__ import annotations

from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class KnowledgeDocumentRepository:
    """The official pages and references we have read."""

    def __init__(self, db: Database) -> None:
        self.collection = db.knowledge_documents

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

    def find_for_company(self, document_id: str, company_id: str) -> dict | None:
        return with_id(
            self.collection.find_one({"_id": document_id, "company_id": company_id})
        )

    def find_by_url(self, company_id: str, url: str, scope: str) -> dict | None:
        return with_id(
            self.collection.find_one(
                {"company_id": company_id, "url": url, "scope": scope}
            )
        )

    def list_for_company(
        self, company_id: str, *, scope: str | None = None, limit: int = 200
    ) -> list[dict]:
        query: dict = {"company_id": company_id}
        if scope:
            query["scope"] = scope
        cursor = self.collection.find(query).sort("created_at", -1).limit(max(limit, 1))
        return [with_id(item) for item in cursor]

    def update(self, document_id: str, company_id: str, changes: dict) -> dict | None:
        if changes:
            changes = {**changes, "updated_at": utcnow()}
            self.collection.update_one(
                {"_id": document_id, "company_id": company_id}, {"$set": changes}
            )
        return self.find_for_company(document_id, company_id)

    def delete(self, document_id: str, company_id: str) -> bool:
        result = self.collection.delete_one(
            {"_id": document_id, "company_id": company_id}
        )
        return result.deleted_count == 1
