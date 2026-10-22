"""The knowledge endpoints.

The tests use a fake store and a fake embedding provider, so they run without a
Qdrant server. What matters here is the contract: retrieval being unavailable is
reported, never raised, and the rest of the application is unaffected.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.dependencies import get_embedding_provider, get_vector_store


class FakeProvider:
    name = "fake"
    model = "fake-v1"
    dimension = 16
    available = True

    def embed(self, texts):
        return [[0.0] * self.dimension for _ in texts]

    def embed_query(self, text):
        return [0.0] * self.dimension


class FakeStore:
    collection_name = "test_collection"

    def __init__(self) -> None:
        self.created = False

    def health(self):
        return {
            "status": "ok",
            "url": "http://localhost:6333",
            "collection": self.collection_name,
            "collection_exists": True,
            "collections": [self.collection_name],
        }

    def ensure_collection(self, dimension, *, distance="Cosine"):
        self.created = True
        return True

    def count(self, filters=None):
        return 0


def use_fakes(app, store=None, provider=None):
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embedding_provider] = lambda: provider or FakeProvider()


def test_the_knowledge_health_reports_the_store_and_the_model(client: TestClient) -> None:
    from app.main import app as fastapi_app

    use_fakes(fastapi_app, FakeStore())
    response = client.get("/api/knowledge/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["vector_store"]["status"] == "ok"
    assert body["embeddings"]["provider"] == "fake"
    assert body["embeddings"]["dimension"] == 16


def test_the_collection_is_created_with_the_provider_dimension(
    client: TestClient,
) -> None:
    from app.main import app as fastapi_app

    store = FakeStore()
    use_fakes(fastapi_app, store)
    response = client.get("/api/knowledge/collection")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dimension"] == 16
    assert store.created is True


def test_a_disabled_store_is_reported_not_failing(client: TestClient) -> None:
    from app.main import app as fastapi_app

    use_fakes(fastapi_app, None)
    response = client.get("/api/knowledge/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disabled"
    assert body["enabled"] is False


def test_the_application_is_healthy_without_a_vector_store(
    client: TestClient,
) -> None:
    from app.main import app as fastapi_app

    use_fakes(fastapi_app, None)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "ok"
    assert body["vector_store"] == "disabled"
    # The rest of the application keeps working: an unauthenticated call is
    # still refused, but by the auth layer and not by the vector store.
    assert client.get("/api/companies/me").status_code == 401
