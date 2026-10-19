from __future__ import annotations

from fastapi.testclient import TestClient


def test_profile_update_persists_and_increases_completeness(
    client: TestClient, auth_headers: dict[str, str]
):
    before = client.get("/api/auth/me", headers=auth_headers).json()["company"]
    assert before["profile_completeness"] < 20

    response = client.patch(
        "/api/companies/me",
        headers=auth_headers,
        json={
            "legal_name": "Asha Infrastructure Private Limited",
            "business_type": "private_limited",
            "description": "Roads, bridges and municipal civil works.",
            "products_services": ["Road construction", "Bridge maintenance"],
            "sectors": ["Infrastructure", "Transport"],
            "regions": ["Maharashtra", "Gujarat"],
            "certifications": ["ISO 9001:2015"],
            "annual_turnover": 125000000,
            "employee_count": 240,
            "established_year": 2011,
            "preferences": {
                "sectors": ["Infrastructure"],
                "regions": ["Maharashtra"],
                "keywords": ["highway"],
                "min_value": 1000000,
                "max_value": 500000000,
            },
        },
    )
    assert response.status_code == 200, response.text
    company = response.json()
    assert company["legal_name"] == "Asha Infrastructure Private Limited"
    assert company["profile_completeness"] > 50
    assert company["annual_turnover"] == 125000000

    reloaded = client.get("/api/companies/me", headers=auth_headers).json()
    assert reloaded["sectors"] == ["Infrastructure", "Transport"]
    assert reloaded["preferences"]["min_value"] == 1000000


def test_company_records_are_isolated(client: TestClient, auth_headers: dict[str, str]):
    second = client.post(
        "/api/auth/register",
        json={
            "email": "second@example.com",
            "password": "StrongPass123",
            "full_name": "Vikram Shah",
            "company_name": "Shah Builders",
        },
    )
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}

    client.patch(
        "/api/companies/me",
        headers=auth_headers,
        json={"description": "First company only"},
    )

    first_company = client.get("/api/companies/me", headers=auth_headers).json()
    second_company = client.get("/api/companies/me", headers=second_headers).json()
    assert first_company["id"] != second_company["id"]
    assert first_company["description"] == "First company only"
    assert second_company["description"] is None


def test_invalid_preference_range_is_rejected(client: TestClient, auth_headers: dict[str, str]):
    response = client.patch(
        "/api/companies/me",
        headers=auth_headers,
        json={
            "preferences": {
                "min_value": 500,
                "max_value": 100,
            }
        },
    )
    assert response.status_code == 422
