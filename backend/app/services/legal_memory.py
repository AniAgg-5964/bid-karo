"""The memory of the official pages we have already read.

The legal agent used to read the web for every clause, every time. Now it
looks in the index first:

* a page we have read before, and that is still fresh enough, is used as it
  is, with the URL and the date it was read;
* a page we have not read, or one that has gone stale, is read again from the
  official source;
* every page we read is kept, so the next question about the same provision
  is answered from the memory.

The rule that keeps this honest: **a reading in the index is not proof that
the law is still the same.** A stored reading carries the date it was read,
and a reading older than the freshness limit is read again. The answer always
says which it was.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import Settings, get_settings
from app.core.database import Database
from app.repositories.knowledge import KnowledgeDocumentRepository
from app.services.chunking import chunk_page
from app.services.embeddings import EmbeddingProvider
from app.services.retrieval import SCOPE_LEGAL_REFERENCE, RetrievalService
from app.services.vector_store import (
    QdrantVectorStore,
    VectorPoint,
    VectorStoreError,
    VectorStoreUnavailable,
    point_id,
)

logger = logging.getLogger(__name__)

SCOPE_REFERENCE = SCOPE_LEGAL_REFERENCE


@dataclass(slots=True)
class RememberedPage:
    """A page we have read, in the shape the legal agent expects."""

    url: str
    title: str
    text: str
    retrieved_at: datetime | None = None
    from_memory: bool = True
    document_id: str | None = None


class LegalMemory:
    """Keeps the official pages we have read, and finds them again."""

    def __init__(
        self,
        db: Database,
        embeddings: EmbeddingProvider,
        store: QdrantVectorStore | None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.embeddings = embeddings
        self.store = store
        self.settings = settings or get_settings()
        self.repository = KnowledgeDocumentRepository(db)
        self.retrieval = RetrievalService(db, embeddings, store, settings=self.settings)

    # ------------------------------------------------------------------ write

    def remember(
        self,
        *,
        company_id: str,
        url: str,
        title: str,
        text: str,
        topic: str | None = None,
        retrieved_at: datetime | None = None,
    ) -> dict | None:
        """Keep a page we read, and index it so it can be found again."""
        if not (url or "").strip() or not (text or "").strip():
            return None
        moment = retrieved_at or datetime.now(timezone.utc)
        limit = max(self.settings.legal_memory_max_chars, 0)
        truncated = False
        if limit and len(text) > limit:
            # A page can be a whole book. We keep the part we read and say so.
            text = text[:limit]
            truncated = True
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

        existing = self.repository.find_by_url(company_id, url, SCOPE_REFERENCE)
        if existing:
            if existing.get("content_hash") == digest:
                # The same page, already remembered.
                return existing
            document = self.repository.update(
                existing["id"],
                company_id,
                {"text": text, "content_hash": digest, "retrieved_at": moment},
            )
        else:
            document = self.repository.create(
                {
                    "company_id": company_id,
                    "scope": SCOPE_REFERENCE,
                    "url": url,
                    "title": title or url,
                    "domain": _domain_of(url),
                    "topic": topic,
                    "text": text,
                    "content_hash": digest,
                    "retrieved_at": moment,
                    "truncated": truncated,
                    "index_status": "pending",
                }
            )
        if document:
            self._index(document)
            document = self.repository.find_for_company(document["id"], company_id) or document
        return document

    def _index(self, document: dict) -> int:
        """Index the passages of a remembered page."""
        if self.store is None or not self.embeddings.available:
            return 0
        text = document.get("text") or ""
        passages = chunk_page(
            1,
            "1",
            text,
            max_words=max(self.settings.chunk_max_chars // 6, 40),
            max_chars=self.settings.chunk_max_chars,
            overlap_words=max(self.settings.chunk_overlap_chars // 6, 0),
        )
        if not passages:
            return 0
        try:
            self.store.ensure_collection(self.embeddings.dimension)
            self.store.delete_document(document["id"])
            points: list[VectorPoint] = []
            texts: list[str] = []
            for passage in passages:
                chunk_id = point_id(document["id"], str(passage.chunk_index))
                texts.append(passage.embedding_text)
                payload = {
                    "company_id": document["company_id"],
                    "tender_id": None,
                    "document_id": document["id"],
                    "document_version_id": document.get("content_hash"),
                    "document_title": document.get("title"),
                    "document_kind": "legal_reference",
                    "document_type": "legal_reference",
                    "original_filename": None,
                    "storage_reference": None,
                    "source_type": "official_web",
                    "source_url": document.get("url"),
                    "retrieved_at": (
                        document.get("retrieved_at").isoformat()
                        if isinstance(document.get("retrieved_at"), datetime)
                        else None
                    ),
                    "document_status": "read",
                    "verification_status": "official_source",
                    "scope": SCOPE_REFERENCE,
                    "chunk_id": chunk_id,
                    "chunk_index": passage.chunk_index,
                    "page_index": passage.page_index,
                    "printed_page": passage.printed_page,
                    "section_heading": passage.section_heading,
                    "clause_number": passage.clause_number,
                    "text": passage.text,
                    "context": passage.context,
                    "word_count": passage.word_count,
                    "content_hash": document.get("content_hash"),
                    "embedding_model": getattr(self.embeddings, "model", ""),
                    "embedding_provider": getattr(self.embeddings, "name", ""),
                    "embedding_version": getattr(self.embeddings, "model", ""),
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                    "text_source": "web",
                    "topic": document.get("topic"),
                }
                points.append(VectorPoint(id=chunk_id, vector=[], payload=payload))
            vectors = self.embeddings.embed(texts)
            for point, vector in zip(points, vectors):
                point.vector = list(vector)
            self.store.upsert_points(points)
        except (VectorStoreUnavailable, VectorStoreError) as exc:
            logger.warning("The page %s could not be indexed: %s", document.get("url"), exc)
            self.repository.update(
                document["id"], document["company_id"], {"index_status": "failed"}
            )
            return 0
        except Exception as exc:  # noqa: BLE001 - the page is kept either way
            logger.warning("The page %s could not be indexed: %s", document.get("url"), exc)
            self.repository.update(
                document["id"], document["company_id"], {"index_status": "failed"}
            )
            return 0
        self.repository.update(
            document["id"],
            document["company_id"],
            {
                "index_status": "indexed",
                "indexed_at": datetime.now(timezone.utc),
                "index_chunk_count": len(points),
            },
        )
        return len(points)

    # ------------------------------------------------------------------- read

    def recall(
        self,
        *,
        company_id: str,
        question: str,
        topic: str | None = None,
        max_age_days: int | None = None,
        limit: int = 3,
    ) -> list[RememberedPage]:
        """The pages we have read that answer this question, if they are fresh.

        A page that is older than the freshness limit is not returned: the
        agent reads the official source again instead of relying on an old
        reading of the law.
        """
        if self.store is None or not self.embeddings.available:
            return []
        try:
            hits = self.retrieval.search(
                query=question,
                company_id=company_id,
                scope=SCOPE_REFERENCE,
                limit=limit,
            )
        except (VectorStoreUnavailable, VectorStoreError) as exc:
            logger.info("The legal memory could not be searched: %s", exc)
            return []
        except Exception as exc:  # noqa: BLE001 - the memory is optional
            logger.info("The legal memory could not be searched: %s", exc)
            return []

        days = max_age_days if max_age_days is not None else self.settings.legal_memory_max_age_days
        now = datetime.now(timezone.utc)
        pages: list[RememberedPage] = []
        seen: set[str] = set()
        for hit in hits:
            document_id = hit.citation.document_id
            if document_id in seen:
                # One page, one reading: a page with several passages is still
                # one reading.
                continue
            document = self.repository.find_for_company(document_id, company_id)
            if not document:
                continue
            seen.add(document_id)
            if topic and document.get("topic") and document["topic"] != topic:
                continue
            moment = document.get("retrieved_at")
            if isinstance(moment, datetime):
                if moment.tzinfo is None:
                    moment = moment.replace(tzinfo=timezone.utc)
                if days >= 0 and now - moment > timedelta(days=days):
                    # Too old to rely on. The agent reads the source again.
                    continue
            pages.append(
                RememberedPage(
                    url=document.get("url") or "",
                    title=document.get("title") or "",
                    text=document.get("text") or "",
                    retrieved_at=moment if isinstance(moment, datetime) else None,
                    from_memory=True,
                    document_id=document_id,
                )
            )
        return pages

    def stats(self, company_id: str) -> dict[str, Any]:
        documents = self.repository.list_for_company(company_id, scope=SCOPE_REFERENCE)
        return {
            "pages": len(documents),
            "indexed": sum(1 for item in documents if item.get("index_status") == "indexed"),
        }


def _domain_of(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(url).netloc.lower()
    except Exception:  # noqa: BLE001 - the URL is only for display
        return ""
