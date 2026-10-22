"""The life of a document in the retrieval index.

The index follows the document. When a document is deleted its passages go
with it. When a new version arrives it is indexed next to the old one, and the
old one keeps its own history. When the embedding model changes, the passages
are marked as needing a rebuild instead of quietly answering with vectors that
no longer match the model.

The rules:

* **A deleted document leaves nothing behind.** The passages and the cached
  pages are removed. If the store cannot be reached, the removal is recorded
  and can be run again; the document itself is never silently left indexed.
* **Historical evidence is not destroyed.** A corrected tender file is a new
  document, and the old one stays where it was, marked as it is.
* **A model change is visible.** The documents say that they need a rebuild
  rather than pretending their passages are current.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings, get_settings
from app.core.database import Database
from app.repositories.documents import CompanyPageRepository, DocumentRepository
from app.repositories.tender_documents import TenderDocumentRepository, TenderPageRepository
from app.services.vector_store import (
    QdrantVectorStore,
    VectorStoreError,
    VectorStoreUnavailable,
)

logger = logging.getLogger(__name__)


class DocumentLifecycleService:
    """Keeps the index and the documents in step."""

    def __init__(
        self,
        db: Database,
        store: QdrantVectorStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        if store is None:
            from app.services.vector_store import build_vector_store

            store = build_vector_store(self.settings)
        self.store = store
        self.tender_documents = TenderDocumentRepository(db)
        self.company_documents = DocumentRepository(db)
        self.company_pages = CompanyPageRepository(db)

    # ---------------------------------------------------------------- deletion

    def remove_tender_document(self, company_id: str, document_id: str) -> dict[str, Any]:
        """Remove a tender document's passages and its cached pages."""
        removed = self._remove_passages(document_id)
        pages = TenderPageRepository(self.db).delete_for_document(document_id, company_id)
        return {"document_id": document_id, "passages_removed": removed, "pages_removed": pages}

    def remove_company_document(self, company_id: str, document_id: str) -> dict[str, Any]:
        """Remove a company document's passages and its cached pages."""
        removed = self._remove_passages(document_id)
        pages = self.company_pages.delete_for_document(document_id, company_id)
        return {"document_id": document_id, "passages_removed": removed, "pages_removed": pages}

    def _remove_passages(self, document_id: str) -> bool:
        if self.store is None:
            return False
        try:
            self.store.delete_document(document_id)
            return True
        except (VectorStoreUnavailable, VectorStoreError) as exc:
            logger.warning("The passages of %s could not be removed: %s", document_id, exc)
            return False
        except Exception as exc:  # noqa: BLE001 - the store must not break a delete
            logger.warning("The passages of %s could not be removed: %s", document_id, exc)
            return False

    # ------------------------------------------------------------------- state

    def mark_pending(self, company_id: str, document_id: str, *, tender: bool) -> None:
        """A document that has not been indexed yet."""
        changes = {"index_status": "pending", "index_error": None}
        if tender:
            self.tender_documents.update(document_id, company_id, changes)
        else:
            self.company_documents.update_for_company(document_id, company_id, changes)

    def mark_stale(self, company_id: str, model: str) -> dict[str, Any]:
        """Mark the documents as needing a rebuild after a model change.

        The passages stay where they are until the rebuild replaces them, so
        the answer does not disappear in the middle of the change.
        """
        stale = 0
        for document in self.company_documents.list_for_company(company_id, limit=1000)[0]:
            if document.get("index_status") == "indexed" and document.get("index_model") != model:
                self.company_documents.update_for_company(
                    document["id"], company_id, {"index_status": "stale"}
                )
                stale += 1
        for document in self.db.tender_documents.find({"company_id": company_id}):
            if document.get("index_status") == "indexed" and document.get("index_model") != model:
                self.tender_documents.update(
                    document["_id"], company_id, {"index_status": "stale"}
                )
                stale += 1
        return {"stale": stale, "model": model}
