from __future__ import annotations

from fastapi.testclient import TestClient


def test_security_headers_and_unauthorised_requests(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.headers["X-Content-Type-Options"] == "nosniff"
    assert health.headers["X-Frame-Options"] == "DENY"
    assert health.headers["Referrer-Policy"] == "no-referrer"

    unauthorised = client.get("/api/tenders")
    assert unauthorised.status_code == 401
    assert unauthorised.headers["X-Content-Type-Options"] == "nosniff"


def test_validation_and_missing_resources_are_honest(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    missing = client.get("/api/tenders/not-a-real-tender", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["detail"]

    invalid_status = client.get(
        "/api/reminders",
        headers=auth_headers,
        params={"status": "made-up"},
    )
    assert invalid_status.status_code == 422

    bad_review = client.patch(
        "/api/changes/not-a-real-change/review",
        headers=auth_headers,
        json={"review_status": "made-up"},
    )
    assert bad_review.status_code == 422

    unauthenticated_ics = client.get("/api/calendar.ics")
    assert unauthenticated_ics.status_code == 401
