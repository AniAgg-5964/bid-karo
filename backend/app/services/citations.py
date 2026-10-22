"""Turning a retrieved passage into a source the user can check.

A passage that cannot be traced back to a document and a page is not evidence.
This module keeps the two halves together: the passage, and the reference that
says where it came from. It also holds the check that a passage really exists
on the page it claims, which uses the same whitespace-insensitive match as the
quote gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.services.requirement_service import normalize_for_match


@dataclass(slots=True)
class Citation:
    """Where a passage came from."""

    document_id: str
    document_title: str
    document_kind: str
    company_id: str
    tender_id: str | None = None
    page_index: int | None = None
    printed_page: str | None = None
    section_heading: str | None = None
    clause_number: str | None = None
    excerpt: str = ""
    source_url: str | None = None
    source_type: str = "uploaded"
    retrieved_at: datetime | None = None
    verification_status: str | None = None
    text_source: str | None = None
    original_filename: str | None = None
    document_type: str | None = None
    score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "document_kind": self.document_kind,
            "company_id": self.company_id,
            "tender_id": self.tender_id,
            "page_index": self.page_index,
            "printed_page": self.printed_page,
            "section_heading": self.section_heading,
            "clause_number": self.clause_number,
            "excerpt": self.excerpt,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "retrieved_at": self.retrieved_at,
            "verification_status": self.verification_status,
            "text_source": self.text_source,
            "original_filename": self.original_filename,
            "document_type": self.document_type,
            "score": self.score,
        }


def citation_from_payload(payload: dict[str, Any], score: float | None = None) -> Citation:
    """Build a citation from a stored passage payload."""
    retrieved_at = payload.get("retrieved_at")
    if isinstance(retrieved_at, str):
        try:
            retrieved_at = datetime.fromisoformat(retrieved_at)
        except ValueError:
            retrieved_at = None
    return Citation(
        document_id=str(payload.get("document_id") or ""),
        document_title=str(payload.get("document_title") or "Untitled document"),
        document_kind=str(payload.get("document_kind") or "document"),
        company_id=str(payload.get("company_id") or ""),
        tender_id=payload.get("tender_id"),
        page_index=payload.get("page_index"),
        printed_page=payload.get("printed_page"),
        section_heading=payload.get("section_heading"),
        clause_number=payload.get("clause_number"),
        excerpt=str(payload.get("text") or ""),
        source_url=payload.get("source_url"),
        source_type=str(payload.get("source_type") or "uploaded"),
        retrieved_at=retrieved_at,
        verification_status=payload.get("verification_status"),
        text_source=payload.get("text_source"),
        original_filename=payload.get("original_filename"),
        document_type=payload.get("document_type"),
        score=score,
    )


def verify_against_page(excerpt: str, page_text: str) -> bool:
    """Whether the excerpt really appears on the page.

    The match ignores whitespace and typography, so a passage that came from
    the page text is always found, and a passage that was invented is not.
    """
    if not (excerpt or "").strip():
        return False
    if not (page_text or "").strip():
        return False
    return normalize_for_match(excerpt) in normalize_for_match(page_text)
