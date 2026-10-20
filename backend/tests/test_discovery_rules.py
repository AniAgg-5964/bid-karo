"""Phase 5 discovery rules: what a run may list, and how it is matched.

The rules under test:

* a notice is read out of a search result, a table row or a page;
* the closing date is never a publish date, and an expired tender is never
  listed;
* a tender is listed when the work matches the company's work types, and the
  region only decides the order;
* notices outside India are not listed;
* every source is typed so the user knows what kind of page it is.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.dependencies import get_discovery_client
from app.integrations.tinyfish import FetchedPage, SearchHit
from app.main import app
from app.services import tender_extraction as extraction
from app.services.relevance import score_tender, term_variants

OFFICIAL_URL = "https://mahatenders.gov.in/tender/road-114"
LISTING_URL = "https://www.tenderdetail.com/indian-tender/road-construction-tenders"

PROFILE = {
    "sectors": ["Infrastructure"],
    "products_services": ["Road construction"],
    "regions": ["Maharashtra", "Karnataka"],
    "preferences": {"keywords": ["highway"], "sectors": [], "regions": []},
}


class FakeTinyFish:
    def __init__(self, *, hits=None, pages=None, errors=None) -> None:
        self.configured = True
        self.base_url = "https://fake.tinyfish.local"
        self.hits = hits or []
        self.pages = pages or {}
        self.errors = errors or {}
        self.search_calls: list[str] = []

    def search(self, query, *, purpose=None, location=None, language=None, page=None):
        self.search_calls.append(query)
        return list(self.hits)

    def fetch(self, urls, *, purpose=None, output_format="markdown", timeout=None):
        batch = type("Batch", (), {"pages": [], "errors": {}})()
        for url in urls:
            if url in self.errors:
                batch.errors[url] = self.errors[url]
            elif url in self.pages:
                batch.pages.append(self.pages[url])
        return batch


def configure(fake: FakeTinyFish) -> None:
    app.dependency_overrides[get_discovery_client] = lambda: fake


def set_profile(client: TestClient, headers: dict[str, str]) -> None:
    response = client.patch("/api/companies/me", headers=headers, json=PROFILE)
    assert response.status_code == 200, response.text


# --------------------------------------------------------------- term matching


def test_term_variants_cover_the_common_way_of_writing_the_same_work() -> None:
    assert "road construction" in term_variants("road construction")
    assert "construction of road" in term_variants("road construction")
    assert "roads" in term_variants("road")
    # The reverse is never applied, so "electronics" cannot match "electronic".
    assert "electronic" not in term_variants("electronics")


def test_matching_uses_word_boundaries_and_variants() -> None:
    company = {
        "products_services": ["Road construction"],
        "sectors": [],
        "regions": ["Maharashtra"],
        "preferences": {"keywords": []},
    }
    written = score_tender(company, title="Construction of road at Ward 47")
    assert written.work_type_match is True
    assert any("road construction" in reason for reason in written.reasons)

    # A term the company wrote in the singular also matches the plural.
    road_only = {
        "products_services": ["Road"],
        "sectors": [],
        "regions": [],
        "preferences": {"keywords": []},
    }
    plural = score_tender(road_only, title="Roads and highways in Maharashtra")
    assert plural.work_type_match is True

    unrelated = score_tender(company, title="Supply of office furniture in Pune")
    assert unrelated.work_type_match is False
    assert unrelated.region_match is False


# ------------------------------------------------------------- closing dates


def test_a_publish_date_is_never_used_as_the_closing_date() -> None:
    facts = extraction.read_close_date(
        "Published 29-Sep-2026. Last date of submission: 22-Oct-2026 for the work."
    )
    assert facts.deadline is not None
    assert facts.deadline.isoformat() == "2026-10-22"
    assert facts.published is not None
    assert facts.published.isoformat() == "2026-09-29"


def test_a_notice_with_only_a_publish_date_has_no_closing_date() -> None:
    facts = extraction.read_close_date("Tender published 29-Sep-2026 for road work")
    assert facts.deadline is None


def test_an_unlabelled_row_uses_the_later_date_as_the_closing_date() -> None:
    cells = ["354052260807", "08-Aug-2026", "21-Aug-2026", "India / UTTAR PRADESH"]
    row = extraction.infer_row_tender(cells, today=extraction.date(2026, 1, 1))
    assert row is None  # no work description in the row
    cells = [
        "223052260929",
        "29-Sep-2026",
        "22-Oct-2026",
        "India / DELHI",
        "Tender For Toilet Bathroom Renovation and Painting civil work",
    ]
    row = extraction.infer_row_tender(cells, today=extraction.date(2026, 1, 1))
    assert row is not None
    assert row.deadline == "2026-10-22"
    assert row.published == "2026-09-29"
    assert "Toilet Bathroom" in row.title


def test_a_headerless_table_still_yields_tenders() -> None:
    table = "\n".join(
        [
            "|  |  |  |  |  |  |",
            "| --- | --- | --- | --- | --- | --- |",
            "| 223052260929 | 29-Sep-2026 | 22-Oct-2026 | India / DELHI | Refer Document. "
            "| Tender For Toilet Bathroom Renovation and Painting civil work | View Tender |",
        ]
    )
    rows = extraction.extract_table_rows(table, today=extraction.date(2026, 1, 1))
    assert len(rows) == 1
    assert rows[0].deadline == "2026-10-22"
    assert "Toilet Bathroom" in rows[0].title


def test_a_page_with_a_closing_date_is_not_treated_as_a_listing() -> None:
    text = (
        "# Pune Road Surface Marking Project\n\n"
        "* Opening DateAug 03, 2026\n* Closing DateAug 17, 2026\n\n"
        "| Item | Date |\n| --- | --- |\n| a | 01-08-2026 |\n| b | 02-08-2026 |\n"
    )
    assert extraction.looks_like_single_notice(text) is True


def test_foreign_notices_are_recognised() -> None:
    assert extraction.is_foreign_notice("Tender For Athletic Fields, United States") is True
    assert extraction.is_foreign_notice("Tender for road work, India / DELHI") is False
    assert extraction.is_foreign_notice("Road work worth USD 1,00,000") is True


def test_source_kinds_separate_portals_from_authorities_and_aggregators() -> None:
    assert extraction.source_kind("https://etenders.gov.in/xyz") == "official_portal"
    assert extraction.source_kind("https://mmrda.maharashtra.gov.in/notice") == "authority"
    assert extraction.source_kind("https://www.tenderdetail.com/list") == "aggregator"


# ----------------------------------------------------------------- end to end


def test_a_notice_inside_a_search_result_is_listed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """The page is a category page, but the search result describes one work."""
    set_profile(client, auth_headers)
    hits = [
        SearchHit(
            title="3141 Roads Construction tenders in Maharashtra 2026",
            url=LISTING_URL,
            snippet=(
                "Tender for Asphalt Road Construction Work At Various Places Under Ward No. 47. "
                "Closes Nov 11, 2026 - 25 days left - Rs. 42.34 Lakh. Government Department."
            ),
            site_name="www.tenderdetail.com",
            position=1,
        )
    ]
    configure(FakeTinyFish(hits=hits, pages={}))

    payload = client.post("/api/discovery/run", headers=auth_headers).json()

    assert payload["total"] == 1
    item = payload["items"][0]
    assert "Asphalt Road Construction" in item["title"]
    assert item["extracted"]["deadline"] == "2026-11-11"
    assert item["extracted_from"] == "search_result"
    assert item["relevance"]["work_type_match"] is True
    assert payload["run"]["stats"]["notices_from_search_results"] == 1


def test_an_expired_notice_is_never_listed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    set_profile(client, auth_headers)
    hits = [
        SearchHit(
            title="Road construction tender in Maharashtra",
            url="https://www.tender247.com/tenders/road-old",
            snippet="Tender for Asphalt Road Construction Work at Ward 21. Closes Jan 05, 2026.",
            site_name="www.tender247.com",
            position=1,
        )
    ]
    configure(FakeTinyFish(hits=hits, pages={}))

    payload = client.post("/api/discovery/run", headers=auth_headers).json()

    assert payload["total"] == 0
    assert payload["run"]["stats"]["skipped_closed"] == 1


def test_a_tender_in_another_state_is_listed_and_ranked_below(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    set_profile(client, auth_headers)
    hits = [
        SearchHit(
            title="Road construction work in Gujarat",
            url="https://www.tender247.com/tenders/road-gujarat",
            snippet="Tender for Road Construction of Bridge on NH-48. Closes Dec 05, 2026.",
            site_name="www.tender247.com",
            position=1,
        ),
        SearchHit(
            title="Road construction work in Maharashtra",
            url="https://www.tender247.com/tenders/road-maharashtra",
            snippet="Tender for Road Construction of Bridge on NH-44. Closes Dec 06, 2026.",
            site_name="www.tender247.com",
            position=2,
        ),
    ]
    configure(FakeTinyFish(hits=hits, pages={}))

    payload = client.post("/api/discovery/run", headers=auth_headers).json()

    assert payload["total"] == 2
    first, second = payload["items"]
    assert first["relevance"]["region_match"] is True
    assert second["relevance"]["region_match"] is False
    assert second["relevance"]["work_type_match"] is True


def test_a_notice_without_a_closing_date_is_not_a_tender(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    set_profile(client, auth_headers)
    hits = [
        SearchHit(
            title="Highway road construction contractor directory in Maharashtra",
            url="https://www.tender247.com/tenders/road-directory",
            snippet="Directory of highway road construction contractors in Maharashtra.",
            site_name="www.tender247.com",
            position=1,
        )
    ]
    configure(FakeTinyFish(hits=hits, pages={}))

    payload = client.post("/api/discovery/run", headers=auth_headers).json()

    assert payload["total"] == 0
    assert payload["run"]["stats"]["skipped_no_deadline"] == 1


def test_a_foreign_notice_is_not_listed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    set_profile(client, auth_headers)
    hits = [
        SearchHit(
            title="Road construction tender for a community college",
            url="https://www.tendernews.com/tender/us-1",
            snippet=(
                "Tender For Athletic Fields at Reid State Technical Community College, "
                "United States. Closes Dec 05, 2026."
            ),
            site_name="www.tendernews.com",
            position=1,
        )
    ]
    configure(FakeTinyFish(hits=hits, pages={}))

    payload = client.post("/api/discovery/run", headers=auth_headers).json()

    assert payload["total"] == 0
    assert payload["run"]["stats"]["skipped_foreign"] == 1
