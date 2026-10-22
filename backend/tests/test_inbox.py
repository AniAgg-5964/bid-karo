"""The Action Inbox endpoint.

The list must be built from the company's own records, and every item must
point at a real record.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.repositories.tender_documents import RequirementRepository
from app.repositories.tenders import ChecklistRepository, TenderRepository


def test_the_inbox_is_empty_for_a_fresh_company(
    client: TestClient, auth_headers: dict[str, str], company_id: str
):
    response = client.get("/api/dashboard/inbox", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_the_inbox_needs_a_signed_in_user(client: TestClient):
    assert client.get("/api/dashboard/inbox").status_code == 401


def test_an_unresolved_mandatory_criterion_reaches_the_inbox(
    client: TestClient,
    database,
    auth_headers: dict[str, str],
    company_id: str,
    tender: dict,
):
    RequirementRepository(database).create(
        {
            "company_id": company_id,
            "tender_id": tender["id"],
            "document_id": "document-1",
            "title": "Valid ISO 9001 certification",
            "category": "technical",
            "mandatory": "yes",
            "excerpt": "The bidder shall hold a valid ISO 9001 certification.",
            "verification_status": "verified",
            "origin": "ai",
        }
    )
    response = client.get("/api/dashboard/inbox", headers=auth_headers)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items
    first = items[0]
    assert first["kind"] == "eligibility"
    assert first["severity"] == "warning"
    assert first["tender_id"] == tender["id"]
    assert first["href"].endswith(f"/app/tenders/{tender['id']}?tab=eligibility")
    assert first["action_label"]


def test_a_task_with_a_deadline_reaches_the_inbox(
    client: TestClient,
    database,
    auth_headers: dict[str, str],
    company_id: str,
    tender: dict,
):
    ChecklistRepository(database).collection.insert_one(
        {
            "company_id": company_id,
            "tender_id": tender["id"],
            "title": "Attach the audited statements",
            "status": "missing",
            "due_at": datetime.now(timezone.utc) + timedelta(days=3),
            "created_at": datetime.now(timezone.utc),
        }
    )
    response = client.get("/api/dashboard/inbox", headers=auth_headers)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    kinds = {item["kind"] for item in items}
    assert "deadline" in kinds


def test_a_tender_whose_source_was_never_checked_reaches_the_inbox(
    client: TestClient,
    database,
    auth_headers: dict[str, str],
    company_id: str,
    tender: dict,
):
    TenderRepository(database).update_for_company(
        tender["id"],
        company_id,
        {"source_url": "https://example.gov.in/tender/road-14", "source_retrieved_at": None},
    )
    response = client.get("/api/dashboard/inbox", headers=auth_headers)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    sources = [item for item in items if item["kind"] == "source"]
    assert sources
    assert "never" in sources[0]["description"].lower()
