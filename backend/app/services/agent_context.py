"""What the agents read from the index.

The agents used to see the tender's clauses as short excerpts and the
company's documents as a list of titles. Now they can also see the passages
the retrieval service finds: the tender's own words around a clause, and what
our own documents actually say.

Two rules:

* **Only the company's passages.** The retrieval service applies the company
  filter, and the tender scope adds the tender, so an agent cannot read
  another company's documents.
* **A passage is quoted, not summarised.** The passages are given to the model
  as text with their page and clause, so a proposal can still be checked
  against the document it came from.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.retrieval import (
    SCOPE_COMPANY_EVIDENCE,
    SCOPE_TENDER,
    RetrievedPassage,
    RetrievalService,
)

logger = logging.getLogger(__name__)

MAX_CLAUSES = 8
MAX_PASSAGES_PER_CLAUSE = 2
MAX_EVIDENCE_PASSAGES = 6
MAX_PASSAGE_CHARS = 400


def _shorten(text: str, limit: int = MAX_PASSAGE_CHARS) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "..."


def _label(passage: RetrievedPassage) -> str:
    citation = passage.citation
    bits = [citation.document_title or "document"]
    if citation.page_index:
        bits.append(f"page {citation.page_index}")
    if citation.clause_number:
        bits.append(f"clause {citation.clause_number}")
    return ", ".join(bits)


def clause_passages(
    retrieval: RetrievalService | None,
    *,
    company_id: str,
    tender_id: str | None,
    requirements: list[dict],
    max_clauses: int = MAX_CLAUSES,
) -> dict[str, list[RetrievedPassage]]:
    """The tender's own words around each clause we will act on."""
    if retrieval is None:
        return {}
    found: dict[str, list[RetrievedPassage]] = {}
    for requirement in requirements[:max_clauses]:
        query = (requirement.get("excerpt") or requirement.get("title") or "").strip()
        if not query:
            continue
        try:
            passages = retrieval.search(
                query=query,
                company_id=company_id,
                scope=SCOPE_TENDER,
                tender_id=tender_id,
                limit=MAX_PASSAGES_PER_CLAUSE,
            )
        except Exception as exc:  # noqa: BLE001 - the index is optional
            logger.info("The clause passages could not be read: %s", exc)
            continue
        if passages:
            found[str(requirement.get("id"))] = passages
    return found


def evidence_passages(
    retrieval: RetrievalService | None,
    *,
    company_id: str,
    requirements: list[dict],
    limit: int = MAX_EVIDENCE_PASSAGES,
) -> list[RetrievedPassage]:
    """What our own documents say about the clauses we are acting on."""
    if retrieval is None:
        return []
    seen: set[str] = set()
    found: list[RetrievedPassage] = []
    for requirement in requirements[:MAX_CLAUSES]:
        query = (requirement.get("excerpt") or requirement.get("title") or "").strip()
        if not query:
            continue
        try:
            passages = retrieval.search(
                query=query,
                company_id=company_id,
                scope=SCOPE_COMPANY_EVIDENCE,
                limit=2,
            )
        except Exception as exc:  # noqa: BLE001 - the index is optional
            logger.info("The evidence passages could not be read: %s", exc)
            continue
        for passage in passages:
            key = f"{passage.citation.document_id}:{passage.citation.page_index}"
            if key in seen:
                continue
            seen.add(key)
            found.append(passage)
            if len(found) >= limit:
                return found
    return found


def format_clause_context(passages_by_requirement: dict[str, list[RetrievedPassage]]) -> str:
    """The tender's own words, as a block the model can read."""
    if not passages_by_requirement:
        return "(the indexed tender documents were not available for these clauses)"
    lines: list[str] = []
    for requirement_id, passages in passages_by_requirement.items():
        for passage in passages:
            lines.append(f"- [{_label(passage)}] {_shorten(passage.text)}")
    return "\n".join(lines) or "(the indexed tender documents were not available)"


def format_evidence_context(passages: list[RetrievedPassage]) -> str:
    """What our own documents say, as a block the model can read."""
    if not passages:
        return "(no indexed company document matched these clauses)"
    lines = [
        f"- [{_label(passage)}] {_shorten(passage.text)}" for passage in passages
    ]
    return "\n".join(lines)


def citation_payload(passages: list[RetrievedPassage]) -> list[dict[str, Any]]:
    """The passages, in the shape a stored proposal keeps."""
    return [
        {
            "document_id": passage.citation.document_id,
            "document_title": passage.citation.document_title,
            "page_index": passage.citation.page_index,
            "clause_number": passage.citation.clause_number,
            "score": passage.score,
            "verified": passage.verified,
        }
        for passage in passages
    ]
