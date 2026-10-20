from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import FakeEmailService, register_and_verify

REGISTER = {
    "email": "owner@example.com",
    "password": "StrongPass123",
    "full_name": "Asha Rao",
    "company_name": "Asha Infra Pvt Ltd",
}


def _verify(client: TestClient, email: str, purpose: str, code: str):
    return client.post(
        "/api/auth/verify-otp",
        json={"email": email, "purpose": purpose, "code": code},
    )


def test_register_verifies_email_and_login_uses_otp(
    client: TestClient, fake_email: FakeEmailService
):
    registered = client.post("/api/auth/register", json=REGISTER)
    assert registered.status_code == 201, registered.text
    challenge = registered.json()
    assert challenge["otp_required"] is True
    assert challenge["purpose"] == "verify_email"
    assert "access_token" not in challenge

    code = fake_email.code_for("owner@example.com", "verify_email")
    wrong = _verify(client, "owner@example.com", "verify_email", "000000")
    assert wrong.status_code == 400

    verified = _verify(client, "owner@example.com", "verify_email", code)
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email_verified"] is True
    assert body["user"]["otp_login_enabled"] is True
    assert body["company"]["name"] == "Asha Infra Pvt Ltd"

    login = client.post(
        "/api/auth/login",
        json={"email": "OWNER@example.com", "password": "StrongPass123"},
    )
    assert login.status_code == 200
    assert login.json()["otp_required"] is True
    assert login.json()["purpose"] == "login"
    assert "access_token" not in login.json()

    login_code = fake_email.code_for("owner@example.com", "login")
    second = _verify(client, "owner@example.com", "login", login_code)
    assert second.status_code == 200
    token = second.json()["access_token"]

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


def test_unverified_login_returns_verification_challenge(
    client: TestClient, fake_email: FakeEmailService
):
    client.post("/api/auth/register", json=REGISTER)
    login = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "StrongPass123"},
    )
    assert login.status_code == 200
    assert login.json()["purpose"] == "verify_email"
    assert "access_token" not in login.json()


def test_otp_can_be_disabled_for_password_only_login(
    client: TestClient, fake_email: FakeEmailService
):
    auth = register_and_verify(client, fake_email)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    changed = client.post(
        "/api/auth/security",
        headers=headers,
        json={"otp_login_enabled": False, "current_password": "StrongPass123"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["otp_login_enabled"] is False

    login = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "StrongPass123"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_resend_is_rate_limited_and_unknown_accounts_get_the_same_shape(
    client: TestClient,
):
    client.post("/api/auth/register", json=REGISTER)
    too_soon = client.post(
        "/api/auth/resend-otp",
        json={"email": "owner@example.com", "purpose": "verify_email"},
    )
    assert too_soon.status_code == 429

    unknown = client.post(
        "/api/auth/resend-otp",
        json={"email": "nobody@example.com", "purpose": "login"},
    )
    assert unknown.status_code == 200
    assert unknown.json()["otp_required"] is True
    assert "access_token" not in unknown.json()


def test_session_requires_authentication(client: TestClient):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/dashboard/summary").status_code == 401
