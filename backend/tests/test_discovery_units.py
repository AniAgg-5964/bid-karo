from __future__ import annotations

from datetime import date

from app.repositories.discovery import DiscoveryTenderRepository
from app.services import tender_extraction as extraction
from app.services.relevance import company_terms, has_any_terms, score_tender


# --------------------------------------------------------------- source type
def test_classify_source_flags_official_government_hosts() -> None:
    assert extraction.classify_source("https://eprocure.gov.in/eprocure/app") == "official"
    assert extraction.classify_source("https://mahatenders.gov.in/portal") == "official"
    assert extraction.classify_source("https://some.state.nic.in/tender") == "official"
    assert extraction.classify_source("https://www.tender247.com/tenders/x") == "aggregator"
    assert extraction.classify_source("not a url") == "unknown"


def test_listing_page_detection() -> None:
    assert extraction.is_listing_page("3141 Roads Construction tenders in Maharashtra 2026")
    assert extraction.is_listing_page("Latest 2026 Soil Survey Tenders In India")
    assert extraction.is_listing_page("Road Construction Tenders in Maharashtra 2026")
    assert extraction.is_listing_page("Tender Notices for road works")
    assert extraction.is_listing_page("Tender Notice | PMRDA Pune - Official Tenders & e-Bids")
    assert extraction.is_listing_page("Tenders by Organisation")
    assert extraction.is_listing_page("Tenders - Public Private Partneships in India")
    assert extraction.is_listing_page("eProcurement System Government of India")
    assert extraction.is_listing_page("Mahatenders.gov.in")
    assert not extraction.is_listing_page("Tender for Asphalt Road Construction Work At Various Places")
    assert not extraction.is_listing_page("Highway road construction tender in Maharashtra")
    assert not extraction.is_listing_page("Tender Notice no 35 Appointment of Contractor for Supply")


def test_has_many_dated_rows_flags_dated_tables() -> None:
    table = "\n".join(
        [
            "| S.N. | Tender Name | Closing Date |",
            "| --- | --- | --- |",
            "| 1 | Road work at Ward 1 | 22 Sep 2026 |",
            "| 2 | Road work at Ward 2 | 22 Sep 2026 |",
            "| 3 | Road work at Ward 3 | 22 Sep 2026 |",
            "| 4 | Road work at Ward 4 | 22 Sep 2026 |",
        ]
    )
    assert extraction.has_many_dated_rows(table)
    assert not extraction.has_many_dated_rows("Tender closes on 22 Sep 2026")


def test_blocked_hosts_and_award_notices() -> None:
    assert extraction.is_blocked_host("https://www.facebook.com/groups/1/posts/2")
    assert extraction.is_blocked_host("https://m.facebook.com/groups/1")
    assert not extraction.is_blocked_host("https://mahatenders.gov.in/tender/1")

    assert extraction.is_award_notice("Another major highway maintenance project awarded in Pune")
    assert extraction.is_award_notice("Tender cancelled due to administrative reasons")
    assert not extraction.is_award_notice("Tender for highway maintenance work")
    assert extraction.is_non_tender("Road Construction Tenders in Maharashtra 2026")


def test_extract_table_rows_reads_open_tenders_only() -> None:
    text = "\n".join(
        [
            "| S.N. | For FY | Tender Name | Publish Date | Closing Date | Download |",
            "| --- | --- | --- | --- | --- | --- |",
            "| 1 | 2026-2027 | Appointment of Project Management Consultant for Hinjewadi | 7 Sep 2026 | 22 Sep 2026 | Download |",
            "| 2 | 2026-2027 | Construction of cement concrete road at Ward 47 Pune | 1 Oct 2026 | 15 Nov 2026 | Download |",
        ]
    )
    rows = extraction.extract_table_rows(text, today=date(2026, 10, 20))

    assert len(rows) == 1
    assert "cement concrete road" in rows[0].title
    assert rows[0].deadline == "2026-11-15"
    assert rows[0].published == "2026-10-01"
    assert "Ward 47" in rows[0].excerpt


def test_extract_table_rows_ignores_tables_without_closing_date() -> None:
    text = "\n".join(
        [
            "| Sr No. | Tenders | Date | Download PDF |",
            "| --- | --- | --- | --- |",
            "| 1 | Empanelment of Transaction Advisers | 05 Feb 2026 | |",
        ]
    )
    assert extraction.extract_table_rows(text, today=date(2026, 10, 20)) == []


def test_dedupe_key_is_stable_and_url_based() -> None:
    first = extraction.dedupe_key("https://x.com/a/b/", "Title A", "site")
    second = extraction.dedupe_key("https://x.com/a/b", "Different title", "other")
    third = extraction.dedupe_key("https://x.com/a/c", "Title A", "site")
    assert first == second  # path normalised, so title does not matter
    assert first != third


def test_dedupe_key_keeps_tender_query_but_drops_tracking() -> None:
    a = extraction.dedupe_key("https://eprocure.gov.in/eprocure/app?component=view&sp=AAA", "t")
    b = extraction.dedupe_key("https://eprocure.gov.in/eprocure/app?component=view&sp=BBB", "t")
    c = extraction.dedupe_key(
        "https://eprocure.gov.in/eprocure/app?component=view&sp=AAA&utm_source=newsletter", "t"
    )
    assert a != b  # different tender id in the query string
    assert a == c  # tracking parameter ignored


# ------------------------------------------------------------------ parsing
def test_parse_date_token_accepts_common_indian_formats() -> None:
    assert extraction.parse_date_token("15-12-2026") == date(2026, 12, 15)
    assert extraction.parse_date_token("5/6/2026") == date(2026, 6, 5)
    assert extraction.parse_date_token("15 Dec 2026") == date(2026, 12, 15)
    assert extraction.parse_date_token("Dec 15, 2026") == date(2026, 12, 15)
    assert extraction.parse_date_token("2026-12-15") == date(2026, 12, 15)
    assert extraction.parse_date_token("32-13-2026") is None


def test_extract_fields_pulls_deadline_reference_value_location_with_evidence() -> None:
    text = (
        "Tender No: PWD/2026/ROAD-114\n"
        "Organisation: Maharashtra Public Works Department\n"
        "Estimated Cost: INR 12,50,000\n"
        "Last Date of Submission: 15-12-2026\n"
        "Work Location: Pune, Maharashtra\n"
    )

    result = extraction.extract_fields("Road resurfacing work", "snippet", text)

    assert result.reference_number == "PWD/2026/ROAD-114"
    assert result.deadline == "2026-12-15"
    assert result.deadline_raw == "15-12-2026"
    assert result.value_amount == 1_250_000
    assert result.value_currency == "INR"
    assert result.location is not None and "Pune" in result.location
    assert result.authority is not None and "Public Works" in result.authority
    # Every extracted field must carry the verbatim excerpt it came from.
    for field in ("reference_number", "deadline", "value", "location", "authority"):
        assert field in result.evidence
        assert result.evidence[field]


def test_extract_fields_never_invents_missing_values() -> None:
    result = extraction.extract_fields("Some notice", "no useful details here", "")
    assert result.deadline is None
    assert result.value_amount is None
    assert result.reference_number is None
    assert result.evidence == {}


def test_parse_value_units() -> None:
    assert extraction._parse_amount("INR 2.5 crore") == 25_000_000
    assert extraction._parse_amount("Rs. 4 lakh") == 400_000
    assert extraction._parse_amount("INR 50,000") == 50_000


def test_reference_extraction_ignores_prose_and_requires_a_digit() -> None:
    prose = extraction.extract_fields("Latest tenders", "Tender Notices for road works", "")
    assert prose.reference_number is None

    real = extraction.extract_fields("x", "y", "Tender No: ABC/2026/77")
    assert real.reference_number == "ABC/2026/77"


def test_value_falls_back_to_currency_amount_in_snippet() -> None:
    result = extraction.extract_fields("Road work", "Closes Oct 15, 2026 · ₹ 43.90 Crore", "")
    assert result.value_amount == 439_000_000
    assert result.value_currency == "INR"
    assert result.evidence["value"] == "₹ 43.90 Crore"


def test_deadline_understands_closes_label() -> None:
    result = extraction.extract_fields("x", "Closes Oct 15, 2026", "")
    assert result.deadline == "2026-10-15"


def test_location_prefers_title_over_unrelated_page_states() -> None:
    result = extraction.extract_fields(
        "Road work in Maharashtra",
        "Tender at Trombay",
        "Kerala flood relief supplies were also discussed in Kerala.",
    )
    assert result.location == "Maharashtra"


# ---------------------------------------------------------------- relevance
COMPANY = {
    "sectors": ["Infrastructure"],
    "products_services": ["Road construction"],
    "regions": ["Maharashtra"],
    "preferences": {"keywords": ["highway"], "sectors": [], "regions": []},
}


def test_company_terms_dedupes_and_filters_short_terms() -> None:
    terms = company_terms({"preferences": {"keywords": ["a", "highway", "highway"]}})
    assert terms["keywords"] == ["highway"]
    assert has_any_terms(COMPANY) is True
    assert has_any_terms({"preferences": {}}) is False


def test_score_tender_full_match_scores_high() -> None:
    relevance = score_tender(
        COMPANY,
        title="Highway road construction tender in Maharashtra",
        snippet="",
    )
    assert relevance.score > 0.8
    assert "highway" in relevance.matched_terms
    assert any("region" in reason for reason in relevance.reasons)


def test_score_tender_unrelated_source_scores_zero() -> None:
    relevance = score_tender(COMPANY, title="Supply of office furniture", snippet="chairs and desks")
    assert relevance.score == 0.0
    assert relevance.reasons


def test_score_tender_partial_match_is_between() -> None:
    relevance = score_tender(COMPANY, title="Road construction tender in Maharashtra", snippet="")
    assert 0.0 < relevance.score < 1.0


def test_ensure_does_not_downgrade_a_fetched_record(database) -> None:
    repository = DiscoveryTenderRepository(database)
    stored, created = repository.upsert(
        "company-1",
        "key-1",
        {"source_url": "https://example.gov.in/t/1", "fetch_status": "fetched", "content_hash": "abc"},
    )
    assert created is True

    kept, created_again = repository.ensure(
        "company-1",
        "key-1",
        {"source_url": "https://example.gov.in/t/1", "fetch_status": "not_fetched", "content_hash": None},
    )
    assert created_again is False
    assert kept["id"] == stored["id"]
    assert kept["fetch_status"] == "fetched"
    assert kept["content_hash"] == "abc"
