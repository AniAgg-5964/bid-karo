from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database as PyMongoDatabase

from app.core.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Database:
    """Owns the MongoDB client and exposes typed collection access."""

    def __init__(self, uri: str, name: str, client: MongoClient | None = None) -> None:
        self.client = client or MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
        self.db: PyMongoDatabase = self.client[name]

    @property
    def users(self):
        return self.db["users"]

    @property
    def companies(self):
        return self.db["companies"]

    @property
    def company_documents(self):
        return self.db["company_documents"]

    @property
    def tenders(self):
        return self.db["tenders"]

    @property
    def requirements(self):
        return self.db["requirements"]

    @property
    def checklist_tasks(self):
        return self.db["checklist_tasks"]

    @property
    def changes(self):
        return self.db["changes"]

    @property
    def audit_logs(self):
        return self.db["audit_logs"]

    def ping(self) -> bool:
        self.client.admin.command("ping")
        return True

    def init_indexes(self) -> None:
        self.users.create_index([("email", ASCENDING)], unique=True, name="uq_users_email")
        self.users.create_index([("company_id", ASCENDING)], name="ix_users_company")

        self.companies.create_index([("name", ASCENDING)], name="ix_companies_name")

        self.company_documents.create_index(
            [("company_id", ASCENDING), ("created_at", DESCENDING)],
            name="ix_documents_company_created",
        )
        self.company_documents.create_index(
            [("company_id", ASCENDING), ("document_type", ASCENDING)],
            name="ix_documents_company_type",
        )
        self.company_documents.create_index(
            [("company_id", ASCENDING), ("expiry_date", ASCENDING)],
            name="ix_documents_company_expiry",
        )

        self.audit_logs.create_index(
            [("company_id", ASCENDING), ("created_at", DESCENDING)],
            name="ix_audit_company_created",
        )

        self.tenders.create_index(
            [("company_id", ASCENDING), ("created_at", DESCENDING)],
            name="ix_tenders_company_created",
        )
        self.checklist_tasks.create_index(
            [("company_id", ASCENDING), ("due_at", ASCENDING)],
            name="ix_tasks_company_due",
        )
        self.changes.create_index(
            [("company_id", ASCENDING), ("detected_at", DESCENDING)],
            name="ix_changes_company_detected",
        )

    def close(self) -> None:
        self.client.close()


_database: Database | None = None


def get_database() -> Database:
    global _database
    if _database is None:
        settings = get_settings()
        _database = Database(settings.mongodb_uri, settings.mongodb_db)
        _database.init_indexes()
    return _database


def set_database(database: Database | None) -> None:
    """Used by startup/shutdown and tests."""
    global _database
    _database = database


def to_dict(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    item = dict(document)
    item["id"] = item.pop("_id")
    return item
