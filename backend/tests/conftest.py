from __future__ import annotations

import mongomock
import pytest
from fastapi.testclient import TestClient

from app.core.database import Database, get_database
from app.core.dependencies import get_storage
from app.main import app
from app.services.storage import StorageService

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


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
