from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.database import Database, utcnow
from app.repositories.tenders import TenderRepository


def test_dashboard_counts_tender_submission_deadlines(
    client: TestClient, auth_headers: dict[str, str], database: Database
):
    company_id = client.get("/api/companies/me", headers=auth_headers).json()["id"]
    tenders = TenderRepository(database)

    tenders.create(
        {
            "company_id": company_id,
            "title": "Near-deadline tender",
            "status": "saved",
            "deadline": utcnow() + timedelta(days=5),
        }
    )
    tenders.create(
        {
            "company_id": company_id,
            "title": "Far-deadline tender",
            "status": "saved",
            "deadline": utcnow() + timedelta(days=40),
        }
    )

    summary = client.get("/api/dashboard/summary", headers=auth_headers).json()

    assert summary["metrics"]["active_bids"] == 2
    assert summary["metrics"]["upcoming_deadlines"] == 1
    assert [item["title"] for item in summary["upcoming_deadlines"]] == ["Near-deadline tender"]
    assert summary["upcoming_deadlines"][0]["href"].startswith("/app/tenders/")
