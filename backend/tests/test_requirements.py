from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.dependencies import get_ai_provider
from app.integrations.ai import AIError
from app.main import app
from app.services import requirement_service as requirement_service_module
from app.services.download import DownloadError
from tests.conftest import make_pdf
from tests.test_tender_documents import upload_document

EXCERPT_1 = (
    "The bidder shall have an average annual turnover of at least INR 5 crore "
    "during the last three financial years."
)
EXCERPT_2 = (
    "Bids must be submitted before 15 November 2026 at 17:00 IST through the online portal."
)


class FakeAI:
    model = "fake-model"

    def __init__(self, payload: dict | None = None, *, configured: bool = True) -> None:
        self.payload = payload or {"requirements": []}
        self.configured = configured
        self.calls = 0

    def complete_json(self, *, system: str, user: str) -> dict:
        self.calls += 1
        return self.payload


class FailingAI:
    model = "fake-model"
    configured = True

    def complete_json(self, *, system: str, user: str) -> dict:
        raise AIError("provider unavailable")


def ai_payload() -> dict:
    return {
        "requirements": [
            {
                "category": "eligibility",
                "title": "Minimum average annual turnover",
                "obligation": "Bidder must show average annual turnover of at least INR 5 crore.",
                "excerpt": EXCERPT_1,
                "page_index": 1,
                "clause_reference": "Section 3",
                "mandatory": "required",
            },
            {
                "category": "eligibility",
                "title": "Notarised affidavit",
                "obligation": "Bidder must submit a notarised affidavit.",
                "excerpt": "A notarised affidavit of ownership must be submitted on stamp paper.",
                "page_index": 1,
                "mandatory": "yes",
            },
            {
                "category": "submission",
                "title": "Bid submission deadline",
                "obligation": "Bids must be submitted online before 15 November 2026 at 17:00 IST.",
                "excerpt": EXCERPT_2,
                "page_index": 1,
                "mandatory": "yes",
            },
            {
                "category": "other",
                "title": "Empty citation",
                "obligation": "This item has no usable excerpt.",
                "excerpt": "",
                "page_index": 1,
            },
        ]
    }


def extract(client: TestClient, headers: dict[str, str], document_id: str, **body):
    return client.post(
        f"/api/tender-documents/{document_id}/extract",
        headers=headers,
        json=body or {},
    )


def test_extraction_verifies_and_flags_citations(
    client: TestClient,
    auth_headers: dict[str, str],
    tender: dict,
    sample_pdf: bytes,
):
    document = upload_document(client, auth_headers, tender["id"], sample_pdf).json()
    fake = FakeAI(ai_payload())
    app.dependency_overrides[get_ai_provider] = lambda: fake

    response = extract(client, auth_headers, document["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["created"] == 3
    assert body["verified"] == 1
    assert body["unverified"] == 2
    assert body["invalid"] == 1
    assert body["model"] == "fake-model"

    listing = client.get(
        f"/api/tenders/{tender['id']}/requirements", headers=auth_headers
    )
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 3

    verified = [item for item in items if item["verification_status"] == "verified"]
    assert len(verified) == 1
    assert verified[0]["page_index"] == 1
    assert verified[0]["printed_page"] == "1"
    assert verified[0]["mandatory"] == "yes"
    assert verified[0]["clause_reference"] == "Section 3"
    assert verified[0]["source_url"] == "https://example.gov.in/tender/road-14"
    assert verified[0]["document_title"] == "Sample tender document"
    assert verified[0]["document_retrieved_at"]

    unverified = [item for item in items if item["verification_status"] == "unverified"]
    assert len(unverified) == 2
    assert all(item["verification_notes"] for item in unverified)

    filtered = client.get(
        f"/api/tenders/{tender['id']}/requirements?verification_status=unverified",
        headers=auth_headers,
    )
    assert filtered.json()["total"] == 2

    summary = client.get(
        f"/api/tenders/{tender['id']}/requirements/summary", headers=auth_headers
    )
    assert summary.status_code == 200
    assert summary.json() == {"total": 3, "verified": 1, "unverified": 2, "documents": 1}


def test_rerun_is_idempotent_and_replace_resets(
    client: TestClient,
    auth_headers: dict[str, str],
    tender: dict,
    sample_pdf: bytes,
):
    document = upload_document(client, auth_headers, tender["id"], sample_pdf).json()
    app.dependency_overrides[get_ai_provider] = lambda: FakeAI(ai_payload())

    first = extract(client, auth_headers, document["id"]).json()
    assert first["created"] == 3

    second = extract(client, auth_headers, document["id"]).json()
    assert second["created"] == 0
    assert second["duplicates"] == 3

    replaced = extract(client, auth_headers, document["id"], replace=True).json()
    assert replaced["created"] == 3
    total = client.get(
        f"/api/tenders/{tender['id']}/requirements", headers=auth_headers
    ).json()["total"]
    assert total == 3


def test_manual_review_updates_status(
    client: TestClient,
    auth_headers: dict[str, str],
    tender: dict,
    sample_pdf: bytes,
):
    document = upload_document(client, auth_headers, tender["id"], sample_pdf).json()
    app.dependency_overrides[get_ai_provider] = lambda: FakeAI(ai_payload())
    extract(client, auth_headers, document["id"])

    items = client.get(
        f"/api/tenders/{tender['id']}/requirements", headers=auth_headers
    ).json()["items"]
    unverified = next(item for item in items if item["verification_status"] == "unverified")

    updated = client.patch(
        f"/api/requirements/{unverified['id']}",
        headers=auth_headers,
        json={"verification_status": "verified", "note": "Checked against the PDF page."},
    )
    assert updated.status_code == 200
    assert updated.json()["verification_status"] == "verified"
    assert updated.json()["verification_notes"] == "Checked against the PDF page."

    cleared = client.patch(
        f"/api/requirements/{unverified['id']}",
        headers=auth_headers,
        json={"verification_status": "verified"},
    )
    assert cleared.status_code == 200
    assert cleared.json()["verification_notes"] is None


def test_failed_replace_keeps_existing_requirements(
    client: TestClient,
    auth_headers: dict[str, str],
    tender: dict,
    sample_pdf: bytes,
):
    document = upload_document(client, auth_headers, tender["id"], sample_pdf).json()
    app.dependency_overrides[get_ai_provider] = lambda: FakeAI(ai_payload())
    extract(client, auth_headers, document["id"])

    app.dependency_overrides[get_ai_provider] = lambda: FailingAI()
    response = extract(client, auth_headers, document["id"], replace=True)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == 0
    assert body["failed_chunks"] >= 1
    assert "kept" in body["message"]

    listing = client.get(
        f"/api/tenders/{tender['id']}/requirements", headers=auth_headers
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 3


def test_extraction_requires_text_and_ai_configuration(
    client: TestClient, auth_headers: dict[str, str], tender: dict
):
    blank = upload_document(client, auth_headers, tender["id"], make_pdf([" "])).json()
    assert blank["status"] == "no_text_layer"
    assert extract(client, auth_headers, blank["id"]).status_code == 422

    document = upload_document(
        client,
        auth_headers,
        tender["id"],
        make_pdf(["This page has enough text to be treated as a text layer."]),
    ).json()
    app.dependency_overrides[get_ai_provider] = lambda: FakeAI(configured=False)
    not_configured = extract(client, auth_headers, document["id"])
    assert not_configured.status_code == 503


def test_fetch_downloads_pdf_and_records_source(
    client: TestClient,
    auth_headers: dict[str, str],
    tender: dict,
    sample_pdf: bytes,
    monkeypatch,
):
    def fake_download(url: str, **kwargs):
        assert url == "https://example.gov.in/files/tender.pdf"
        assert kwargs["max_bytes"] > 0
        return sample_pdf, "https://example.gov.in/files/tender.pdf", "application/pdf"

    monkeypatch.setattr(requirement_service_module, "download_pdf", fake_download)

    response = client.post(
        f"/api/tenders/{tender['id']}/documents/fetch",
        headers=auth_headers,
        json={"url": "https://example.gov.in/files/tender.pdf", "kind": "main"},
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["source"] == "downloaded"
    assert document["source_url"] == "https://example.gov.in/files/tender.pdf"
    assert document["original_filename"] == "tender.pdf"
    assert document["status"] == "extracted"


def test_blocked_download_asks_for_upload(
    client: TestClient, auth_headers: dict[str, str], tender: dict, monkeypatch
):
    def blocked(url: str, **kwargs):
        raise DownloadError("http_403", "bot protection")

    monkeypatch.setattr(requirement_service_module, "download_pdf", blocked)

    response = client.post(
        f"/api/tenders/{tender['id']}/documents/fetch",
        headers=auth_headers,
        json={"url": "https://portal.example.gov.in/tender.pdf"},
    )
    assert response.status_code == 409
    assert "Upload the PDF instead" in response.json()["detail"]
    assert "http_403" in response.json()["detail"]
