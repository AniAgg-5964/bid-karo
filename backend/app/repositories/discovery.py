from __future__ import annotations

from datetime import date
from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class DiscoveryTenderRepository:
    """Store for tenders surfaced by web discovery, scoped per company.

    Records are deduplicated per company by a normalised key so the same tender
    seen in several runs updates in place instead of duplicating.
    """

    def __init__(self, db: Database) -> None:
        self.collection = db.discovered_tenders

    def upsert(self, company_id: str, dedupe_key: str, values: dict) -> tuple[dict, bool]:
        now = utcnow()
        existing = self.collection.find_one({"company_id": company_id, "dedupe_key": dedupe_key})
        if existing:
            update = dict(values)
            update["last_seen_at"] = now
            update["updated_at"] = now
            self.collection.update_one(
                {"_id": existing["_id"], "company_id": company_id},
                {"$set": update},
            )
            merged = self.collection.find_one({"_id": existing["_id"]})
            return with_id(merged), False

        document = {
            "_id": uuid4().hex,
            "company_id": company_id,
            "dedupe_key": dedupe_key,
            "status": values.get("status", "new"),
            "first_seen_at": now,
            "last_seen_at": now,
            "created_at": now,
            "updated_at": now,
            **values,
        }
        self.collection.insert_one(document)
        return with_id(document), True

    def ensure(self, company_id: str, dedupe_key: str, values: dict) -> tuple[dict, bool]:
        """Insert if absent, otherwise leave the stored record untouched.

        Used for candidates that were not fetched in the current run, so an
        earlier fetched copy keeps its content hash, excerpts and fetch status
        instead of being downgraded to "not_fetched".
        """
        existing = self.collection.find_one({"company_id": company_id, "dedupe_key": dedupe_key})
        if existing:
            return with_id(existing), False
        return self.upsert(company_id, dedupe_key, values)

    def list_for_company(
        self,
        company_id: str,
        *,
        min_score: float | None = None,
        statuses: list[str] | None = None,
        exclude_non_tender: bool = False,
        ready_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        query: dict = {"company_id": company_id}
        if min_score is not None:
            query["relevance.score"] = {"$gte": min_score}
        if statuses:
            query["status"] = {"$in": statuses}
        if exclude_non_tender:
            query["is_listing_page"] = {"$ne": True}
            query["is_award_notice"] = {"$ne": True}
        if ready_only:
            today = date.today().isoformat()
            query["$and"] = [
                {"extracted.deadline": {"$not": {"$lt": today}}},
                {
                    "$or": [
                        {"extracted.deadline": {"$ne": None}},
                        {"extracted.reference_number": {"$ne": None}},
                    ]
                },
            ]
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort([("relevance.score", -1), ("last_seen_at", -1)])
            .skip(max(offset, 0))
            .limit(min(max(limit, 1), 200))
        )
        return [with_id(item) for item in cursor], total

    def list_sources(self, company_id: str, *, limit: int = 8) -> list[dict]:
        """Index/portal pages, official first, used as follow-up sources."""
        query = {
            "company_id": company_id,
            "is_listing_page": True,
            "status": {"$ne": "dismissed"},
        }
        cursor = (
            self.collection.find(query)
            .sort([("relevance.score", -1), ("last_seen_at", -1)])
            .limit(min(max(limit * 4, limit), 80))
        )
        items = [with_id(item) for item in cursor]
        items.sort(
            key=lambda item: (
                item.get("source_type") == "official",
                (item.get("relevance") or {}).get("score", 0),
            ),
            reverse=True,
        )
        return items[:limit]

    def find_for_company(self, tender_id: str, company_id: str) -> dict | None:
        return with_id(self.collection.find_one({"_id": tender_id, "company_id": company_id}))

    def list_children(self, company_id: str, parent_url: str) -> list[dict]:
        cursor = self.collection.find(
            {
                "company_id": company_id,
                "parent_url": parent_url,
                "extracted_from": "listing_table",
            }
        )
        return [with_id(item) for item in cursor]

    def set_status(self, tender_id: str, company_id: str, status: str) -> dict | None:
        result = self.collection.update_one(
            {"_id": tender_id, "company_id": company_id},
            {"$set": {"status": status, "updated_at": utcnow()}},
        )
        if result.matched_count == 0:
            return None
        return with_id(self.collection.find_one({"_id": tender_id, "company_id": company_id}))

    def count_for_company(self, company_id: str, *, statuses: list[str] | None = None) -> int:
        query: dict = {"company_id": company_id}
        if statuses:
            query["status"] = {"$in": statuses}
        return self.collection.count_documents(query)


class DiscoveryRunRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.discovery_runs

    def create(self, company_id: str, queries: list[str]) -> dict:
        now = utcnow()
        document = {
            "_id": uuid4().hex,
            "company_id": company_id,
            "status": "running",
            "queries": queries,
            "stats": {},
            "error": None,
            "started_at": now,
            "finished_at": None,
            "created_at": now,
        }
        self.collection.insert_one(document)
        return with_id(document)

    def finish(self, run_id: str, company_id: str, *, status: str, stats: dict, error: str | None = None) -> dict | None:
        self.collection.update_one(
            {"_id": run_id, "company_id": company_id},
            {
                "$set": {
                    "status": status,
                    "stats": stats,
                    "error": error,
                    "finished_at": utcnow(),
                }
            },
        )
        return with_id(self.collection.find_one({"_id": run_id, "company_id": company_id}))

    def list_for_company(self, company_id: str, limit: int = 10, offset: int = 0) -> tuple[list[dict], int]:
        query = {"company_id": company_id}
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("started_at", -1)
            .skip(max(offset, 0))
            .limit(min(max(limit, 1), 50))
        )
        return [with_id(item) for item in cursor], total
