from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.database import Database
from app.core.exceptions import NotFoundError
from app.models.document import DocumentMetadata
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.services.storage import StorageService, sanitize_original_filename


class DocumentService:
    def __init__(self, db: Database, storage: StorageService) -> None:
        self.db = db
        self.storage = storage
        self.documents = DocumentRepository(db)
        self.audit = AuditRepository(db)

    def create(
        self,
        *,
        company_id: str,
        user_id: str,
        filename: str | None,
        content_type: str | None,
        content: bytes,
        metadata: DocumentMetadata,
    ) -> dict:
        suffix, mime_type = self.storage.validate(filename, content_type, content)
        original = sanitize_original_filename(filename)
        stored_filename, path = self.storage.save_company_document(company_id, suffix, content)

        try:
            document = self.documents.create(
                {
                    "company_id": company_id,
                    "original_filename": original,
                    "stored_filename": stored_filename,
                    "title": metadata.title,
                    "document_type": metadata.document_type,
                    "issuer": metadata.issuer,
                    "signatory": metadata.signatory,
                    "financial_year": metadata.financial_year,
                    "issue_date": metadata.issue_date,
                    "expiry_date": metadata.expiry_date,
                    "project_value": metadata.project_value,
                    "notes": metadata.notes,
                    "mime_type": mime_type,
                    "size_bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
        except Exception:
            if path.exists():
                path.unlink()
            raise

        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="document.uploaded",
            entity_type="company_document",
            entity_id=document["id"],
            metadata={"title": document["title"], "document_type": document["document_type"]},
        )
        return document

    def list(self, company_id: str, **filters) -> tuple[list[dict], int]:
        return self.documents.list_for_company(company_id, **filters)

    def get(self, document_id: str, company_id: str) -> dict:
        document = self.documents.find_for_company(document_id, company_id)
        if not document:
            raise NotFoundError("Document not found.")
        return document

    def path_for(self, document_id: str, company_id: str) -> tuple[dict, Path]:
        document = self.get(document_id, company_id)
        path = self.storage.resolve_company_document(company_id, document["stored_filename"])
        if not path.exists():
            raise NotFoundError("The stored file is unavailable.")
        return document, path

    def delete(self, document_id: str, company_id: str, user_id: str) -> None:
        document = self.get(document_id, company_id)
        # The indexed passages go with the document.
        from app.services.document_lifecycle import DocumentLifecycleService

        DocumentLifecycleService(self.db).remove_company_document(company_id, document_id)
        deleted = self.documents.delete_for_company(document_id, company_id)
        if not deleted:
            raise NotFoundError("Document not found.")
        self.storage.delete(company_id, document["stored_filename"])
        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="document.deleted",
            entity_type="company_document",
            entity_id=document_id,
            metadata={"title": document["title"]},
        )
