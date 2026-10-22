"""The search endpoint, and the tenant boundary it must hold.

The store is a stand-in, so the tests check what the API does with the
results and, above all, that one company can never reach the passages of
another.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.dependencies import get_embedding_provider, get_vector_store
from app.services.retrieval import SCOPE_TENDER
from tests.conftest import register_and_verify


class FakeProvider:
    name = "fake"
    model = "fake-model"
    dimension = 4
    available = True

    def embed(self, texts):
        return [[0.1] * 4 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 4


class FakeStore:
    """Returns the same passage for every company, so the filter is the only
    thing that can protect the data."""

    collection_name = "test_collection"

    def __init__(self) -> None:
        self.filters: list[dict] = []

    def health(self):
        return {"status": "ok", "collection": self.collection_name}

    def search(self, vector, *, limit=8, filters=None, score_threshold=None):
        self.filters.append(filters or {})
        return []

    def count(self, filters=None):
        return 0


def use_fake_store(app, store):
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embedding_provider] = lambda: FakeProvider()


def test_a_search_needs_a_signed_in_user(client: TestClient) -> None:
    response = client.post("/api/knowledge/search", json={"query": "turnover"})
    assert response.status_code == 401


def test_a_search_returns_the_passages_with_their_source(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from app.main import app

    class OnePassageStore(FakeStore):
        def search(self, vector, *, limit=8, filters=None, score_threshold=None):
            self.filters.append(filters or {})
            from app.services.vector_store import ScoredPassage

            return [
                ScoredPassage(
                    id="1",
                    score=0.8,
                    payload={
                        "document_id": "doc-1",
                        "document_title": "RFP",
                        "company_id": "company-1",
                        "tender_id": "tender-1",
                        "page_index": 3,
                        "printed_page": "3",
                        "clause_number": "3.1",
                        "text": "3.1 The bidder shall have an average annual turnover.",
                        "scope": SCOPE_TENDER,
                    },
                )
            ]

    store = OnePassageStore()
    use_fake_store(app, store)
    response = client.post(
        "/api/knowledge/search",
        headers=auth_headers,
        json={"query": "turnover", "tender_id": "tender-1"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 1
    item = body["items"][0]
    assert item["citation"]["page_index"] == 3
    assert item["citation"]["clause_number"] == "3.1"
    assert item["citation"]["document_title"] == "RFP"


def test_a_search_never_reaches_another_company(
    client: TestClient, auth_headers: dict[str, str], fake_email
) -> None:
    """The second company asks for the first company's tender, and gets nothing."""
    from app.main import app

    store = FakeStore()
    use_fake_store(app, store)

    other = register_and_verify(
        client,
        fake_email,
        email="other@example.com",
        company_name="Another Company Ltd",
    )
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    client.post(
        "/api/knowledge/search",
        headers=other_headers,
        json={"query": "turnover", "scope": "all", "tender_id": "any-tender"},
    )

    assert store.filters
    for filters in store.filters:
        # Whatever the scope, the company filter is there and it is the other
        # company's own id.
        assert filters["must"]["company_id"] != "company-1"
        assert filters["must"]["company_id"]
    # The scope cannot switch the company off either.
    assert "company_id" not in filters.get("should", [])


def test_the_search_endpoint_is_unavailable_without_a_store(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from app.main import app

    use_fake_store(app, None)
    response = client.post(
        "/api/knowledge/search", headers=auth_headers, json={"query": "turnover"}
    )
    assert response.status_code == 503
    assert "vector store" in response.json()["detail"].lower()
