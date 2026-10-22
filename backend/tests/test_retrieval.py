"""The retrieval service.

The store is a stand-in here, so the tests can check what would be asked of
Qdrant. What matters is the contract: the company filter is always applied,
the scope decides what a search may see, and a passage is checked against the
page it names.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.database import Database
from app.repositories.tender_documents import TenderPageRepository
from app.services.retrieval import (
    SCOPE_ALL,
    SCOPE_COMPANY_EVIDENCE,
    SCOPE_LEGAL_REFERENCE,
    SCOPE_TENDER,
    SCOPE_TENDER_WITH_REFERENCES,
    RetrievalService,
)
from app.services.vector_store import ScoredPassage, VectorStoreUnavailable


class FakeStore:
    """A stand-in for the vector store that records the filters it was given."""

    def __init__(self, points: list[dict] | None = None) -> None:
        self.points = points or []
        self.filters: list[dict] = []
        self.queries: list[list[float]] = []

    def search(self, vector, *, limit=8, filters=None, score_threshold=None):
        self.filters.append(filters or {})
        self.queries.append(vector)
        return [
            ScoredPassage(id=str(index), score=1.0 - index / 10, payload=payload)
            for index, payload in enumerate(self.points[:limit])
        ]

    def health(self) -> dict:
        return {"status": "ok"}


class FakeEmbeddings:
    name = "fake"
    model = "fake-model"
    dimension = 4
    available = True

    def embed(self, texts):
        return [[0.1] * 4 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 4


def make_service(database, store, **settings) -> RetrievalService:
    return RetrievalService(
        database, FakeEmbeddings(), store, settings=Settings(**settings)
    )


def test_the_company_filter_is_always_applied(database):
    store = FakeStore()
    service = make_service(database, store)
    service.search(query="turnover", company_id="company-1", scope=SCOPE_TENDER)
    assert store.filters
    assert store.filters[0]["must"]["company_id"] == "company-1"


def test_the_tender_scope_is_limited_to_that_tender(database):
    store = FakeStore()
    service = make_service(database, store)
    service.search(
        query="turnover", company_id="company-1", scope=SCOPE_TENDER, tender_id="tender-1"
    )
    filters = store.filters[0]
    assert filters["must"]["scope"] == SCOPE_TENDER
    assert filters["must"]["tender_id"] == "tender-1"


def test_the_company_evidence_scope_only_reaches_the_company_documents(database):
    store = FakeStore()
    service = make_service(database, store)
    service.search(
        query="certificate", company_id="company-1", scope=SCOPE_COMPANY_EVIDENCE
    )
    filters = store.filters[0]
    assert filters["must"]["scope"] == SCOPE_COMPANY_EVIDENCE
    assert filters["must"]["company_id"] == "company-1"


def test_the_legal_scope_is_separate_from_the_tender_scope(database):
    store = FakeStore()
    service = make_service(database, store)
    service.search(query="wages", company_id="company-1", scope=SCOPE_LEGAL_REFERENCE)
    assert store.filters[0]["must"]["scope"] == SCOPE_LEGAL_REFERENCE


def test_the_tender_with_references_scope_allows_both(database):
    store = FakeStore()
    service = make_service(database, store)
    service.search(
        query="wages",
        company_id="company-1",
        scope=SCOPE_TENDER_WITH_REFERENCES,
        tender_id="tender-1",
    )
    filters = store.filters[0]
    assert filters["must"]["company_id"] == "company-1"
    assert {"scope": SCOPE_TENDER, "tender_id": "tender-1"} in filters["should"]
    assert {"scope": SCOPE_LEGAL_REFERENCE} in filters["should"]


def test_the_all_scope_still_keeps_the_company(database):
    store = FakeStore()
    service = make_service(database, store)
    service.search(query="wages", company_id="company-1", scope=SCOPE_ALL)
    filters = store.filters[0]
    assert filters["must"]["company_id"] == "company-1"
    assert filters["should"]


def test_an_empty_query_returns_nothing_without_a_search(database):
    store = FakeStore()
    service = make_service(database, store)
    assert service.search(query="   ", company_id="company-1") == []
    assert store.queries == []


def test_a_missing_company_returns_nothing(database):
    store = FakeStore()
    service = make_service(database, store)
    assert service.search(query="turnover", company_id="") == []
    assert store.queries == []


def test_a_store_that_is_switched_off_is_reported(database):
    service = RetrievalService(database, FakeEmbeddings(), None, settings=Settings())
    with pytest.raises(VectorStoreUnavailable):
        service.search(query="turnover", company_id="company-1")


def test_a_passage_is_checked_against_the_page_it_names(database, tender: dict):
    page_text = "3.1 The bidder shall have an average annual turnover of at least INR 5 crore."
    TenderPageRepository(database).replace_for_document(
        company_id=tender["company_id"],
        tender_id=tender["id"],
        document_id="document-1",
        pages=[
            {
                "page_index": 3,
                "printed_label": "3",
                "text": page_text,
                "char_count": len(page_text),
                "has_text": True,
                "text_source": "text_layer",
            }
        ],
    )
    store = FakeStore(
        [
            {
                "document_id": "document-1",
                "company_id": tender["company_id"],
                "tender_id": tender["id"],
                "document_title": "RFP",
                "page_index": 3,
                "printed_page": "3",
                "clause_number": "3.1",
                "text": "3.1 The bidder shall have an average annual turnover of at least INR 5 crore.",
                "scope": SCOPE_TENDER,
            }
        ]
    )
    service = make_service(database, store)
    passages = service.search(
        query="turnover", company_id=tender["company_id"], scope=SCOPE_TENDER
    )
    assert passages
    assert passages[0].verified is True
    assert passages[0].citation.page_index == 3
    assert passages[0].citation.clause_number == "3.1"


def test_a_passage_that_is_not_on_the_page_is_reported_as_unverified(database, tender: dict):
    TenderPageRepository(database).replace_for_document(
        company_id=tender["company_id"],
        tender_id=tender["id"],
        document_id="document-1",
        pages=[
            {
                "page_index": 3,
                "printed_label": "3",
                "text": "Something else entirely.",
                "char_count": 24,
                "has_text": True,
                "text_source": "text_layer",
            }
        ],
    )
    store = FakeStore(
        [
            {
                "document_id": "document-1",
                "company_id": tender["company_id"],
                "tender_id": tender["id"],
                "document_title": "RFP",
                "page_index": 3,
                "printed_page": "3",
                "text": "3.1 The bidder shall have an average annual turnover of INR 5 crore.",
                "scope": SCOPE_TENDER,
            }
        ]
    )
    service = make_service(database, store)
    passages = service.search(
        query="turnover", company_id=tender["company_id"], scope=SCOPE_TENDER
    )
    assert passages
    assert passages[0].verified is False
    assert passages[0].verification_note
