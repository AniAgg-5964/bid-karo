from __future__ import annotations

import io

import mongomock
import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.core.database import Database, get_database
from app.core.dependencies import get_email_service, get_storage
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


def make_scanned_pdf(text: str) -> bytes:
    """A one-page PDF whose only content is a raster image (no text layer)."""
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 30)
    image = Image.new("RGB", (1200, 420), "white")
    draw = ImageDraw.Draw(image)
    draw.text((50, 80), text, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=80)

    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(pymupdf.Rect(30, 30, 582, 762), stream=buffer.getvalue())
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture
def scanned_pdf() -> bytes:
    return make_scanned_pdf(
        "The bidder shall have an average annual turnover of at least INR 5 crore."
    )


@pytest.fixture
def database() -> Database:
    database = Database(
        "mongodb://localhost:27017",
        "bidkaro_test",
        client=mongomock.MongoClient(tz_aware=True),
    )
    database.init_indexes()
    return database


class FakeEmailService:
    configured = True

    def __init__(self) -> None:
        self.codes: dict[tuple[str, str], str] = {}

    def send_otp(self, *, to: str, code: str, purpose: str, expires_minutes: int) -> None:
        self.codes[(to.lower(), purpose)] = code

    def code_for(self, email: str, purpose: str) -> str:
        return self.codes[(email.lower(), purpose)]


@pytest.fixture
def fake_email() -> FakeEmailService:
    return FakeEmailService()


@pytest.fixture
def client(database: Database, tmp_path, fake_email: FakeEmailService):
    app.dependency_overrides[get_database] = lambda: database
    app.dependency_overrides[get_storage] = lambda: StorageService(tmp_path / "storage", 2)
    app.dependency_overrides[get_email_service] = lambda: fake_email
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_and_verify(
    client: TestClient,
    fake_email: FakeEmailService,
    *,
    email: str = "owner@example.com",
    password: str = "StrongPass123",
    full_name: str = "Asha Rao",
    company_name: str = "Asha Infra Pvt Ltd",
) -> dict:
    registered = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "company_name": company_name,
        },
    )
    assert registered.status_code == 201, registered.text
    verified = client.post(
        "/api/auth/verify-otp",
        json={
            "email": email,
            "purpose": "verify_email",
            "code": fake_email.code_for(email, "verify_email"),
        },
    )
    assert verified.status_code == 200, verified.text
    return verified.json()


@pytest.fixture
def auth_headers(client: TestClient, fake_email: FakeEmailService) -> dict[str, str]:
    auth = register_and_verify(client, fake_email)
    return {"Authorization": f"Bearer {auth['access_token']}"}


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
