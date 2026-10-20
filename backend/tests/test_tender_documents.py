from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import make_pdf


def upload_document(
    client: TestClient,
    headers: dict[str, str],
    tender_id: str,
    content: bytes,
    *,
    filename: str = "tender.pdf",
    kind: str = "main",
    title: str = "Sample tender document",
):
    return client.post(
        f"/api/tenders/{tender_id}/documents",
        headers=headers,
        data={"kind": kind, "title": title, "source_url": "https://example.gov.in/tender/road-14"},
        files={"file": (filename, content, "application/pdf")},
    )


def test_upload_extracts_pages_and_download(
    client: TestClient, auth_headers: dict[str, str], tender: dict, sample_pdf: bytes
):
    response = upload_document(client, auth_headers, tender["id"], sample_pdf)
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["status"] == "extracted"
    assert document["page_count"] == 3
    assert document["text_page_count"] == 3
    assert document["source"] == "uploaded"
    assert document["tender_id"] == tender["id"]
    assert document["sha256"]

    listing = client.get(f"/api/tenders/{tender['id']}/documents", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    pages = client.get(f"/api/tender-documents/{document['id']}/pages", headers=auth_headers)
    assert pages.status_code == 200
    body = pages.json()
    assert len(body["items"]) == 3
    assert body["items"][0]["page_index"] == 1
    assert body["items"][0]["has_text"] is True

    page_text = client.get(
        f"/api/tender-documents/{document['id']}/pages/1", headers=auth_headers
    )
    assert page_text.status_code == 200
    assert "average annual turnover" in page_text.json()["text"]

    downloaded = client.get(
        f"/api/tender-documents/{document['id']}/download", headers=auth_headers
    )
    assert downloaded.status_code == 200
    assert downloaded.content == sample_pdf
    assert downloaded.headers["cache-control"] == "private, no-store"


def test_duplicate_upload_reuses_document(
    client: TestClient, auth_headers: dict[str, str], tender: dict, sample_pdf: bytes
):
    first = upload_document(client, auth_headers, tender["id"], sample_pdf).json()
    second = upload_document(client, auth_headers, tender["id"], sample_pdf).json()
    assert first["id"] == second["id"]
    listing = client.get(f"/api/tenders/{tender['id']}/documents", headers=auth_headers).json()
    assert listing["total"] == 1


def test_non_pdf_is_rejected(
    client: TestClient, auth_headers: dict[str, str], tender: dict
):
    response = client.post(
        f"/api/tenders/{tender['id']}/documents",
        headers=auth_headers,
        data={"kind": "main", "title": "Not a PDF"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 422


def test_scanned_pdf_is_flagged(
    client: TestClient, auth_headers: dict[str, str], tender: dict
):
    blank = make_pdf([" "])
    document = upload_document(client, auth_headers, tender["id"], blank).json()
    assert document["status"] == "no_text_layer"
    assert document["text_page_count"] == 0


def test_delete_removes_document_pages(
    client: TestClient, auth_headers: dict[str, str], tender: dict, sample_pdf: bytes
):
    document = upload_document(client, auth_headers, tender["id"], sample_pdf).json()
    deleted = client.delete(f"/api/tender-documents/{document['id']}", headers=auth_headers)
    assert deleted.status_code == 200
    assert (
        client.get(f"/api/tender-documents/{document['id']}", headers=auth_headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/tender-documents/{document['id']}/pages/1", headers=auth_headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/tenders/{tender['id']}/documents", headers=auth_headers).json()["total"]
        == 0
    )


def test_other_company_cannot_access_tender_documents(
    client: TestClient, auth_headers: dict[str, str], tender: dict, sample_pdf: bytes
):
    document = upload_document(client, auth_headers, tender["id"], sample_pdf).json()
    second = client.post(
        "/api/auth/register",
        json={
            "email": "other-docs@example.com",
            "password": "StrongPass123",
            "full_name": "Other Owner",
            "company_name": "Other Co",
        },
    )
    other_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}

    assert (
        client.get(f"/api/tenders/{tender['id']}/documents", headers=other_headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/tender-documents/{document['id']}", headers=other_headers).status_code
        == 404
    )
    assert (
        client.delete(f"/api/tender-documents/{document['id']}", headers=other_headers).status_code
        == 404
    )
