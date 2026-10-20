from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.repositories.documents import DocumentRepository
from app.repositories.tender_documents import RequirementRepository
from app.repositories.tenders import TenderRepository
from tests.conftest import register_and_verify


def make_document(database, company_id: str, **overrides) -> dict:
    payload = {
        "company_id": company_id,
        "original_filename": "evidence.pdf",
        "stored_filename": "evidence.pdf",
        "title": "Audited financial statements FY 2024-25",
        "document_type": "financial_statement",
        "issuer": "Chartered Accountant",
        "mime_type": "application/pdf",
        "size_bytes": 100,
        "sha256": "a" * 64,
        "verification_status": "self_declared",
        "notes": "Average annual turnover certificates",
    }
    payload.update(overrides)
    return DocumentRepository(database).create(payload)


def make_requirement(database, tender: dict, **overrides) -> dict:
    payload = {
        "company_id": tender["company_id"],
        "tender_id": tender["id"],
        "document_id": "doc-1",
        "category": "eligibility",
        "title": "Average annual turnover",
        "obligation": "The bidder must show average annual turnover of at least INR 5 crore.",
        "excerpt": (
            "The bidder shall have an average annual turnover of at least INR 5 crore "
            "during the last three financial years."
        ),
        "excerpt_key": "turnover",
        "page_index": 3,
        "printed_page": "3",
        "clause_reference": "3.1",
        "form_reference": None,
        "mandatory": "yes",
        "deadline_text": None,
        "consequence_text": None,
        "verification_status": "verified",
        "verification_notes": None,
        "document_title": "Sample tender",
        "source_url": "https://example.gov.in/tender/road-14",
        "origin": "ai",
        "text_source": "text_layer",
    }
    payload.update(overrides)
    return RequirementRepository(database).create(payload)


def test_assessment_keeps_gate_unknown_until_evidence_is_confirmed(
    client: TestClient, database, auth_headers: dict[str, str], tender: dict
):
    document = make_document(database, tender["company_id"])
    requirement = make_requirement(database, tender)

    response = client.get(f"/api/tenders/{tender['id']}/assessment", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["eligibility"]["status"] == "unknown"
    assert body["eligibility"]["pass_count"] == 0
    assert body["eligibility"]["unknown_count"] == 1
    assert body["score"]["gating_status"] == "unknown"
    assert "cannot override" not in body["score"]["explanation"]

    evidence = client.get(
        f"/api/tenders/{tender['id']}/requirements/{requirement['id']}/evidence",
        headers=auth_headers,
    )
    assert evidence.status_code == 200
    candidates = evidence.json()["candidates"]
    assert candidates
    assert candidates[0]["document_id"] == document["id"]
    assert candidates[0]["score"] >= 0.25

    decided = client.post(
        f"/api/tenders/{tender['id']}/requirements/{requirement['id']}/evidence",
        headers=auth_headers,
        json={"document_id": document["id"], "status": "confirmed"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "confirmed"

    after = client.get(f"/api/tenders/{tender['id']}/assessment", headers=auth_headers)
    assert after.json()["eligibility"]["status"] == "pass"
    assert after.json()["eligibility"]["items"][0]["gate"] == "pass"
    assert after.json()["score"]["gating_status"] == "pass"


def test_expired_or_contradicted_evidence_never_passes(
    client: TestClient, database, auth_headers: dict[str, str], tender: dict
):
    expired = make_document(
        database,
        tender["company_id"],
        title="Expired ISO 9001 certificate",
        document_type="certificate",
        expiry_date=date.today() - timedelta(days=1),
        notes="ISO 9001 quality certificate",
    )
    requirement = make_requirement(
        database,
        tender,
        category="technical",
        title="ISO 9001 certification",
        obligation="The bidder must hold a valid ISO 9001 certification.",
        excerpt="The bidder must hold a valid ISO 9001 certification.",
        clause_reference="4.2",
    )

    confirmed = client.post(
        f"/api/tenders/{tender['id']}/requirements/{requirement['id']}/evidence",
        headers=auth_headers,
        json={"document_id": expired["id"], "status": "confirmed"},
    )
    assert confirmed.status_code == 200

    assessment = client.get(f"/api/tenders/{tender['id']}/assessment", headers=auth_headers).json()
    item = assessment["eligibility"]["items"][0]
    assert item["gate"] == "unknown"
    assert "expired" in item["reason"].lower()

    contradicted = client.post(
        f"/api/tenders/{tender['id']}/requirements/{requirement['id']}/evidence",
        headers=auth_headers,
        json={"document_id": expired["id"], "status": "contradicted"},
    )
    assert contradicted.status_code == 200
    assessment = client.get(f"/api/tenders/{tender['id']}/assessment", headers=auth_headers).json()
    assert assessment["eligibility"]["status"] == "fail"
    assert assessment["score"]["gating_status"] == "fail"
    assert "cannot override" in assessment["score"]["explanation"]


def test_unverified_requirement_cannot_be_gated_even_with_evidence(
    client: TestClient, database, auth_headers: dict[str, str], tender: dict
):
    document = make_document(database, tender["company_id"])
    requirement = make_requirement(
        database,
        tender,
        verification_status="needs_review",
        title="Turnover requirement needing visual review",
    )
    client.post(
        f"/api/tenders/{tender['id']}/requirements/{requirement['id']}/evidence",
        headers=auth_headers,
        json={"document_id": document["id"], "status": "confirmed"},
    )
    assessment = client.get(f"/api/tenders/{tender['id']}/assessment", headers=auth_headers).json()
    item = assessment["eligibility"]["items"][0]
    assert item["gate"] == "unknown"
    assert "citation" in item["reason"].lower()


def test_checklist_is_tender_specific_and_idempotent(
    client: TestClient, database, auth_headers: dict[str, str], tender: dict
):
    database.tenders.update_one(
        {"_id": tender["id"]},
        {"$set": {"deadline": datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)}},
    )
    make_requirement(
        database,
        tender,
        title="Submit bid security",
        category="submission",
        obligation="Submit a bid security of INR 2,00,000.",
        excerpt="A bid security of INR 2,00,000 must be submitted with the bid.",
        mandatory="yes",
        consequence_text="Bids without bid security shall be rejected.",
        clause_reference="3.2",
    )
    make_requirement(
        database,
        tender,
        title="Liquidated damages",
        category="performance",
        obligation="Liquidated damages apply for delay.",
        excerpt="Liquidated damages of 0.5 percent per week shall apply.",
        mandatory="no",
        consequence_text="Liquidated damages of 0.5 percent per week shall apply.",
    )

    generated = client.post(
        f"/api/tenders/{tender['id']}/checklist/generate", headers=auth_headers
    )
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["created"] == 1
    assert body["skipped"] == 0
    task = next(item for item in body["items"] if item["title"] == "Submit bid security")
    assert task["acceptance_criteria"]
    assert task["evidence_check"]
    assert task["due_at"]
    assert task["consequence"] == "Bids without bid security shall be rejected."
    assert task["clause_reference"] == "3.2"
    assert task["status"] == "missing"

    again = client.post(
        f"/api/tenders/{tender['id']}/checklist/generate", headers=auth_headers
    ).json()
    assert again["created"] == 0
    assert again["skipped"] == 1

    updated = client.patch(
        f"/api/checklist/{task['id']}",
        headers=auth_headers,
        json={"status": "complete", "owner": "Asha"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "complete"
    assert updated.json()["owner"] == "Asha"

    listing = client.get(f"/api/tenders/{tender['id']}/checklist", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    legal = client.get(f"/api/tenders/{tender['id']}/legal", headers=auth_headers)
    assert legal.status_code == 200
    assert legal.json()["total"] == 2
    assert any(
        item["category"] == "performance" for item in legal.json()["items"]
    )
    assert "not legal advice" in legal.json()["disclaimer"]


def test_assessment_is_company_scoped(
    client: TestClient, database, auth_headers: dict[str, str], tender: dict, fake_email
):
    requirement = make_requirement(database, tender)
    other = register_and_verify(
        client,
        fake_email,
        email="assessor-other@example.com",
        company_name="Other Assessor",
    )
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    assert (
        client.get(f"/api/tenders/{tender['id']}/assessment", headers=other_headers).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/tenders/{tender['id']}/requirements/{requirement['id']}/evidence",
            headers=other_headers,
        ).status_code
        == 404
    )


def test_empty_assessment_is_honest(client: TestClient, auth_headers: dict[str, str], tender: dict):
    body = client.get(f"/api/tenders/{tender['id']}/assessment", headers=auth_headers).json()
    assert body["eligibility"]["status"] == "unknown"
    assert body["score"]["band"] == "insufficient"
    assert body["counts"]["total"] == 0
    assert "No mandatory eligibility" in body["eligibility"]["message"]


def test_requirement_evidence_is_scoped_to_the_tender_in_the_url(
    client: TestClient, database, auth_headers: dict[str, str], tender: dict
):
    other_tender = {
        "_id": "other-tender-id",
        "company_id": tender["company_id"],
        "title": "Other tender",
        "authority": "Other authority",
        "reference_number": "OTHER/1",
        "status": "saved",
    }
    database.tenders.insert_one(other_tender)
    requirement = make_requirement(
        database,
        {**other_tender, "id": other_tender["_id"]},
        excerpt="The bidder must provide a separate bank guarantee.",
    )

    response = client.get(
        f"/api/tenders/{tender['id']}/requirements/{requirement['id']}/evidence",
        headers=auth_headers,
    )
    assert response.status_code == 404
    decision = client.post(
        f"/api/tenders/{tender['id']}/requirements/{requirement['id']}/evidence",
        headers=auth_headers,
        json={"document_id": "missing", "status": "confirmed"},
    )
    assert decision.status_code == 404
