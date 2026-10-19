from __future__ import annotations

from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class AuditRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.audit_logs

    def log(
        self,
        *,
        company_id: str,
        actor_user_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict | None = None,
    ) -> dict:
        document = {
            "_id": uuid4().hex,
            "company_id": company_id,
            "actor_user_id": actor_user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "metadata": metadata or {},
            "created_at": utcnow(),
        }
        self.collection.insert_one(document)
        return with_id(document)

    def recent_for_company(self, company_id: str, limit: int = 8) -> list[dict]:
        cursor = (
            self.collection.find({"company_id": company_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [with_id(item) for item in cursor]
