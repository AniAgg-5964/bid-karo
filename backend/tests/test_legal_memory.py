"""The memory of the official pages we have read.

The rules under test: a page we read is kept and found again, a reading that
has gone stale is not used, and the same page is not kept twice.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import Settings
from app.core.database import Database
from app.repositories.knowledge import KnowledgeDocumentRepository
from app.services.legal_memory import LegalMemory
from app.services.vector_store import VectorStoreUnavailable


class FakeStore:
    """A stand-in for the vector store."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.points: dict[str, dict] = {}

    def health(self):
        return {"status": "unavailable"} if self.fail else {"status": "ok"}

    def ensure_collection(self, dimension, *, distance="Cosine"):
        return True

    def delete_document(self, document_id):
        for key in [k for k, v in self.points.items() if v.get("document_id") == document_id]:
            self.points.pop(key)
        return 1

    def upsert_points(self, points):
        if self.fail:
            raise RuntimeError("the store is not available")
        for point in points:
            self.points[point.id] = point.payload
        return len(points)

    def search(self, vector, *, limit=8, filters=None, score_threshold=None):
        from app.services.vector_store import ScoredPassage

        hits = []
        for index, (point_id, payload) in enumerate(list(self.points.items())[:limit]):
            hits.append(ScoredPassage(id=point_id, score=1.0 - index / 10, payload=payload))
        return hits

    def count(self, filters=None):
        return len(self.points)


class FakeEmbeddings:
    name = "fake"
    model = "fake-model"
    dimension = 8
    available = True

    def embed(self, texts):
        return [[float(len(entry) % 5)] * 8 for entry in texts]

    def embed_query(self, text):
        return [0.1] * 8


def make_memory(database, store, **settings) -> LegalMemory:
    return LegalMemory(
        database, FakeEmbeddings(), store, settings=Settings(**settings)
    )


PAGE = (
    "Minimum Wages Act, 1948\n\n"
    "3. Payment of wages.- Every employer shall pay the wages to the workers "
    "on or before the seventh day of the month."
)
PAGE_TWO = (
    "Payment of Bonus Act, 1965\n\n"
    "8. Calculation of bonus.- The bonus payable to a worker in any year shall "
    "be at least eight and one third per cent of the wages paid."
)


def test_a_page_we_read_is_kept_and_found_again(database):
    store = FakeStore()
    memory = make_memory(database, store)
    document = memory.remember(
        company_id="company-1",
        url="https://www.indiacode.nic.in/minimum-wages-act",
        title="Minimum Wages Act, 1948",
        text=PAGE,
        topic="labour",
    )
    assert document
    assert document["scope"] == "legal_reference"
    assert document["index_status"] == "indexed"
    assert store.points

    pages = memory.recall(
        company_id="company-1", question="when must wages be paid?", topic="labour"
    )
    assert pages
    assert pages[0].url == "https://www.indiacode.nic.in/minimum-wages-act"
    assert "seventh day" in pages[0].text
    assert pages[0].from_memory is True


def test_the_same_page_is_not_kept_twice(database):
    store = FakeStore()
    memory = make_memory(database, store)
    first = memory.remember(
        company_id="company-1",
        url="https://www.indiacode.nic.in/minimum-wages-act",
        title="Minimum Wages Act, 1948",
        text=PAGE,
        topic="labour",
    )
    second = memory.remember(
        company_id="company-1",
        url="https://www.indiacode.nic.in/minimum-wages-act",
        title="Minimum Wages Act, 1948",
        text=PAGE,
        topic="labour",
    )
    assert first["id"] == second["id"]
    assert len(KnowledgeDocumentRepository(database).list_for_company("company-1")) == 1


def test_a_reading_that_has_gone_stale_is_not_used(database):
    store = FakeStore()
    memory = make_memory(database, store)
    document = memory.remember(
        company_id="company-1",
        url="https://www.indiacode.nic.in/minimum-wages-act",
        title="Minimum Wages Act, 1948",
        text=PAGE,
        topic="labour",
    )
    # The reading was made a long time ago.
    KnowledgeDocumentRepository(database).update(
        document["id"],
        "company-1",
        {"retrieved_at": datetime.now(timezone.utc) - timedelta(days=90)},
    )
    pages = memory.recall(
        company_id="company-1",
        question="when must wages be paid?",
        topic="labour",
        max_age_days=30,
    )
    assert pages == []


def test_a_reading_within_the_limit_is_used(database):
    store = FakeStore()
    memory = make_memory(database, store)
    document = memory.remember(
        company_id="company-1",
        url="https://www.indiacode.nic.in/minimum-wages-act",
        title="Minimum Wages Act, 1948",
        text=PAGE,
        topic="labour",
    )
    KnowledgeDocumentRepository(database).update(
        document["id"],
        "company-1",
        {"retrieved_at": datetime.now(timezone.utc) - timedelta(days=5)},
    )
    pages = memory.recall(
        company_id="company-1",
        question="when must wages be paid?",
        topic="labour",
        max_age_days=30,
    )
    assert len(pages) == 1


def test_another_company_cannot_reach_the_memory(database):
    store = FakeStore()
    memory = make_memory(database, store)
    memory.remember(
        company_id="company-1",
        url="https://www.indiacode.nic.in/minimum-wages-act",
        title="Minimum Wages Act, 1948",
        text=PAGE,
        topic="labour",
    )
    pages = memory.recall(
        company_id="company-2", question="when must wages be paid?", topic="labour"
    )
    assert pages == []


def test_a_store_that_is_down_leaves_the_page_kept_but_unindexed(database):
    store = FakeStore(fail=True)
    memory = make_memory(database, store)
    document = memory.remember(
        company_id="company-1",
        url="https://www.indiacode.nic.in/minimum-wages-act",
        title="Minimum Wages Act, 1948",
        text=PAGE,
        topic="labour",
    )
    assert document
    assert document["index_status"] == "failed"
    # The page is still kept, so the reading is not lost.
    assert KnowledgeDocumentRepository(database).find_for_company(
        document["id"], "company-1"
    )


def test_a_memory_without_a_store_does_not_raise(database):
    memory = LegalMemory(database, FakeEmbeddings(), None, settings=Settings())
    assert memory.recall(company_id="company-1", question="wages") == []
    with pytest.raises(VectorStoreUnavailable):
        memory.retrieval.search(query="wages", company_id="company-1")
