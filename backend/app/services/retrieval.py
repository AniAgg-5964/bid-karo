"""The retrieval service: the one way into the index.

Everything that needs passages comes through here, so the access rules live in
one place.

The rules:

* **The company filter is always applied.** The scope is chosen by the caller,
  but the company comes from the authenticated user and is never taken from
  the request. A search for another company's documents returns nothing, not
  because the model filtered it out, but because the filter never let it in.
* **A passage is checked against its page.** When the page is still stored,
  the passage text is matched against it. A passage that cannot be found on
  the page it names is reported as unverified, not as evidence.
* **A missing store is an honest answer.** The service says the retrieval is
  unavailable; it never returns made-up passages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings, get_settings
from app.core.database import Database
from app.repositories.documents import CompanyPageRepository
from app.repositories.tender_documents import TenderPageRepository
from app.services.citations import Citation, citation_from_payload, verify_against_page
from app.services.embeddings import EmbeddingProvider
from app.services.vector_store import (
    QdrantVectorStore,
    ScoredPassage,
    VectorStoreError,
    VectorStoreUnavailable,
)

logger = logging.getLogger(__name__)

# The scopes a search can be limited to.
SCOPE_TENDER = "tender"
SCOPE_COMPANY_EVIDENCE = "company_evidence"
SCOPE_LEGAL_REFERENCE = "legal_reference"
SCOPE_TENDER_WITH_REFERENCES = "tender_with_references"
SCOPE_ALL = "all"

SCOPES = {
    SCOPE_TENDER,
    SCOPE_COMPANY_EVIDENCE,
    SCOPE_LEGAL_REFERENCE,
    SCOPE_TENDER_WITH_REFERENCES,
    SCOPE_ALL,
}


@dataclass(slots=True)
class RetrievedPassage:
    """One passage, with the reference that lets a user check it."""

    citation: Citation
    score: float
    text: str
    context: str = ""
    verified: bool | None = None
    verification_note: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "context": self.context,
            "score": self.score,
            "verified": self.verified,
            "verification_note": self.verification_note,
            "citation": self.citation.to_dict(),
        }


class RetrievalService:
    """Finds passages inside the scope the caller is allowed to see."""

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
        self.pages = TenderPageRepository(db)
        self.company_pages = CompanyPageRepository(db)

    # ----------------------------------------------------------------- search

    def search(
        self,
        *,
        query: str,
        company_id: str,
        scope: str = SCOPE_TENDER,
        tender_id: str | None = None,
        limit: int | None = None,
        min_score: float | None = None,
    ) -> list[RetrievedPassage]:
        """Find the passages that answer a question.

        The company filter is applied here and cannot be switched off.
        """
        if not (query or "").strip():
            return []
        if not company_id:
            return []
        scope = scope if scope in SCOPES else SCOPE_TENDER

        if self.store is None:
            raise VectorStoreUnavailable("The vector store is switched off.")
        if not self.embeddings.available:
            raise VectorStoreUnavailable("The embedding provider is not available.")

        filters = self._filters(company_id, scope, tender_id)
        vector = self.embeddings.embed_query(query)
        hits = self.store.search(
            vector,
            limit=max(limit or self.settings.retrieval_top_k, 1),
            filters=filters,
            score_threshold=min_score if min_score is not None else None,
        )
        passages = [self._to_passage(hit) for hit in hits]
        self._verify(passages)
        return passages

    def _filters(
        self, company_id: str, scope: str, tender_id: str | None
    ) -> dict[str, Any]:
        """The filter that decides what a search may see."""
        must: dict[str, Any] = {"company_id": company_id}
        should: list[dict[str, Any]] = []

        if scope == SCOPE_TENDER:
            must["scope"] = SCOPE_TENDER
            if tender_id:
                must["tender_id"] = tender_id
        elif scope == SCOPE_COMPANY_EVIDENCE:
            must["scope"] = SCOPE_COMPANY_EVIDENCE
        elif scope == SCOPE_LEGAL_REFERENCE:
            must["scope"] = SCOPE_LEGAL_REFERENCE
        elif scope == SCOPE_TENDER_WITH_REFERENCES:
            if tender_id:
                should.append({"scope": SCOPE_TENDER, "tender_id": tender_id})
            should.append({"scope": SCOPE_LEGAL_REFERENCE})
        else:  # SCOPE_ALL
            if tender_id:
                should.append({"scope": SCOPE_TENDER, "tender_id": tender_id})
            should.append({"scope": SCOPE_COMPANY_EVIDENCE})
            should.append({"scope": SCOPE_LEGAL_REFERENCE})
        return {"must": must, "should": should}

    def _to_passage(self, hit: ScoredPassage) -> RetrievedPassage:
        payload = hit.payload
        citation = citation_from_payload(payload, hit.score)
        return RetrievedPassage(
            citation=citation,
            score=hit.score,
            text=str(payload.get("text") or ""),
            context=str(payload.get("context") or ""),
            metadata={
                "chunk_id": payload.get("chunk_id"),
                "chunk_index": payload.get("chunk_index"),
                "scope": payload.get("scope"),
                "text_source": payload.get("text_source"),
                "embedding_model": payload.get("embedding_model"),
            },
        )

    def _verify(self, passages: list[RetrievedPassage]) -> None:
        """Check each passage against the page it names."""
        cache: dict[tuple[str, int], str] = {}
        for passage in passages:
            document_id = passage.citation.document_id
            page_index = passage.citation.page_index
            if not document_id or not page_index:
                passage.verified = None
                passage.verification_note = "The passage has no page reference."
                continue
            key = (document_id, int(page_index))
            if key not in cache:
                cache[key] = self._page_text(
                    document_id, passage.citation.company_id, int(page_index)
                )
            text = cache[key]
            if not text:
                passage.verified = None
                passage.verification_note = "The page is no longer stored."
                continue
            if verify_against_page(passage.text, text):
                passage.verified = True
                passage.verification_note = None
            else:
                passage.verified = False
                passage.verification_note = (
                    "The passage was not found on the page it names."
                )

    def _page_text(self, document_id: str, company_id: str, page_index: int) -> str:
        """The stored text of a page, from whichever document holds it."""
        page = self.pages.find_page(document_id, company_id, page_index)
        if page:
            return str(page.get("text") or "")
        page = self.company_pages.find_page(document_id, company_id, page_index)
        return str((page or {}).get("text") or "")
