"""The deterministic gate: what a model may say, and what it may not.

These tests pin the two rule sets. If one of them changes, a claim that was
being refused would start to pass, so they are written as behaviour, not
implementation.
"""

from __future__ import annotations

from app.services.agents.gate import check_grounding, check_quote

PAGE = (
    "Section 3 - Eligibility Criteria. The bidder shall have an average annual "
    "turnover of at least INR 5 crore during the last three financial years. "
    "A bid security of INR 2,00,000 must be submitted with the bid."
)


def test_a_quote_on_the_page_passes() -> None:
    verdict = check_quote(
        "The bidder shall have an average annual turnover of at least INR 5 crore",
        page_text=PAGE,
    )
    assert verdict.status == "verified"
    assert verdict.reason is None


def test_whitespace_and_typography_do_not_matter() -> None:
    verdict = check_quote(
        "The  bidder   shall have an average\nannual turnover",
        page_text=PAGE,
    )
    assert verdict.status == "verified"


def test_a_paraphrase_does_not_pass() -> None:
    verdict = check_quote(
        "The bidder must show average turnover of at least five crore rupees",
        page_text=PAGE,
    )
    assert verdict.status == "unverified"
    assert "not found verbatim" in (verdict.reason or "")


def test_a_quote_from_another_page_does_not_pass() -> None:
    verdict = check_quote(
        "A bid security of INR 2,00,000 must be submitted with the bid",
        page_text="Page three is about eligibility only.",
    )
    assert verdict.status == "unverified"


def test_a_missing_page_is_reported() -> None:
    verdict = check_quote("A quote long enough to be checked at all", page_text=None)
    assert verdict.status == "unverified"
    assert "does not exist" in (verdict.reason or "")


def test_an_ocr_quote_needs_a_human() -> None:
    verdict = check_quote(
        "The bidder shall have an average annual turnover of at least INR 5 crore",
        page_text=PAGE,
        text_source="ocr",
    )
    assert verdict.status == "needs_review"
    assert "OCR" in (verdict.reason or "")


def test_a_short_quote_is_not_checked() -> None:
    verdict = check_quote("too short", page_text=PAGE)
    assert verdict.status == "unverified"
    assert "too short" in (verdict.reason or "")


# ------------------------------------------------------------------- grounding

REQUIREMENTS = {
    "3-1": {
        "title": "Minimum average annual turnover",
        "excerpt": "The bidder shall have an average annual turnover of at least INR 5 crore",
        "obligation": "Show a three-year average turnover of at least INR 5 crore.",
        "deadline_text": "Before the bid due date",
        "consequence_text": None,
    }
}


def test_a_recommendation_must_rest_on_a_stored_clause() -> None:
    check = check_grounding(
        "Attach the audited statements for clause 3.1.",
        requirement_ids=["3-1"],
        known_requirements=REQUIREMENTS,
    )
    assert check.grounded is True
    assert check.grounded_requirements == ["3-1"]
    assert check.reason is None


def test_a_recommendation_without_a_clause_is_refused() -> None:
    check = check_grounding(
        "Attach your PF registration and a shop licence.",
        requirement_ids=["3-1"],
        known_requirements=REQUIREMENTS,
    )
    assert check.grounded is False
    assert "does not rest on any stored clause" in (check.reason or "")


def test_a_recommendation_may_not_invent_a_figure() -> None:
    check = check_grounding(
        "Attach audited statements showing turnover of at least INR 25 crore for clause 3.1.",
        requirement_ids=["3-1"],
        known_requirements=REQUIREMENTS,
    )
    assert check.grounded is False
    assert check.dropped_claims
    assert "not in the clause" in (check.reason or "")


def test_a_figure_from_the_tender_record_is_allowed() -> None:
    check = check_grounding(
        "The contract value of INR 25 crore is recorded in the tender for clause 3.1.",
        requirement_ids=["3-1"],
        known_requirements=REQUIREMENTS,
        stored_fields={"value_amount": 250000000},
    )
    assert check.grounded is True
