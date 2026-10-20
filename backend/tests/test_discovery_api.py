from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.dependencies import get_discovery_client
from app.integrations.tinyfish import FetchBatch, FetchedPage, SearchHit
from app.main import app
from tests.conftest import register_and_verify

OFFICIAL_URL = "https://mahatenders.gov.in/tender/road-114"
AGGREGATOR_URL = "https://www.tender247.com/tenders/office-furniture"

PROFILE = {
    "sectors": ["Infrastructure"],
    "products_services": ["Road construction"],
    "regions": ["Maharashtra"],
    "preferences": {"keywords": ["highway"], "sectors": [], "regions": []},
}


class FakeTinyFish:
    """Stand-in for TinyFishClient so tests never touch the network."""

    def __init__(self, *, configured: bool = True, hits=None, pages=None, errors=None) -> None:
        self.configured = configured
        self.base_url = "https://fake.tinyfish.local"
        self.hits = hits if hits is not None else []
        self.pages = pages or {}
        self.errors = errors or {}
        self.search_calls: list[str] = []
        self.fetch_calls: list[list[str]] = []

    def search(self, query, *, purpose=None, location=None, language=None, page=None):
        self.search_calls.append(query)
        return list(self.hits)

    def fetch(self, urls, *, purpose=None, output_format="markdown", timeout=None):
        self.fetch_calls.append(list(urls))
        batch = FetchBatch()
        for url in urls:
            if url in self.errors:
                batch.errors[url] = self.errors[url]
            elif url in self.pages:
                batch.pages.append(self.pages[url])
        return batch


def default_hits() -> list[SearchHit]:
    return [
        SearchHit(
            title="Highway road construction tender in Maharashtra",
            url=OFFICIAL_URL,
            snippet="Estimated Cost: INR 50,00,000. Last Date of Submission: 15-12-2026",
            site_name="mahatenders.gov.in",
            position=1,
        ),
        SearchHit(
            title="Supply of office furniture",
            url=AGGREGATOR_URL,
            snippet="Chairs, desks and filing cabinets for offices",
            site_name="www.tender247.com",
            position=2,
        ),
    ]


def default_pages() -> dict[str, FetchedPage]:
    return {
        OFFICIAL_URL: FetchedPage(
            url=OFFICIAL_URL,
            final_url=OFFICIAL_URL,
            title="Highway road construction tender",
            description="Road work",
            text=(
                "Tender No: PWD/2026/ROAD-114\n"
                "Organisation: Maharashtra Public Works Department\n"
                "Estimated Cost: Rs. 50,00,000\n"
                "Last Date of Submission: 15-12-2026\n"
                "Work Location: Pune, Maharashtra\n"
            ),
        )
    }


def configure(fake: FakeTinyFish) -> None:
    app.dependency_overrides[get_discovery_client] = lambda: fake


def set_profile(client: TestClient, headers: dict[str, str]) -> None:
    response = client.patch("/api/companies/me", headers=headers, json=PROFILE)
    assert response.status_code == 200, response.text


def test_discovery_run_lists_only_relevant_tenders(client: TestClient, auth_headers: dict[str, str]):
    set_profile(client, auth_headers)
    fake = FakeTinyFish(hits=default_hits(), pages=default_pages())
    configure(fake)

    response = client.post("/api/discovery/run", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["run"]["status"] == "completed"
    assert payload["run"]["stats"]["search_hits"] == 12  # 6 profile queries x 2 hits each
    assert payload["run"]["stats"]["unique_candidates"] == 2
    assert payload["total"] >= 1

    titles = [item["title"] for item in payload["items"]]
    assert any("Highway" in title for title in titles)
    assert not any("furniture" in title.lower() for title in titles)

    matched = next(item for item in payload["items"] if "Highway" in item["title"])
    assert matched["source_type"] == "official"
    assert matched["source_url"] == OFFICIAL_URL
    assert matched["retrieved_at"]
    assert matched["relevance"]["score"] >= 0.3
    assert matched["relevance"]["reasons"]
    assert matched["fetch_status"] == "fetched"
    assert matched["extracted"]["reference_number"] == "PWD/2026/ROAD-114"
    assert matched["extracted"]["deadline"] == "2026-12-15"
    assert matched["extracted"]["value_amount"] == 5_000_000
    assert matched["extracted"]["evidence"]["deadline"]

    # Queries are built from the profile and cover the declared region and India.
    assert any("highway" in q.lower() for q in fake.search_calls)
    assert any("maharashtra" in q.lower() for q in fake.search_calls)


def test_discovery_stored_listing_and_save_flow(client: TestClient, auth_headers: dict[str, str]):
    set_profile(client, auth_headers)
    configure(FakeTinyFish(hits=default_hits(), pages=default_pages()))

    run = client.post("/api/discovery/run", headers=auth_headers).json()
    tender_id = run["items"][0]["id"]

    listing = client.get("/api/discovery/tenders", headers=auth_headers, params={"min_score": 0.3})
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    detail = client.get(f"/api/discovery/tenders/{tender_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == tender_id

    saved = client.post(f"/api/discovery/tenders/{tender_id}/save", headers=auth_headers, json={})
    assert saved.status_code == 200, saved.text

    my_tenders = client.get("/api/tenders", headers=auth_headers)
    assert my_tenders.status_code == 200
    assert my_tenders.json()["total"] == 1
    assert my_tenders.json()["items"][0]["source_url"] == OFFICIAL_URL
    # Date-only deadlines are anchored at noon UTC so the calendar day is stable in IST.
    assert "T12:00:00" in my_tenders.json()["items"][0]["deadline"]

    # Saving again is idempotent.
    again = client.post(f"/api/discovery/tenders/{tender_id}/save", headers=auth_headers, json={})
    assert again.status_code == 200
    assert client.get("/api/tenders", headers=auth_headers).json()["total"] == 1

    dismissed = client.post(f"/api/discovery/tenders/{tender_id}/dismiss", headers=auth_headers)
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"


def test_discovery_requires_configuration(client: TestClient, auth_headers: dict[str, str]):
    set_profile(client, auth_headers)
    configure(FakeTinyFish(configured=False))

    status_response = client.get("/api/discovery/status", headers=auth_headers)
    assert status_response.status_code == 200
    assert status_response.json()["configured"] is False

    response = client.post("/api/discovery/run", headers=auth_headers)
    assert response.status_code == 503
    assert "TINYFISH_API_KEY" in response.json()["detail"]


def test_discovery_requires_profile_terms(client: TestClient, auth_headers: dict[str, str]):
    configure(FakeTinyFish(hits=default_hits(), pages=default_pages()))
    response = client.post("/api/discovery/run", headers=auth_headers)
    assert response.status_code == 422
    assert "company profile" in response.json()["detail"].lower()


def test_discovery_is_scoped_to_the_company(
    client: TestClient, auth_headers: dict[str, str], fake_email
):
    set_profile(client, auth_headers)
    configure(FakeTinyFish(hits=default_hits(), pages=default_pages()))
    client.post("/api/discovery/run", headers=auth_headers)
    assert client.get("/api/discovery/tenders", headers=auth_headers).json()["total"] >= 1

    other = register_and_verify(
        client,
        fake_email,
        email="other@example.com",
        full_name="Other Owner",
        company_name="Other Infra Pvt Ltd",
    )
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    assert client.get("/api/discovery/tenders", headers=other_headers).json()["total"] == 0
    assert client.get("/api/discovery/runs", headers=other_headers).json()["total"] == 0


def test_listing_pages_are_stored_but_not_listed(
    client: TestClient, auth_headers: dict[str, str], database
):
    set_profile(client, auth_headers)
    listing_url = "https://www.tenderdetail.com/tenders/road-construction-tenders"
    hits = [
        SearchHit(
            title="Tender for Asphalt Road Construction Work At Various Places",
            url=OFFICIAL_URL,
            snippet="Closes Nov 11, 2026",
            site_name="mahatenders.gov.in",
            position=1,
        ),
        SearchHit(
            title="3141 Roads Construction tenders in Maharashtra 2026",
            url=listing_url,
            snippet="Road construction tenders across Maharashtra",
            site_name="www.tenderdetail.com",
            position=2,
        ),
    ]
    configure(FakeTinyFish(hits=hits, pages=default_pages()))

    payload = client.post("/api/discovery/run", headers=auth_headers).json()

    assert payload["run"]["stats"]["skipped_non_tender"] == 1
    assert payload["run"]["stats"]["skipped_listing"] == 1
    assert payload["total"] == 1
    assert all("tenders in" not in item["title"].lower() for item in payload["items"])

    company_id = client.get("/api/companies/me", headers=auth_headers).json()["id"]
    stored = list(database.discovered_tenders.find({"company_id": company_id}))
    assert any("3141" in doc["title"] for doc in stored)  # kept for provenance
    assert any(doc.get("is_listing_page") for doc in stored)


def test_social_posts_and_award_notices_are_not_listed(
    client: TestClient, auth_headers: dict[str, str], database
):
    set_profile(client, auth_headers)
    award_url = "https://www.tender247.com/tenders/award/highway-1"
    facebook_url = "https://www.facebook.com/groups/123/posts/456"
    hits = [
        SearchHit(
            title="Tender for Asphalt Road Construction Work At Various Places",
            url=OFFICIAL_URL,
            snippet="Closes Nov 11, 2026",
            site_name="mahatenders.gov.in",
            position=1,
        ),
        SearchHit(
            title="Highway road construction work awarded to a contractor in Maharashtra",
            url=award_url,
            snippet="The contract was awarded last week",
            site_name="www.tender247.com",
            position=2,
        ),
        SearchHit(
            title="Another major highway maintenance project awarded in Pune",
            url=facebook_url,
            snippet="Road construction update",
            site_name="www.facebook.com",
            position=3,
        ),
    ]
    configure(FakeTinyFish(hits=hits, pages=default_pages()))

    payload = client.post("/api/discovery/run", headers=auth_headers).json()

    assert payload["total"] == 1
    assert [item["source_url"] for item in payload["items"]] == [OFFICIAL_URL]
    assert payload["run"]["stats"]["skipped_non_tender"] == 1

    company_id = client.get("/api/companies/me", headers=auth_headers).json()["id"]
    stored = list(database.discovered_tenders.find({"company_id": company_id}))
    stored_urls = {doc["source_url"] for doc in stored}
    assert award_url in stored_urls  # stored for provenance, hidden from the list
    assert facebook_url not in stored_urls  # blocked before fetching


def test_tenders_are_ingested_from_a_listing_table(client: TestClient, auth_headers: dict[str, str]):
    set_profile(client, auth_headers)
    listing_url = "https://www.pmrda.gov.in/en/tender-notice/"
    table = "\n".join(
        [
            "| S.N. | Tender Name | Publish Date | Closing Date | Download |",
            "| --- | --- | --- | --- | --- |",
            "| 1 | Road construction work in Maharashtra at Ward 47 | 1 Oct 2030 | 15 Nov 2030 | Download |",
        ]
    )
    hit = SearchHit(
        title="Tender Notice | PMRDA Pune",
        url=listing_url,
        snippet="Official tenders and e-bids",
        site_name="www.pmrda.gov.in",
        position=1,
    )
    pages = {
        listing_url: FetchedPage(
            url=listing_url,
            final_url=listing_url,
            title="Tender Notice | PMRDA Pune",
            description="Official tenders",
            text=table,
        )
    }
    configure(FakeTinyFish(hits=[hit], pages=pages))

    payload = client.post("/api/discovery/run", headers=auth_headers).json()

    assert payload["run"]["stats"]["tenders_from_listings"] == 1
    assert payload["total"] == 1
    item = payload["items"][0]
    assert "Road construction work" in item["title"]
    assert item["source_url"] == listing_url
    assert item["source_type"] == "official"
    assert item["extracted_from"] == "listing_table"
    assert item["extracted"]["deadline"] == "2030-11-15"
    assert item["extracted"]["evidence"]["deadline"]


def test_closed_and_unverified_pages_are_not_listed(
    client: TestClient, auth_headers: dict[str, str]
):
    set_profile(client, auth_headers)
    closed_url = "https://www.tender247.com/tenders/road-closed"
    unverified_url = "https://www.tender247.com/tenders/road-directory"
    hits = [
        SearchHit(
            title="Tender for Asphalt Road Construction Work At Various Places",
            url=OFFICIAL_URL,
            snippet="Last date 15-12-2026",
            site_name="mahatenders.gov.in",
            position=1,
        ),
        SearchHit(
            title="Highway road construction work in Maharashtra closed last month",
            url=closed_url,
            snippet="Road work",
            site_name="www.tender247.com",
            position=2,
        ),
        SearchHit(
            title="Highway road construction contractor directory in Maharashtra",
            url=unverified_url,
            snippet="Road work",
            site_name="www.tender247.com",
            position=3,
        ),
    ]
    pages = default_pages()
    pages[closed_url] = FetchedPage(
        url=closed_url,
        final_url=closed_url,
        title="Highway road construction work closed",
        description="Closed",
        text="Tender No: XYZ/2026/1\nLast Date of Submission: 01-01-2026\n",
    )
    pages[unverified_url] = FetchedPage(
        url=unverified_url,
        final_url=unverified_url,
        title="Contractor directory",
        description="Directory",
        text="Directory of highway road construction contractors in Maharashtra.\n",
    )
    configure(FakeTinyFish(hits=hits, pages=pages))

    payload = client.post("/api/discovery/run", headers=auth_headers).json()

    assert payload["total"] == 1
    assert payload["run"]["stats"]["skipped_closed"] == 1
    assert payload["run"]["stats"]["skipped_unverified"] == 1


def test_sources_endpoint_lists_portal_pages(client: TestClient, auth_headers: dict[str, str]):
    set_profile(client, auth_headers)
    listing_url = "https://www.tenderdetail.com/Indian-tender/road-construction-tenders"
    hits = [
        SearchHit(
            title="Road Construction tenders in Maharashtra 2026",
            url=listing_url,
            snippet="Road construction tenders across Maharashtra",
            site_name="www.tenderdetail.com",
            position=1,
        )
    ]
    configure(FakeTinyFish(hits=hits, pages={}))

    client.post("/api/discovery/run", headers=auth_headers)
    response = client.get("/api/discovery/sources", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["source_url"] == listing_url
    assert data["items"][0]["is_listing_page"] is True
