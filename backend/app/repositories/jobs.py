"""Persistence for jobs and their steps."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class JobRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.jobs

    def create(self, values: dict) -> dict:
        now = utcnow()
        document = {
            "_id": uuid4().hex,
            "status": "queued",
            "payload": {},
            "steps": [],
            "error": None,
            "started_at": None,
            "finished_at": None,
            "created_at": now,
            "updated_at": now,
            **values,
        }
        self.collection.insert_one(document)
        return with_id(document)

    def find_for_company(self, job_id: str, company_id: str) -> dict | None:
        return with_id(
            self.collection.find_one({"_id": job_id, "company_id": company_id})
        )

    def list_for_company(
        self, company_id: str, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[dict], int]:
        query = {"company_id": company_id}
        total = self.collection.count_documents(query)
        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .skip(max(offset, 0))
            .limit(min(max(limit, 1), 100))
        )
        return [with_id(item) for item in cursor], total

    def next_queued(self) -> dict | None:
        return with_id(
            self.collection.find_one({"status": "queued"}, sort=[("created_at", 1)])
        )

    def update(self, job_id: str, changes: dict) -> dict | None:
        if changes:
            changes = {**changes, "updated_at": utcnow()}
            self.collection.update_one({"_id": job_id}, {"$set": changes})
        return with_id(self.collection.find_one({"_id": job_id}))

    def update_step(self, job_id: str, key: str, changes: dict) -> dict | None:
        job = with_id(self.collection.find_one({"_id": job_id}))
        if not job:
            return None
        steps = list(job.get("steps") or [])
        for index, step in enumerate(steps):
            if step.get("key") == key:
                steps[index] = {**step, **changes}
                break
        return self.update(job_id, {"steps": steps})

    def set_status(self, job_id: str, status: str, *, error: str | None = None) -> dict | None:
        changes: dict[str, Any] = {"status": status}
        if status == "running":
            changes["started_at"] = utcnow()
        if status in {"done", "failed"}:
            changes["finished_at"] = utcnow()
        if error is not None:
            changes["error"] = error
        return self.update(job_id, changes)
