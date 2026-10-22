"""What the agents read from the index, and the legal agent's memory.

The point of these tests is the order of operations: the legal agent must
look in the memory before it goes to the web, and the agents must only ever
read their own company's passages.
"""

from __future__ import annotations

from datetime import datetime

from app.core.config import Settings
from app.core.database import Database
from app.services.agent_context import (
    clause_passages,
    evidence_passages,
    format_clause_context,
    format_evidence_context,
)
from app.services.agents.legal_researcher import LegalResearcher
from app.services.retrieval import SCOPE_COMPANY_EVIDENCE, SCOPE_TENDER, RetrievalService
from app.services.vector_store import ScoredPassage


class FakeStore:
    """A stand-in for the vector store that records the filters it was given."""

    def __init__(self) -> None:
        self.filters: list[dict] = []

    def health(self):
        return {"status": "ok"}

    def search(self, vector, *, limit=8, filters=None, score_threshold=None):
        self.filters.append(filters or {})
        scope = (filters or {}).get("must", {}).get("scope")
        if scope == SCOPE_TENDER:
            payload = {
                "document_id": "tender-doc",
                "document_title": "RFP",
                "company_id": "company-1",
                "tender_id": "tender-1",
                "page_index": 3,
                "printed_page": "3",
                "clause_number": "3.1",
                "text": "3.1 The bidder shall have an average annual turnover of INR 5 crore.",
                "scope": SCOPE_TENDER,
            }
        else:
            payload = {
                "document_id": "company-doc",
                "document_title": "ISO 9001 certificate",
                "company_id": "company-1",
                "page_index": 1,
                "printed_page": "1",
                "clause_number": None,
                "text": "ISO 9001:2015 certificate, valid until 31 March 2027.",
                "scope": SCOPE_COMPANY_EVIDENCE,
            }
        return [ScoredPassage(id="1", score=0.8, payload=payload)]


class FakeEmbeddings:
    name = "fake"
    model = "fake-model"
    dimension = 4
    available = True

    def embed(self, texts):
        return [[0.1] * 4 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 4


REQUIREMENTS = [
    {
        "id": "requirement-1",
        "title": "Turnover",
        "excerpt": "The bidder shall have an average annual turnover of INR 5 crore.",
    }
]


def make_retrieval(database) -> tuple[RetrievalService, FakeStore]:
    store = FakeStore()
    return RetrievalService(database, FakeEmbeddings(), store, settings=Settings()), store


def test_the_clauses_are_read_from_the_tender_scope(database):
    retrieval, store = make_retrieval(database)
    found = clause_passages(
        retrieval,
        company_id="company-1",
        tender_id="tender-1",
        requirements=REQUIREMENTS,
    )
    assert found
    assert store.filters[0]["must"]["scope"] == SCOPE_TENDER
    assert store.filters[0]["must"]["tender_id"] == "tender-1"
    assert store.filters[0]["must"]["company_id"] == "company-1"


def test_the_evidence_is_read_from_the_company_scope(database):
    retrieval, store = make_retrieval(database)
    found = evidence_passages(
        retrieval, company_id="company-1", requirements=REQUIREMENTS
    )
    assert found
    assert store.filters[0]["must"]["scope"] == SCOPE_COMPANY_EVIDENCE
    assert store.filters[0]["must"]["company_id"] == "company-1"


def test_the_context_carries_the_source_of_each_passage(database):
    retrieval, _store = make_retrieval(database)
    found = clause_passages(
        retrieval,
        company_id="company-1",
        tender_id="tender-1",
        requirements=REQUIREMENTS,
    )
    text = format_clause_context(found)
    assert "page 3" in text
    assert "clause 3.1" in text
    assert "turnover" in text

    evidence = format_evidence_context(
        evidence_passages(retrieval, company_id="company-1", requirements=REQUIREMENTS)
    )
    assert "ISO 9001 certificate" in evidence


def test_without_an_index_there_is_no_context(database):
    assert clause_passages(None, company_id="c", tender_id="t", requirements=REQUIREMENTS) == {}
    assert evidence_passages(None, company_id="c", requirements=REQUIREMENTS) == []
    assert "not available" in format_clause_context({})


# ----------------------------------------------------------------- the legal agent


class FakePage:
    def __init__(self, url: str, title: str, text: str) -> None:
        self.url = url
        self.title = title
        self.text = text


class FakeBatch:
    def __init__(self, pages: list[FakePage]) -> None:
        self.pages = pages


class FakeTinyFish:
    """Records whether the web was used."""

    def __init__(self, pages: list[FakePage] | None = None) -> None:
        self.configured = True
        self.pages = pages or []
        self.searches: list[str] = []

    def search(self, query, purpose=None, language=None):
        self.searches.append(query)
        return []

    def fetch(self, urls, purpose=None, output_format=None):
        return FakeBatch(self.pages)


class FakeAI:
    configured = True
    model = "fake-model"

    def complete_json(self, *, system: str, user: str):
        return {
            "provisions": [
                {
                    "quote": "Every employer shall pay the wages to the workers",
                    "section": "3",
                    "instrument": "Minimum Wages Act, 1948",
                }
            ],
            "applies_to_us": "The company employs workers on site.",
            "must_hold": ["Wage registers"],
            "next_action": "Check the wage registers.",
        }


class FakeMemory:
    """A memory that already holds a reading."""

    def __init__(self, pages) -> None:
        self.pages = pages
        self.remembered: list[dict] = []

    def recall(self, *, company_id, question, topic=None, **kwargs):
        return list(self.pages)

    def remember(self, **kwargs):
        self.remembered.append(kwargs)
        return None


def test_the_legal_agent_uses_the_memory_before_the_web(database):
    from app.services.legal_memory import RememberedPage

    page = RememberedPage(
        url="https://www.indiacode.nic.in/minimum-wages-act",
        title="Minimum Wages Act, 1948",
        text=(
            "Minimum Wages Act, 1948\n"
            "3. Payment of wages.- Every employer shall pay the wages to the workers "
            "on or before the seventh day of the month."
        ),
        retrieved_at=datetime(2026, 10, 1),
    )
    memory = FakeMemory([page])
    tinyfish = FakeTinyFish([FakePage("https://example.gov.in/law", "Law", "text")])
    researcher = LegalResearcher(ai=FakeAI(), client=tinyfish)

    results = researcher.research(
        company={"id": "company-1", "name": "Asha Infra"},
        tender={"title": "Road work", "authority": "Authority"},
        requirement={
            "id": "requirement-1",
            "title": "Wages",
            "excerpt": "The contractor shall pay the minimum wages.",
        },
        company_documents=[],
        memory=memory,
    )

    assert results
    assert results[0]["source_url"] == "https://www.indiacode.nic.in/minimum-wages-act"
    assert "stored reading" in results[0]["read_from"]
    # The web was not touched, and nothing new was stored.
    assert tinyfish.searches == []
    assert memory.remembered == []


def test_the_legal_agent_reads_the_web_when_the_memory_is_empty(database):
    text = (
        "Minimum Wages Act, 1948\n"
        "3. Payment of wages.- Every employer shall pay the wages to the workers "
        "on or before the seventh day of the month."
    )
    memory = FakeMemory([])
    tinyfish = FakeTinyFish([FakePage("https://www.indiacode.nic.in/wages", "Act", text)])
    researcher = LegalResearcher(ai=FakeAI(), client=tinyfish)

    results = researcher.research(
        company={"id": "company-1", "name": "Asha Infra"},
        tender={"title": "Road work", "authority": "Authority"},
        requirement={
            "id": "requirement-1",
            "title": "Wages",
            "excerpt": "The contractor shall pay the minimum wages.",
        },
        company_documents=[],
        memory=memory,
    )

    assert results
    assert "read now" in results[0]["read_from"]
    assert tinyfish.searches
    # The page it read is kept for next time.
    assert memory.remembered
    assert memory.remembered[0]["url"] == "https://www.indiacode.nic.in/wages"
