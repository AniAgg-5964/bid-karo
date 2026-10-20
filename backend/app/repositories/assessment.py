from __future__ import annotations

from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class EvidenceRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.evidence_matches

    def find_for_requirement(self, requirement_id: str, company_id: str) -> dict | None:
        return with_id(
            self.collection.find_one(
                {"requirement_id": requirement_id, "company_id": company_id}
            )
        )

    def find_for_requirements(
        self, requirement_ids: list[str], company_id: str
    ) -> dict[str, dict]:
        if not requirement_ids:
            return {}
        cursor = self.collection.find(
            {"company_id": company_id, "requirement_id": {"$in": requirement_ids}}
        )
        return {item["requirement_id"]: with_id(item) for item in cursor}

    def upsert_decision(
        self,
        *,
        company_id: str,
        tender_id: str,
        requirement_id: str,
        document_id: str,
        status: str,
        note: str | None,
        user_id: str,
    ) -> dict:
        now = utcnow()
        existing = self.collection.find_one(
            {"company_id": company_id, "requirement_id": requirement_id}
        )
        if existing:
            self.collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "document_id": document_id,
                        "status": status,
                        "note": note,
                        "decided_by": user_id,
                        "updated_at": now,
                    }
                },
            )
            return with_id(
                self.collection.find_one(
                    {"company_id": company_id, "requirement_id": requirement_id}
                )
            )

        document = {
            "_id": uuid4().hex,
            "company_id": company_id,
            "tender_id": tender_id,
            "requirement_id": requirement_id,
            "document_id": document_id,
            "status": status,
            "note": note,
            "decided_by": user_id,
            "created_at": now,
            "updated_at": now,
        }
        self.collection.insert_one(document)
        return with_id(document)

    def delete_for_requirement(self, requirement_id: str, company_id: str) -> None:
        self.collection.delete_one(
            {"requirement_id": requirement_id, "company_id": company_id}
        )

    def delete_for_document(self, document_id: str, company_id: str) -> int:
        result = self.collection.delete_many(
            {"document_id": document_id, "company_id": company_id}
        )
        return result.deleted_count


class AssessmentRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.fit_assessments

    def save(self, *, company_id: str, tender_id: str, payload: dict) -> dict:
        now = utcnow()
        self.collection.update_one(
            {"company_id": company_id, "tender_id": tender_id},
            {
                "$set": {**payload, "company_id": company_id, "tender_id": tender_id, "generated_at": now},
                "$setOnInsert": {"_id": uuid4().hex, "created_at": now},
            },
            upsert=True,
        )
        return with_id(
            self.collection.find_one({"company_id": company_id, "tender_id": tender_id})
        )

    def find_for_tender(self, company_id: str, tender_id: str) -> dict | None:
        return with_id(
            self.collection.find_one({"company_id": company_id, "tender_id": tender_id})
        )
