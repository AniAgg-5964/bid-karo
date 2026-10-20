from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import PDF_BYTES, register_and_verify


def upload(client: TestClient, headers: dict[str, str], name: str = "certificate.pdf"):
    return client.post(
        "/api/documents",
        headers=headers,
        data={
            "title": "ISO 9001 Certificate",
            "document_type": "certification",
            "issuer": "Quality Council",
            "expiry_date": "2030-12-31",
        },
        files={"file": (name, PDF_BYTES, "application/pdf")},
    )


def test_upload_list_download_and_delete(client: TestClient, auth_headers: dict[str, str]):
    uploaded = upload(client, auth_headers)
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["original_filename"] == "certificate.pdf"
    assert document["mime_type"] == "application/pdf"
    assert document["verification_status"] == "self_declared"
    assert document["expiry_date"] == "2030-12-31"

    listing = client.get("/api/documents", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    downloaded = client.get(f"/api/documents/{document['id']}/download", headers=auth_headers)
    assert downloaded.status_code == 200
    assert downloaded.content == PDF_BYTES
    assert downloaded.headers["cache-control"] == "private, no-store"

    deleted = client.delete(f"/api/documents/{document['id']}", headers=auth_headers)
    assert deleted.status_code == 200
    assert client.get("/api/documents", headers=auth_headers).json()["total"] == 0
    assert (
        client.get(f"/api/documents/{document['id']}/download", headers=auth_headers).status_code
        == 404
    )


def test_spoofed_file_is_rejected(client: TestClient, auth_headers: dict[str, str]):
    response = client.post(
        "/api/documents",
        headers=auth_headers,
        data={"title": "Fake", "document_type": "other"},
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 422
    assert "content does not match" in response.json()["detail"]


def test_unsupported_extension_is_rejected(client: TestClient, auth_headers: dict[str, str]):
    response = client.post(
        "/api/documents",
        headers=auth_headers,
        data={"title": "Script", "document_type": "other"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 422


def test_other_company_cannot_access_document(
    client: TestClient, auth_headers: dict[str, str], fake_email
):
    document = upload(client, auth_headers).json()
    second = register_and_verify(
        client,
        fake_email,
        email="other@example.com",
        full_name="Other Owner",
        company_name="Other Co",
    )
    other_headers = {"Authorization": f"Bearer {second['access_token']}"}

    assert client.get("/api/documents", headers=other_headers).json()["total"] == 0
    assert (
        client.get(f"/api/documents/{document['id']}/download", headers=other_headers).status_code
        == 404
    )
    assert (
        client.delete(f"/api/documents/{document['id']}", headers=other_headers).status_code
        == 404
    )


def test_dashboard_uses_stored_records(client: TestClient, auth_headers: dict[str, str]):
    summary = client.get("/api/dashboard/summary", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["metrics"]["evidence_documents"] == 0
    assert summary.json()["metrics"]["active_bids"] == 0
    assert summary.json()["recent_tenders"] == []

    upload(client, auth_headers)
    summary = client.get("/api/dashboard/summary", headers=auth_headers)
    assert summary.json()["metrics"]["evidence_documents"] == 1
    assert any(action["key"] == "discover_tender" for action in summary.json()["priority_actions"])
