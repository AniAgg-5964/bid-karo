from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database as PyMongoDatabase

from app.core.config import get_settings

_URI_CREDENTIALS = re.compile(r"(mongodb(?:\+srv)?://)([^@/]+)@")


def redact_mongodb_uri(uri: str) -> str:
    """Remove user:password from a MongoDB URI before it is logged or shown."""
    return _URI_CREDENTIALS.sub(r"\1***@", uri, count=1)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Database:
    """Owns the MongoDB client and exposes typed collection access."""

    def __init__(
        self,
        uri: str,
        name: str,
        client: MongoClient | None = None,
        *,
        app_name: str = "BidKaro",
        max_pool_size: int = 20,
        connect_timeout_ms: int = 10000,
        server_selection_timeout_ms: int = 10000,
        retry_writes: bool = True,
    ) -> None:
        self.uri = uri
        self.name = name
        self.client = client or MongoClient(
            uri,
            appname=app_name,
            maxPoolSize=max_pool_size,
            connectTimeoutMS=connect_timeout_ms,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
            retryWrites=retry_writes,
            tz_aware=True,
        )
        self.db: PyMongoDatabase = self.client[name]

    def describe_target(self) -> str:
        """Host and database name only, never credentials."""
        try:
            host = urlsplit(self.uri).hostname or "unknown-host"
        except ValueError:
            host = "unknown-host"
        return f"{host}/{self.name}"

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
    def tender_documents(self):
        return self.db["tender_documents"]

    @property
    def tender_pages(self):
        return self.db["tender_pages"]

    @property
    def checklist_tasks(self):
        return self.db["checklist_tasks"]

    @property
    def changes(self):
        return self.db["changes"]

    @property
    def audit_logs(self):
        return self.db["audit_logs"]

    @property
    def otp_codes(self):
        return self.db["otp_codes"]

    @property
    def evidence_matches(self):
        return self.db["evidence_matches"]

    @property
    def fit_assessments(self):
        return self.db["fit_assessments"]

    @property
    def discovered_tenders(self):
        return self.db["discovered_tenders"]

    @property
    def discovery_runs(self):
        return self.db["discovery_runs"]

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
        self.otp_codes.create_index(
            [("email", ASCENDING), ("purpose", ASCENDING), ("created_at", DESCENDING)],
            name="ix_otp_email_purpose_created",
        )
        self.otp_codes.create_index(
            [("expires_at", ASCENDING)],
            name="ttl_otp_expires",
            expireAfterSeconds=0,
        )

        self.tenders.create_index(
            [("company_id", ASCENDING), ("created_at", DESCENDING)],
            name="ix_tenders_company_created",
        )
        self.checklist_tasks.create_index(
            [("company_id", ASCENDING), ("due_at", ASCENDING)],
            name="ix_tasks_company_due",
        )
        self.checklist_tasks.create_index(
            [("company_id", ASCENDING), ("tender_id", ASCENDING), ("requirement_id", ASCENDING)],
            name="ix_tasks_company_tender_requirement",
        )
        self.evidence_matches.create_index(
            [("company_id", ASCENDING), ("requirement_id", ASCENDING)],
            unique=True,
            name="uq_evidence_company_requirement",
        )
        self.evidence_matches.create_index(
            [("company_id", ASCENDING), ("tender_id", ASCENDING)],
            name="ix_evidence_company_tender",
        )
        self.fit_assessments.create_index(
            [("company_id", ASCENDING), ("tender_id", ASCENDING)],
            unique=True,
            name="uq_fit_company_tender",
        )
        self.changes.create_index(
            [("company_id", ASCENDING), ("detected_at", DESCENDING)],
            name="ix_changes_company_detected",
        )

        self.discovered_tenders.create_index(
            [("company_id", ASCENDING), ("dedupe_key", ASCENDING)],
            unique=True,
            name="uq_discovered_company_dedupe",
        )
        self.discovered_tenders.create_index(
            [("company_id", ASCENDING), ("relevance.score", DESCENDING)],
            name="ix_discovered_company_score",
        )
        self.discovered_tenders.create_index(
            [("company_id", ASCENDING), ("last_seen_at", DESCENDING)],
            name="ix_discovered_company_seen",
        )
        self.discovery_runs.create_index(
            [("company_id", ASCENDING), ("started_at", DESCENDING)],
            name="ix_runs_company_started",
        )

        self.tender_documents.create_index(
            [("company_id", ASCENDING), ("tender_id", ASCENDING), ("created_at", ASCENDING)],
            name="ix_tender_docs_company_tender",
        )
        self.tender_documents.create_index(
            [("company_id", ASCENDING), ("tender_id", ASCENDING), ("sha256", ASCENDING)],
            unique=True,
            name="uq_tender_docs_company_tender_hash",
        )
        self.tender_pages.create_index(
            [("document_id", ASCENDING), ("page_index", ASCENDING)],
            unique=True,
            name="uq_tender_pages_document_page",
        )
        self.tender_pages.create_index(
            [("company_id", ASCENDING), ("tender_id", ASCENDING)],
            name="ix_tender_pages_company_tender",
        )
        self.requirements.create_index(
            [("company_id", ASCENDING), ("tender_id", ASCENDING), ("page_index", ASCENDING)],
            name="ix_requirements_company_tender_page",
        )
        self.requirements.create_index(
            [("company_id", ASCENDING), ("document_id", ASCENDING)],
            name="ix_requirements_company_document",
        )
        self.requirements.create_index(
            [("company_id", ASCENDING), ("verification_status", ASCENDING)],
            name="ix_requirements_company_verification",
        )

    def close(self) -> None:
        self.client.close()


_database: Database | None = None


def get_database() -> Database:
    global _database
    if _database is None:
        settings = get_settings()
        _database = Database(
            settings.mongodb_uri,
            settings.mongodb_db,
            app_name=settings.mongodb_app_name,
            max_pool_size=settings.mongodb_max_pool_size,
            connect_timeout_ms=settings.mongodb_connect_timeout_ms,
            server_selection_timeout_ms=settings.mongodb_server_selection_timeout_ms,
            retry_writes=settings.mongodb_retry_writes,
        )
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
