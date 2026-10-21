"""The agents: what they may say, and what the gate lets through.

The model is faked in these tests, so what is being tested is the part we
control: the source policy, the grounding rules, the deterministic verdict and
the quote check on the pages the research agent read.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.integrations.tinyfish import FetchBatch, FetchedPage, SearchHit
from app.services.agents.legal_researcher import LegalResearcher
from app.services.agents.recommender import Recommender
from app.services.agents.sources import allows, is_official_source_host, policy_for, topic_for
from app.services.agents.verifier import Verifier


class FakeAI:
    """A model that returns whatever the test gives it."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.model = "fake-model"
        self.calls: list[dict] = []

    @property
    def configured(self) -> bool:
        return True

    def complete_json(self, *, system: str, user: str) -> dict:
        self.calls.append({"system": system, "user": user})
        return self.payload


class FakeTinyFish:
    def __init__(self, hits: list[SearchHit], pages: dict[str, FetchedPage]) -> None:
        self.hits = hits
        self.pages = pages
        self.configured = True
        self.base_url = "https://fake.tinyfish.local"
        self.searched: list[str] = []
        self.fetched: list[str] = []

    def search(self, query, *, purpose=None, location=None, language=None, page=None):
        self.searched.append(query)
        return list(self.hits)

    def fetch(self, urls, *, purpose=None, output_format="markdown", timeout=None):
        self.fetched.extend(urls)
        batch = FetchBatch()
        for url in urls:
            if url in self.pages:
                batch.pages.append(self.pages[url])
        return batch


REQUIREMENT = {
    "id": "req-1",
    "clause_reference": "3.1",
    "title": "Minimum average annual turnover",
    "excerpt": (
        "The bidder shall have an average annual turnover of at least INR 5 crore "
        "during the last three financial years."
    ),
    "deadline_text": "Before the bid due date",
    "consequence_text": None,
    "category": "financial",
    "page_index": 3,
}

COMPANY = {
    "id": "company-1",
    "name": "Asha Infra Demo",
    "business_type": "private_limited",
    "regions": ["Maharashtra"],
    "products_services": ["Road construction"],
    "certifications": ["ISO 9001:2015"],
    "annual_turnover": 125000000,
    "employee_count": 240,
}

TENDER = {
    "id": "tender-1",
    "title": "Four-laning of a highway",
    "authority": "Demo State Infrastructure Authority",
    "reference_number": "DSIA/RFP/2026/ROAD-014",
    "deadline": datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc),
    "discovery_extracted": {},
}

DEADLINE = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


# ----------------------------------------------------------------- the policy


def test_only_official_sources_are_allowed() -> None:
    policy = policy_for("the contractor shall comply with all applicable labour laws")
    assert allows("https://labour.gov.in/acts/Code-on-Wages-2019.pdf", policy) is True
    assert allows("https://www.tielaw.in/article/abc", policy) is False
    assert allows("https://economictimes.indiatimes.com/news", policy) is False


def test_a_state_source_is_allowed_only_for_a_state_question() -> None:
    labour = policy_for("the contractor shall comply with the state minimum wages")
    assert allows("https://labour.maharashtra.gov.in/notification.pdf", labour) is True

    general = policy_for("the contractor shall comply with all applicable labour laws")
    assert allows("https://labour.maharashtra.gov.in/notification.pdf", general) is False


def test_a_clause_is_matched_to_a_topic() -> None:
    assert topic_for("wages shall be paid by the seventh of the month") == "labour"
    assert topic_for("GST at 18 percent shall be charged") == "tax"
    assert topic_for("the work shall be executed as per CPWD guidelines") == "pwd"
    assert topic_for("the contractor shall submit the methodology") == "general"


def test_the_official_host_check() -> None:
    assert is_official_source_host("labour.gov.in") is True
    assert is_official_source_host("www.labour.gov.in") is True
    assert is_official_source_host("tielaw.in") is False


# ------------------------------------------------------------ agent 1: propose


def test_a_proposal_that_rests_on_a_clause_is_grounded() -> None:
    ai = FakeAI(
        {
            "recommendations": [
                {
                    "kind": "document_to_prepare",
                    "title": "Attach the audited statements",
                    "claim": "Clause 3.1 requires a three-year average turnover of at least INR 5 crore.",
                    "action": "Attach the audited financial statements showing the average turnover.",
                    "acceptance_criteria": "The statements are signed by the chartered accountant.",
                    "requirement_refs": ["3.1"],
                    "owner_hint": "finance",
                    "due_hint_days_before_bid": 7,
                }
            ]
        }
    )
    results = Recommender(ai).propose(
        tender=TENDER,
        company=COMPANY,
        requirements=[REQUIREMENT],
        company_documents=[],
        evidence_decisions={},
        deadline=DEADLINE,
    )
    assert len(results) == 1
    result = results[0]
    assert result["grounding_status"] == "grounded"
    assert result["grounded_requirements"] == ["req-1"]
    # The due date is computed from the bid deadline, never taken from the model.
    assert result["suggested_due_at"].isoformat().startswith("2026-11-08")
    assert result["proposed_task"]["owner"] == "Finance"


def test_a_proposal_that_invents_a_figure_is_not_grounded() -> None:
    ai = FakeAI(
        {
            "recommendations": [
                {
                    "kind": "document_to_prepare",
                    "title": "Attach the statements",
                    "claim": "Clause 3.1 requires an average turnover of at least INR 25 crore.",
                    "requirement_refs": ["3.1"],
                }
            ]
        }
    )
    results = Recommender(ai).propose(
        tender=TENDER,
        company=COMPANY,
        requirements=[REQUIREMENT],
        company_documents=[],
        evidence_decisions={},
        deadline=DEADLINE,
    )
    assert results[0]["grounding_status"] == "unverified"
    assert results[0]["dropped_claims"]
    assert results[0]["proposed_task"] is None


def test_an_unsupported_figure_is_removed_but_the_advice_is_kept() -> None:
    """One invented number must not throw away the rest of the advice."""
    ai = FakeAI(
        {
            "recommendations": [
                {
                    "kind": "document_to_prepare",
                    "title": "Attach the audited statements",
                    "claim": (
                        "Clause 3.1 requires a three-year average turnover of at least "
                        "INR 5 crore. The statements must be certified within 30 days."
                    ),
                    "requirement_refs": ["3.1"],
                }
            ]
        }
    )
    results = Recommender(ai).propose(
        tender=TENDER,
        company=COMPANY,
        requirements=[REQUIREMENT],
        company_documents=[],
        evidence_decisions={},
        deadline=DEADLINE,
    )
    result = results[0]
    assert result["grounding_status"] == "grounded"
    assert "certified within 30 days" not in result["claim"]
    assert "at least INR 5 crore" in result["claim"]
    assert result["dropped_claims"]


def test_a_proposal_without_a_clause_is_not_grounded() -> None:
    ai = FakeAI(
        {
            "recommendations": [
                {
                    "kind": "document_to_prepare",
                    "title": "Attach your PF registration",
                    "claim": "Attach the PF registration and the shop licence.",
                    "requirement_refs": [],
                }
            ]
        }
    )
    results = Recommender(ai).propose(
        tender=TENDER,
        company=COMPANY,
        requirements=[REQUIREMENT],
        company_documents=[],
        evidence_decisions={},
        deadline=DEADLINE,
    )
    assert results[0]["grounding_status"] == "unverified"
    assert "does not rest on any stored clause" in results[0]["grounding_note"]


# ----------------------------------------------------------- agent 2: verify


def test_the_verdict_comes_from_our_record_not_the_model() -> None:
    ai = FakeAI(
        {
            "items": [
                {
                    "requirement_refs": ["3.1"],
                    "gap": "We have not attached the audited statements yet.",
                    "action": "Ask the chartered accountant for the statements.",
                    "acceptance_criteria": "The statements show the three-year average.",
                    "owner_hint": "finance",
                    "due_hint_days_before_bid": 10,
                }
            ]
        }
    )
    item = {
        "requirement_id": "req-1",
        "title": "Minimum average annual turnover",
        "clause_reference": "3.1",
        "excerpt": REQUIREMENT["excerpt"],
        "gate": "pass",
        "reason": "Audited statements confirm an average turnover of INR 12.5 crore.",
        "evidence_status": "confirmed",
        "evidence_document_title": "Audited financial statements FY2023-24 to FY2025-26",
    }
    results = Verifier(ai).verify(
        tender=TENDER,
        company=COMPANY,
        eligibility_items=[item],
        company_documents=[],
        deadline=DEADLINE,
    )
    assert len(results) == 1
    result = results[0]
    assert result["verdict"] == "pass"
    assert result["claim"].startswith("You clear this")
    assert "We have not attached the audited statements yet." in result["claim"]
    assert result["suggested_due_at"].isoformat().startswith("2026-11-05")


def test_an_unknown_verdict_is_never_reported_as_a_pass() -> None:
    ai = FakeAI(
        {
            "items": [
                {
                    "requirement_refs": ["3.1"],
                    "gap": "We do not know yet.",
                    "action": "Check the certificate.",
                }
            ]
        }
    )
    item = {
        "requirement_id": "req-1",
        "title": "Minimum average annual turnover",
        "clause_reference": "3.1",
        "excerpt": REQUIREMENT["excerpt"],
        "gate": "unknown",
        "reason": "No evidence confirmed yet.",
        "evidence_status": "none",
    }
    results = Verifier(ai).verify(
        tender=TENDER,
        company=COMPANY,
        eligibility_items=[item],
        company_documents=[],
        deadline=DEADLINE,
    )
    assert results[0]["verdict"] == "unknown"
    assert "We cannot tell yet" in results[0]["claim"]


# ------------------------------------------------------- agent 3: legal research


def test_a_legal_source_must_be_quoted_from_the_page_that_was_read() -> None:
    page_text = (
        "The Code on Wages, 2019\n\n"
        "18. Equal remuneration: No employer shall pay remuneration for work "
        "performed by any employee at a rate less than the minimum wages."
    )
    ai = FakeAI(
        {
            "provisions": [
                {
                    "quote": "No employer shall pay remuneration for work performed by any employee at a rate less than the minimum wages.",
                    "section": "18",
                    "instrument": "Code on Wages, 2019",
                },
                {
                    "quote": "Every employer must pay double the minimum wage after eight hours.",
                    "section": "18",
                },
            ],
            "applies_to_us": "This applies to the contractor's site staff.",
            "must_hold": ["Wage registers and a minimum wage notification for the state"],
            "next_action": "Attach the state minimum wage notification and the wage register.",
        }
    )
    client = FakeTinyFish(
        hits=[
            SearchHit(
                title="Code on Wages, 2019",
                url="https://labour.gov.in/acts/Code-on-Wages-2019.pdf",
                snippet="",
                site_name="labour.gov.in",
            ),
            SearchHit(
                title="A law firm explains the Code on Wages",
                url="https://www.tielaw.in/article/code-on-wages",
                snippet="",
                site_name="tielaw.in",
            ),
        ],
        pages={
            "https://labour.gov.in/acts/Code-on-Wages-2019.pdf": FetchedPage(
                url="https://labour.gov.in/acts/Code-on-Wages-2019.pdf",
                final_url=None,
                title="Code on Wages, 2019",
                description=None,
                text=page_text,
            )
        },
    )
    results = LegalResearcher(ai=ai, client=client).research(
        company=COMPANY,
        tender=TENDER,
        requirement={
            **REQUIREMENT,
            "title": "Minimum wages and equal remuneration",
            "excerpt": "The contractor shall comply with all applicable labour laws.",
        },
        company_documents=[],
        retrieved_at=DEADLINE,
    )

    # Only the official page was read, and only the verbatim sentence survived.
    assert client.fetched == ["https://labour.gov.in/acts/Code-on-Wages-2019.pdf"]
    assert len(results) == 1
    assert results[0]["source_url"] == "https://labour.gov.in/acts/Code-on-Wages-2019.pdf"
    assert "No employer shall pay remuneration" in results[0]["quote"]
    assert results[0]["section"] == "18"
    assert results[0]["retrieved_at"] == DEADLINE
    assert "not legal advice" in results[0]["disclaimer"]


def test_a_clause_with_no_official_page_yields_nothing() -> None:
    ai = FakeAI({"provisions": [], "must_hold": [], "next_action": None})
    client = FakeTinyFish(
        hits=[
            SearchHit(
                title="A blog about labour law",
                url="https://blog.example.com/labour",
                snippet="",
                site_name="blog.example.com",
            )
        ],
        pages={},
    )
    results = LegalResearcher(ai=ai, client=client).research(
        company=COMPANY,
        tender=TENDER,
        requirement=REQUIREMENT,
        company_documents=[],
        retrieved_at=DEADLINE,
    )
    assert results == []
    # The blog is never read, and the body that owns the law is tried instead.
    assert "https://blog.example.com/labour" not in client.fetched
    assert all("blog.example.com" not in url for url in client.fetched)
