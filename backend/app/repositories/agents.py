"""Storage for agent proposals and for the official sources they read."""

from __future__ import annotations

from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class RecommendationRepository:
    """Recommendations proposed by an agent, with the gate's verdict."""

    def __init__(self, db: Database) -> None:
        self.collection = db.recommendations

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

    def replace_for_tender(
        self,
        company_id: str,
        tender_id: str,
        values: list[dict],
        *,
        origin: str,
    ) -> list[dict]:
        """Replace the proposals of one origin for a tender.

        The origin keeps the steps apart: the recommendations and the
        verification notes live in the same collection, and a re-run of one must
        not delete the other.
        """
        self.collection.delete_many(
            {"company_id": company_id, "tender_id": tender_id, "origin": origin}
        )
        return [self.create({**value, "origin": origin}) for value in values]

    def list_for_tender(
        self, company_id: str, tender_id: str, *, kind: str | None = None
    ) -> list[dict]:
        query: dict = {"company_id": company_id, "tender_id": tender_id}
        if kind:
            query["kind"] = kind
        cursor = self.collection.find(query).sort("created_at", 1)
        return [with_id(item) for item in cursor]

    def find_for_company(self, recommendation_id: str, company_id: str) -> dict | None:
        return with_id(
            self.collection.find_one({"_id": recommendation_id, "company_id": company_id})
        )

    def update(self, recommendation_id: str, company_id: str, changes: dict) -> dict | None:
        if changes:
            changes = {**changes, "updated_at": utcnow()}
            self.collection.update_one(
                {"_id": recommendation_id, "company_id": company_id}, {"$set": changes}
            )
        return self.find_for_company(recommendation_id, company_id)


class LegalSourceRepository:
    """Clauses read from official sources, quoted and dated."""

    def __init__(self, db: Database) -> None:
        self.collection = db.legal_sources

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

    def replace_for_requirement(
        self, company_id: str, tender_id: str, requirement_id: str, values: list[dict]
    ) -> list[dict]:
        self.collection.delete_many(
            {
                "company_id": company_id,
                "tender_id": tender_id,
                "requirement_id": requirement_id,
            }
        )
        return [self.create(value) for value in values]

    def list_for_tender(
        self, company_id: str, tender_id: str, *, requirement_id: str | None = None
    ) -> list[dict]:
        query: dict = {"company_id": company_id, "tender_id": tender_id}
        if requirement_id:
            query["requirement_id"] = requirement_id
        cursor = self.collection.find(query).sort("created_at", 1)
        return [with_id(item) for item in cursor]
