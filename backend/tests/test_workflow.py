from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import Database, utcnow
from app.repositories.tenders import TenderRepository
from app.services.email import EmailService
from app.repositories.workflow import ReminderRepository
from app.services.reminders import ReminderService
from tests.conftest import register_and_verify


def test_snapshot_capture_detects_field_changes_and_review(
    client: TestClient,
    database: Database,
    auth_headers: dict[str, str],
    company_id: str,
    tender: dict,
) -> None:
    first = client.post(
        f"/api/tenders/{tender['id']}/snapshots", headers=auth_headers
    )
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["created"] is True
    assert payload["changes"] == []

    again = client.post(
        f"/api/tenders/{tender['id']}/snapshots", headers=auth_headers
    )
    assert again.status_code == 200, again.text
    assert again.json()["created"] is False

    deadline = datetime(2026, 12, 15, 12, 0, tzinfo=timezone.utc)
    TenderRepository(database).update_for_company(
        tender["id"],
        company_id,
        {"deadline": deadline, "title": "Updated sample road tender"},
    )

    changed = client.post(
        f"/api/tenders/{tender['id']}/snapshots", headers=auth_headers
    )
    assert changed.status_code == 200, changed.text
    fields = {item["field"] for item in changed.json()["changes"]}
    assert {"deadline", "title"} <= fields

    changes = client.get("/api/changes", headers=auth_headers)
    assert changes.status_code == 200, changes.text
    body = changes.json()
    assert body["total"] >= 2
    assert all(item["review_status"] == "pending" for item in body["items"])

    reviewed = client.patch(
        f"/api/changes/{body['items'][0]['id']}/review",
        headers=auth_headers,
        json={"review_status": "acknowledged"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["review_status"] == "acknowledged"


def test_reminders_are_derived_and_can_be_acknowledged(
    client: TestClient,
    database: Database,
    auth_headers: dict[str, str],
    company_id: str,
    tender: dict,
    fake_email,
) -> None:
    TenderRepository(database).update_for_company(
        tender["id"],
        company_id,
        {"deadline": utcnow() + timedelta(days=5)},
    )

    listed = client.get("/api/reminders", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["email_enabled"] is False
    assert any(item["type"] == "deadline" for item in body["items"])
    reminder = body["items"][0]

    acknowledged = client.patch(
        f"/api/reminders/{reminder['id']}",
        headers=auth_headers,
        json={"status": "acknowledged"},
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["status"] == "acknowledged"

    updated = client.patch(
        "/api/companies/me",
        headers=auth_headers,
        json={"reminder_email_enabled": True, "reminder_lead_days": [3, 1]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["reminder_email_enabled"] is True

    result = ReminderService(database, email=fake_email).send_due(
        dry_run=False,
        now=utcnow() + timedelta(days=10),
        limit=10,
        email=fake_email,
    )
    assert result["sent"] >= 1
    assert fake_email.reminders
    assert "BidKaro reminder" not in fake_email.reminders[0]["title"]


def test_tender_and_company_calendar_export(
    client: TestClient,
    database: Database,
    auth_headers: dict[str, str],
    company_id: str,
    tender: dict,
) -> None:
    deadline = datetime(2026, 12, 15, 12, 0, tzinfo=timezone.utc)
    TenderRepository(database).update_for_company(
        tender["id"], company_id, {"deadline": deadline}
    )

    tender_ics = client.get(
        f"/api/tenders/{tender['id']}/calendar.ics", headers=auth_headers
    )
    assert tender_ics.status_code == 200, tender_ics.text
    assert tender_ics.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in tender_ics.text
    assert "DTSTART;VALUE=DATE:20261215" in tender_ics.text
    assert "SUMMARY:" in tender_ics.text

    company_ics = client.get("/api/calendar.ics", headers=auth_headers)
    assert company_ics.status_code == 200, company_ics.text
    assert "BEGIN:VCALENDAR" in company_ics.text
    assert "tender-" in company_ics.text


def test_post_award_obligations_are_cited_and_idempotent(
    client: TestClient,
    database: Database,
    auth_headers: dict[str, str],
    company_id: str,
    tender: dict,
) -> None:
    now = utcnow()
    database.requirements.insert_one(
        {
            "_id": "req-performance-1",
            "company_id": company_id,
            "tender_id": tender["id"],
            "document_id": "doc-performance-1",
            "document_title": "Sample RFP",
            "title": "Performance bank guarantee",
            "category": "performance",
            "mandatory": "yes",
            "obligation": "Submit a performance bank guarantee within 30 days of award.",
            "excerpt": "Submit a performance bank guarantee within 30 days of award.",
            "page_index": 2,
            "printed_page": "2",
            "clause_reference": "Clause 9",
            "source_url": "https://example.gov.in/tender/road-14",
            "source_retrieved_at": now,
            "verification_status": "verified",
            "review_status": "verified",
            "created_at": now,
            "updated_at": now,
        }
    )

    generated = client.post(
        f"/api/tenders/{tender['id']}/obligations/generate", headers=auth_headers
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["created"] == 1

    listed = client.get(
        f"/api/tenders/{tender['id']}/obligations", headers=auth_headers
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["phase"] == "post_award"
    assert items[0]["clause_reference"] == "Clause 9"
    assert items[0]["source_url"] == "https://example.gov.in/tender/road-14"

    again = client.post(
        f"/api/tenders/{tender['id']}/obligations/generate", headers=auth_headers
    )
    assert again.status_code == 200, again.text
    assert again.json()["created"] == 0
    assert again.json()["skipped"] == 1


def test_snapshot_versions_requirement_set_changes(
    client: TestClient,
    database: Database,
    auth_headers: dict[str, str],
    company_id: str,
    tender: dict,
) -> None:
    baseline = client.post(
        f"/api/tenders/{tender['id']}/snapshots", headers=auth_headers
    )
    assert baseline.status_code == 200, baseline.text
    assert baseline.json()["created"] is True

    database.requirements.insert_one(
        {
            "_id": "requirement-snapshot-test",
            "company_id": company_id,
            "tender_id": tender["id"],
            "document_id": "doc-snapshot-test",
            "title": "Performance security",
            "excerpt": "The contractor shall furnish performance security.",
            "excerpt_key": "the contractor shall furnish performance security",
            "verification_status": "verified",
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
    )
    added = client.post(
        f"/api/tenders/{tender['id']}/snapshots", headers=auth_headers
    )
    assert added.status_code == 200, added.text
    assert added.json()["created"] is True
    assert any(
        item["field"] == "requirements" and "Requirement added" in item["summary"]
        for item in added.json()["changes"]
    )

    database.requirements.update_one(
        {"_id": "requirement-snapshot-test"},
        {"$set": {"title": "Performance security (revised)", "updated_at": utcnow()}},
    )
    updated = client.post(
        f"/api/tenders/{tender['id']}/snapshots", headers=auth_headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["created"] is True
    assert any(
        item["field"] == "requirements" and "changed" in item["summary"]
        for item in updated.json()["changes"]
    )

    # A human review status is not a source change and must not create a version.
    database.requirements.update_one(
        {"_id": "requirement-snapshot-test"},
        {"$set": {"verification_status": "needs_review", "updated_at": utcnow()}},
    )
    reviewed = client.post(
        f"/api/tenders/{tender['id']}/snapshots", headers=auth_headers
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["created"] is False
    assert reviewed.json()["changes"] == []


def test_workflow_is_tenant_scoped(
    client: TestClient,
    database: Database,
    auth_headers: dict[str, str],
    tender: dict,
    fake_email,
) -> None:
    captured = client.post(
        f"/api/tenders/{tender['id']}/snapshots", headers=auth_headers
    )
    assert captured.status_code == 200, captured.text
    change_id = "change-tenant-test"
    database.changes.insert_one(
        {
            "_id": change_id,
            "company_id": tender["company_id"],
            "tender_id": tender["id"],
            "tender_title": tender["title"],
            "field": "deadline",
            "old_value": None,
            "new_value": "2026-12-15",
            "summary": "Submission deadline changed",
            "severity": "warning",
            "review_status": "pending",
            "source_url": tender["source_url"],
            "detected_at": utcnow(),
            "created_at": utcnow(),
        }
    )
    database.reminders.insert_one(
        {
            "_id": "reminder-tenant-test",
            "company_id": tender["company_id"],
            "reminder_key": "tenant-test",
            "type": "deadline",
            "title": "Tenant reminder",
            "body": "Tenant reminder body",
            "due_at": utcnow(),
            "href": f"/app/tenders/{tender['id']}",
            "tender_id": tender["id"],
            "active": True,
            "status": "pending",
            "attempts": 0,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
    )

    other = register_and_verify(
        client,
        fake_email,
        email="other-owner@example.com",
        company_name="Other Infra Pvt Ltd",
    )
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    for path in (
        f"/api/tenders/{tender['id']}/snapshots",
        f"/api/tenders/{tender['id']}/changes",
        f"/api/tenders/{tender['id']}/obligations",
        f"/api/tenders/{tender['id']}/calendar.ics",
    ):
        response = client.get(path, headers=other_headers)
        assert response.status_code == 404, (path, response.status_code, response.text)

    assert client.get("/api/changes", headers=other_headers).json()["total"] == 0
    assert client.get("/api/reminders", headers=other_headers).json()["total"] == 0
    denied = client.patch(
        f"/api/changes/{change_id}/review",
        headers=other_headers,
        json={"review_status": "acknowledged"},
    )
    assert denied.status_code == 404
    denied_reminder = client.patch(
        "/api/reminders/reminder-tenant-test",
        headers=other_headers,
        json={"status": "acknowledged"},
    )
    assert denied_reminder.status_code == 404


def test_reminder_email_reports_missing_smtp_honestly(
    client: TestClient,
    database: Database,
    auth_headers: dict[str, str],
    company_id: str,
    tender: dict,
) -> None:
    TenderRepository(database).update_for_company(
        tender["id"], company_id, {"deadline": utcnow() + timedelta(days=2)}
    )
    updated = client.patch(
        "/api/companies/me",
        headers=auth_headers,
        json={"reminder_email_enabled": True, "reminder_lead_days": [1]},
    )
    assert updated.status_code == 200, updated.text

    sender = EmailService(
        Settings(
            jwt_secret="test-secret-value-that-is-long-enough",
            smtp_username="sender@example.com",
            smtp_app_password="",
        )
    )
    assert sender.configured is False
    result = ReminderService(database, email=sender).send_due(
        dry_run=False,
        now=utcnow() + timedelta(days=10),
        limit=5,
        email=sender,
    )
    assert result["sent"] == 0
    assert result["failed"] >= 1
    failed = database.reminders.find_one(
        {"company_id": company_id, "last_error": {"$ne": None}}
    )
    assert failed is not None
    assert "not configured" in failed["last_error"].lower()


def test_tender_detail_includes_document_count(
    client: TestClient,
    database: Database,
    auth_headers: dict[str, str],
    company_id: str,
    tender: dict,
) -> None:
    database.tender_documents.insert_one(
        {
            "_id": "doc-count-test",
            "company_id": company_id,
            "tender_id": tender["id"],
            "title": "Sample RFP",
            "kind": "main",
            "mime_type": "application/pdf",
            "size_bytes": 10,
            "sha256": "abc",
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
    )
    response = client.get(f"/api/tenders/{tender['id']}", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["document_count"] == 1
