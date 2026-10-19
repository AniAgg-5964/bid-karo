from __future__ import annotations

from fastapi.testclient import TestClient


REGISTER = {
    "email": "owner@example.com",
    "password": "StrongPass123",
    "full_name": "Asha Rao",
    "company_name": "Asha Infra Pvt Ltd",
}


def test_register_login_and_session(client: TestClient):
    registered = client.post("/api/auth/register", json=REGISTER)
    assert registered.status_code == 201
    body = registered.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "owner@example.com"
    assert body["company"]["name"] == "Asha Infra Pvt Ltd"
    assert body["company"]["onboarding_completed"] is False

    login = client.post(
        "/api/auth/login",
        json={"email": "OWNER@example.com", "password": "StrongPass123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    session = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert session.status_code == 200
    assert session.json()["user"]["full_name"] == "Asha Rao"
    assert session.json()["company"]["id"] == body["company"]["id"]


def test_duplicate_email_is_rejected(client: TestClient):
    assert client.post("/api/auth/register", json=REGISTER).status_code == 201
    duplicate = client.post("/api/auth/register", json=REGISTER)
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]


def test_weak_password_is_rejected(client: TestClient):
    payload = {**REGISTER, "password": "allletters"}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422


def test_wrong_password_does_not_issue_token(client: TestClient):
    client.post("/api/auth/register", json=REGISTER)
    response = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "WrongPass123"},
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()


def test_session_requires_authentication(client: TestClient):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/dashboard/summary").status_code == 401
