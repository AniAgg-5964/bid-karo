from __future__ import annotations

import mongomock
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.core.database import Database, get_database
from app.core.dependencies import get_storage
from app.main import app
from app.repositories.tenders import TenderRepository
from app.services.storage import StorageService

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"

SAMPLE_PAGES = [
    (
        "Section 3 - Eligibility Criteria. The bidder shall have an average annual "
        "turnover of at least INR 5 crore during the last three financial years. "
        "A bid security of INR 2,00,000 must be submitted with the bid."
    ),
    (
        "Section 5 - Submission of Bids. Bids must be submitted before 15 November 2026 "
        "at 17:00 IST through the online portal. Late bids shall be rejected."
    ),
    (
        "Section 8 - Penalties. Liquidated damages of 0.5 percent of the contract value "
        "per week of delay shall apply, subject to a maximum of 10 percent."
    ),
]


def make_pdf(pages: list[str]) -> bytes:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 790), text, fontsize=11, fontname="helv")
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture
def sample_pdf() -> bytes:
    return make_pdf(SAMPLE_PAGES)


@pytest.fixture
def database() -> Database:
    database = Database(
        "mongodb://localhost:27017",
        "bidkaro_test",
        client=mongomock.MongoClient(tz_aware=True),
    )
    database.init_indexes()
    return database


@pytest.fixture
def client(database: Database, tmp_path):
    app.dependency_overrides[get_database] = lambda: database
    app.dependency_overrides[get_storage] = lambda: StorageService(tmp_path / "storage", 2)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "password": "StrongPass123",
            "full_name": "Asha Rao",
            "company_name": "Asha Infra Pvt Ltd",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def company_id(client: TestClient, auth_headers: dict[str, str]) -> str:
    response = client.get("/api/companies/me", headers=auth_headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]


@pytest.fixture
def tender(database: Database, company_id: str) -> dict:
    return TenderRepository(database).create(
        {
            "company_id": company_id,
            "title": "Sample road tender",
            "authority": "Demo State Infrastructure Authority",
            "reference_number": "DSIA/RFP/2026/ROAD-014",
            "deadline": None,
            "status": "saved",
            "source_url": "https://example.gov.in/tender/road-14",
            "source_type": "official",
            "source_retrieved_at": None,
            "description": "Synthetic fixture used by the test suite.",
        }
    )
