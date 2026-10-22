"""Indexing the documents into the retrieval store.

The pipeline is the one that already exists: the pages are read from Mongo,
split into passages, embedded in batches and written to Qdrant. Nothing is
re-extracted that was already extracted, and nothing is stored that cannot be
traced back to a document and a page.

The rules this service keeps:

* **Indexing is idempotent.** The point id is derived from the document, the
  content hash and the chunk index, so the same content always lands on the
  same points. Re-running the ingestion does not create a second copy.
* **A changed document replaces its old passages.** The document's passages are
  removed before the new ones are written, so a stale clause cannot be found
  next to a new one.
* **A failure is visible and recoverable.** The document is marked failed with
  the reason, the partial passages are removed, and a retry starts from the
  beginning. A document is never marked indexed when it is not.
* **The store is optional.** When Qdrant is not available the documents stay
  untouched in MongoDB and the service says so.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.core.config import Settings, get_settings
from app.core.database import Database
from app.core.exceptions import NotFoundError
from app.repositories.documents import CompanyPageRepository, DocumentRepository
from app.repositories.tender_documents import TenderDocumentRepository, TenderPageRepository
from app.services.chunking import Passage, chunk_pages, content_hash
from app.services.embeddings import EmbeddingProvider
from app.services.pdf_extraction import PdfExtractionError, extract_pdf_pages
from app.services.storage import StorageService
from app.services.vector_store import (
    QdrantVectorStore,
    VectorPoint,
    VectorStoreError,
    VectorStoreUnavailable,
    iter_batches,
)

logger = logging.getLogger(__name__)

# The scopes a passage can belong to. They are the retrieval filters.
SCOPE_TENDER = "tender"
SCOPE_COMPANY = "company_evidence"
SCOPE_REFERENCE = "legal_reference"

# A namespace for the deterministic point ids.
POINT_NAMESPACE = uuid.UUID("6f1a1b8e-0b6f-4a3f-9b4a-2f5f6d7c8b90")


class IngestionError(RuntimeError):
    """Indexing could not be completed."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _point_id(document_id: str, hash_value: str, chunk_index: int) -> str:
    """A deterministic point id, so re-indexing overwrites rather than adds."""
    name = f"{document_id}:{hash_value}:{chunk_index}"
    return str(uuid.uuid5(POINT_NAMESPACE, name))


class DocumentIngestionService:
    """Turns stored documents into searchable passages."""

    def __init__(
        self,
        db: Database,
        storage: StorageService,
        embeddings: EmbeddingProvider,
        store: QdrantVectorStore | None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.storage = storage
        self.embeddings = embeddings
        self.store = store
        self.settings = settings or get_settings()
        self.tender_documents = TenderDocumentRepository(db)
        self.tender_pages = TenderPageRepository(db)
        self.company_documents = DocumentRepository(db)
        self.company_pages = CompanyPageRepository(db)

    # ------------------------------------------------------------------ public

    def store_status(self) -> str:
        """Whether the vector store can be used right now."""
        if self.store is None:
            return "disabled"
        try:
            return str(self.store.health().get("status") or "unavailable")
        except Exception:  # noqa: BLE001 - health must not raise
            return "unavailable"

    def index_tender_document(
        self, company_id: str, tender_id: str, document_id: str, *, force: bool = False
    ) -> dict[str, Any]:
        """Index one tender document."""
        document = self.tender_documents.find_for_company(document_id, company_id)
        if not document or document.get("tender_id") != tender_id:
            raise NotFoundError("Tender document not found.")
        if document.get("is_container"):
            # A package is a container; its members are indexed on their own.
            return self._skip(document, "A package is indexed through its members.")

        pages = self.tender_pages.list_for_document(document_id, company_id)
        payload_base = {
            "company_id": company_id,
            "tender_id": tender_id,
            "document_id": document_id,
            "document_version_id": document.get("sha256") or document_id,
            "document_title": document.get("title") or document.get("original_filename"),
            "document_kind": document.get("kind") or "document",
            "document_type": document.get("kind") or "document",
            "original_filename": document.get("original_filename"),
            "storage_reference": self._tender_storage_reference(company_id, tender_id, document),
            "source_type": document.get("source") or "uploaded",
            "source_url": document.get("source_url"),
            "retrieved_at": document.get("retrieved_at"),
            "document_status": document.get("status"),
            "verification_status": document.get("verification_status"),
            "scope": SCOPE_TENDER,
        }
        return self._index(
            document=document,
            pages=pages,
            payload_base=payload_base,
            update=self._update_tender_state,
            force=force,
        )

    def index_company_document(
        self, company_id: str, document_id: str, *, force: bool = False
    ) -> dict[str, Any]:
        """Index one company document, extracting it when that has not happened."""
        document = self.company_documents.find_for_company(document_id, company_id)
        if not document:
            raise NotFoundError("Document not found.")

        pages = self._company_pages(company_id, document)
        payload_base = {
            "company_id": company_id,
            "tender_id": None,
            "document_id": document_id,
            "document_version_id": document.get("sha256") or document_id,
            "document_title": document.get("title") or document.get("original_filename"),
            "document_kind": "company_document",
            "document_type": document.get("document_type"),
            "original_filename": document.get("original_filename"),
            "storage_reference": self._company_storage_reference(company_id, document),
            "source_type": "uploaded",
            "source_url": None,
            "retrieved_at": document.get("created_at"),
            "document_status": "stored",
            "verification_status": document.get("verification_status"),
            "scope": SCOPE_COMPANY,
        }
        return self._index(
            document=document,
            pages=pages,
            payload_base=payload_base,
            update=self._update_company_state,
            force=force,
        )

    def index_tender(self, company_id: str, tender_id: str, *, force: bool = False) -> dict[str, Any]:
        """Index every document of a tender."""
        documents = self.tender_documents.list_for_tender(company_id, tender_id)
        indexed = 0
        skipped = 0
        failed = 0
        passages = 0
        for document in documents:
            try:
                result = self.index_tender_document(
                    company_id, tender_id, document["id"], force=force
                )
            except Exception as exc:  # noqa: BLE001 - one document must not stop the rest
                failed += 1
                logger.warning("Document %s could not be indexed: %s", document.get("id"), exc)
                continue
            if result.get("status") == "failed":
                failed += 1
            elif result.get("status") in {"indexed", "unchanged"}:
                indexed += 1
                passages += int(result.get("chunks") or 0)
            else:
                skipped += 1
        return {
            "documents": len(documents),
            "indexed": indexed,
            "skipped": skipped,
            "failed": failed,
            "passages": passages,
        }

    def index_company(self, company_id: str, *, force: bool = False) -> dict[str, Any]:
        """Index every company document."""
        documents, _total = self.company_documents.list_for_company(company_id, limit=500)
        indexed = 0
        skipped = 0
        failed = 0
        passages = 0
        for document in documents:
            try:
                result = self.index_company_document(company_id, document["id"], force=force)
            except Exception as exc:  # noqa: BLE001 - one document must not stop the rest
                failed += 1
                logger.warning("Document %s could not be indexed: %s", document.get("id"), exc)
                continue
            if result.get("status") == "failed":
                failed += 1
            elif result.get("status") in {"indexed", "unchanged"}:
                indexed += 1
                passages += int(result.get("chunks") or 0)
            else:
                skipped += 1
        return {
            "documents": len(documents),
            "indexed": indexed,
            "skipped": skipped,
            "failed": failed,
            "passages": passages,
        }

    # ----------------------------------------------------------------- helpers

    def _index(
        self,
        *,
        document: dict,
        pages: list[dict],
        payload_base: dict[str, Any],
        update,
        force: bool,
    ) -> dict[str, Any]:
        document_id = str(document["id"])

        if self.store is None:
            return self._skip(document, "The vector store is switched off.")
        if not self.embeddings.available:
            return self._fail(document, update, "The embedding provider is not available.")

        usable = [page for page in pages if (page.get("text") or "").strip()]
        if not usable:
            return self._skip(document, "The document has no readable text.")

        passages = chunk_pages(
            usable,
            max_words=_max_words(self.settings),
            max_chars=self.settings.chunk_max_chars,
            overlap_words=_overlap(self.settings),
        )
        if not passages:
            return self._skip(document, "The document produced no passages.")
        passages = passages[: max(self.settings.chunk_max_per_document, 1)]

        hash_value = content_hash(passages)
        model = getattr(self.embeddings, "model", "") or "unknown"

        if (
            not force
            and document.get("index_status") == "indexed"
            and document.get("index_content_hash") == hash_value
            and document.get("index_model") == model
        ):
            # The same content, already indexed: nothing to do.
            return {
                "status": "unchanged",
                "document_id": document_id,
                "chunks": document.get("index_chunk_count") or 0,
                "content_hash": hash_value,
            }

        try:
            dimension = self.embeddings.dimension
            self.store.ensure_collection(dimension)
        except VectorStoreUnavailable as exc:
            return self._fail(document, update, str(exc))
        except (VectorStoreError, Exception) as exc:  # noqa: BLE001
            return self._fail(document, update, str(exc))

        # The old passages of this document go first, so a changed document
        # cannot leave a stale clause behind.
        try:
            self.store.delete_document(document_id)
        except VectorStoreUnavailable as exc:
            return self._fail(document, update, str(exc))
        except VectorStoreError:
            logger.info("The old passages of %s could not be removed.", document_id)

        indexed_at = _now()
        try:
            written = self._write(passages, payload_base, hash_value, model, indexed_at)
        except (VectorStoreUnavailable, VectorStoreError) as exc:
            self._remove_partial(document_id)
            return self._fail(document, update, str(exc))
        except Exception as exc:  # noqa: BLE001
            self._remove_partial(document_id)
            return self._fail(document, update, str(exc))

        update(
            document_id,
            payload_base["company_id"],
            {
                "index_status": "indexed",
                "indexed_at": indexed_at,
                "index_chunk_count": written,
                "index_content_hash": hash_value,
                "index_model": model,
                "index_provider": getattr(self.embeddings, "name", ""),
                "index_error": None,
            },
        )
        return {
            "status": "indexed",
            "document_id": document_id,
            "chunks": written,
            "content_hash": hash_value,
            "model": model,
        }

    def _write(
        self,
        passages: list[Passage],
        payload_base: dict[str, Any],
        hash_value: str,
        model: str,
        indexed_at: datetime,
    ) -> int:
        """Embed and store the passages, in batches."""
        written = 0
        batch_size = max(self.settings.embedding_batch_size, 1)
        for batch in iter_batches(passages, batch_size):
            vectors = self.embeddings.embed([passage.embedding_text for passage in batch])
            points: list[VectorPoint] = []
            for passage, vector in zip(batch, vectors):
                point_id = _point_id(str(payload_base["document_id"]), hash_value, passage.chunk_index)
                payload = {
                    **payload_base,
                    "chunk_id": point_id,
                    "chunk_index": passage.chunk_index,
                    "page_index": passage.page_index,
                    "printed_page": passage.printed_page,
                    "section_heading": passage.section_heading,
                    "clause_number": passage.clause_number,
                    "text": passage.text,
                    "context": passage.context,
                    "word_count": passage.word_count,
                    "content_hash": hash_value,
                    "embedding_model": model,
                    "embedding_provider": getattr(self.embeddings, "name", ""),
                    "embedding_version": model,
                    "indexed_at": indexed_at.isoformat(),
                    "text_source": self._text_source(passage),
                }
                points.append(VectorPoint(id=point_id, vector=list(vector), payload=payload))
            self.store.upsert_points(points)  # type: ignore[union-attr]
            written += len(points)
        return written

    def _text_source(self, passage: Passage) -> str:
        return str(passage.metadata.get("text_source") or "text_layer")

    def _remove_partial(self, document_id: str) -> None:
        if self.store is None:
            return
        try:
            self.store.delete_document(document_id)
        except Exception:  # noqa: BLE001 - the failure is already recorded
            logger.warning("The partial passages of %s could not be removed.", document_id)

    def _skip(self, document: dict, reason: str) -> dict[str, Any]:
        return {
            "status": "skipped",
            "document_id": document.get("id"),
            "reason": reason,
            "chunks": 0,
        }

    def _fail(self, document: dict, update, reason: str) -> dict[str, Any]:
        document_id = str(document.get("id") or "")
        company_id = str(document.get("company_id") or "")
        try:
            update(
                document_id,
                company_id,
                {
                    "index_status": "failed",
                    "index_error": reason,
                    "indexed_at": None,
                },
            )
        except Exception:  # noqa: BLE001 - the failure is already recorded
            logger.warning("The index state of %s could not be saved.", document_id)
        return {
            "status": "failed",
            "document_id": document_id,
            "reason": reason,
            "chunks": 0,
        }

    def _update_tender_state(self, document_id: str, company_id: str, changes: dict) -> None:
        self.tender_documents.update(document_id, company_id, changes)

    def _update_company_state(self, document_id: str, company_id: str, changes: dict) -> None:
        self.company_documents.update_for_company(document_id, company_id, changes)

    # ----------------------------------------------------------- company pages

    def _company_pages(self, company_id: str, document: dict) -> list[dict]:
        """The pages of a company document, extracted once and then kept."""
        document_id = str(document["id"])
        pages = self.company_pages.list_for_document(document_id, company_id)
        if pages:
            return pages

        path = self.storage.resolve_company_document(company_id, document["stored_filename"])
        if not path.exists():
            return []
        if path.suffix.lower() != ".pdf":
            return []

        ocr = None
        if self.settings.ocr_enabled:
            from app.services.ocr import build_ocr

            try:
                ocr = build_ocr(
                    language=self.settings.ocr_language,
                    tesseract_cmd=self.settings.tesseract_cmd,
                    timeout_seconds=self.settings.ocr_timeout_seconds,
                )
            except Exception:  # noqa: BLE001 - OCR is optional
                ocr = None

        try:
            extraction = extract_pdf_pages(
                path.read_bytes(),
                max_pages=self.settings.pdf_max_pages,
                ocr=ocr,
                ocr_dpi=self.settings.ocr_dpi,
                ocr_max_pages=self.settings.ocr_max_pages,
            )
        except PdfExtractionError:
            return []

        stored = [
            {
                "page_index": page.page_index,
                "printed_label": page.printed_label,
                "text": page.text,
                "char_count": page.char_count,
                "has_text": page.has_text,
                "text_source": page.text_source,
            }
            for page in extraction.pages
        ]
        self.company_pages.replace_for_document(
            company_id=company_id, document_id=document_id, pages=stored
        )
        return stored

    # -------------------------------------------------------------- references

    def _tender_storage_reference(
        self, company_id: str, tender_id: str, document: dict
    ) -> str:
        filename = document.get("stored_filename") or ""
        return f"companies/{company_id}/tenders/{tender_id}/{filename}"

    def _company_storage_reference(self, company_id: str, document: dict) -> str:
        filename = document.get("stored_filename") or ""
        return f"companies/{company_id}/{filename}"


def _max_words(settings: Settings) -> int:
    """The word limit that matches the character limit."""
    if settings.chunk_max_chars <= 0:
        return 220
    return max(settings.chunk_max_chars // 6, 40)


def _overlap(settings: Settings) -> int:
    if settings.chunk_overlap_chars <= 0:
        return 0
    return max(settings.chunk_overlap_chars // 6, 0)
