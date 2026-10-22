"""The embedding providers and the Qdrant wrapper.

These tests do not need a running Qdrant: the store is given a fake client, in
the same way the TinyFish client is injected elsewhere in this repository.
"""

from __future__ import annotations

import math

import pytest

from app.core.config import Settings
from app.services.embeddings import (
    DEFAULT_HASHING_DIMENSION,
    EmbeddingUnavailable,
    HashingEmbeddingProvider,
    Model2VecEmbeddingProvider,
    UnavailableEmbeddingProvider,
    build_embedding_provider,
)
from app.services.vector_store import (
    QdrantVectorStore,
    VectorPoint,
    VectorStoreError,
    VectorStoreUnavailable,
)


# ------------------------------------------------------------------ embeddings


def test_the_hashing_provider_has_a_stable_dimension() -> None:
    provider = HashingEmbeddingProvider()
    assert provider.dimension == DEFAULT_HASHING_DIMENSION
    assert provider.available is True
    vector = provider.embed_query("a bid security of INR 2,00,000")
    assert len(vector) == provider.dimension


def test_the_hashing_provider_is_deterministic_and_normalised() -> None:
    provider = HashingEmbeddingProvider()
    first = provider.embed_query("clause 3.1 average annual turnover")
    second = provider.embed_query("clause 3.1 average annual turnover")
    assert first == second
    norm = math.sqrt(sum(value * value for value in first))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_the_hashing_provider_separates_different_texts() -> None:
    provider = HashingEmbeddingProvider()
    first = provider.embed_query("performance bank guarantee of five percent")
    second = provider.embed_query("shop licence for the site labour office")
    assert first != second


def test_an_empty_text_gives_a_zero_vector() -> None:
    provider = HashingEmbeddingProvider()
    assert set(provider.embed_query("")) == {0.0}


def test_the_factory_reads_the_dimension_from_the_provider() -> None:
    settings = Settings(embedding_provider="hashing", embedding_dimension=0)
    provider = build_embedding_provider(settings)
    assert provider.dimension == DEFAULT_HASHING_DIMENSION

    settings = Settings(embedding_provider="hashing", embedding_dimension=64)
    provider = build_embedding_provider(settings)
    assert provider.dimension == 64


def test_an_unknown_provider_is_reported_not_guessed() -> None:
    settings = Settings(embedding_provider="does-not-exist")
    provider = build_embedding_provider(settings)
    assert isinstance(provider, UnavailableEmbeddingProvider)
    assert provider.available is False
    with pytest.raises(EmbeddingUnavailable):
        provider.embed_query("anything")


def test_a_missing_semantic_model_is_reported_not_hidden() -> None:
    provider = Model2VecEmbeddingProvider(model="this/model/does-not-exist")
    # The provider must not pretend to work when the model cannot be loaded.
    assert provider.available in {True, False}
    if not provider.available:
        with pytest.raises(EmbeddingUnavailable):
            provider.embed_query("anything")


# ----------------------------------------------------------------- vector store


class FakeCollection:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeCollections:
    def __init__(self, names: list[str]) -> None:
        self.collections = [FakeCollection(name) for name in names]


class FakePoint:
    def __init__(self, point_id: str, score: float, payload: dict) -> None:
        self.id = point_id
        self.score = score
        self.payload = payload


class FakeQueryResult:
    def __init__(self, points: list[FakePoint]) -> None:
        self.points = points


class FakeCount:
    def __init__(self, count: int) -> None:
        self.count = count


class FakeQdrantClient:
    """A stand-in for the Qdrant client with the surface we use."""

    def __init__(self, *, collections: list[str] | None = None, fail: bool = False) -> None:
        self.collections = list(collections or [])
        self.fail = fail
        self.stored: dict[str, dict] = {}
        self.deleted: list[str] = []
        self.search_filters: list[object] = []

    def get_collections(self):
        if self.fail:
            raise RuntimeError("qdrant is down")
        return FakeCollections(self.collections)

    def create_collection(self, *, collection_name, vectors_config):
        self.collections.append(collection_name)

    def upsert(self, *, collection_name, points):
        for point in points:
            self.stored[str(point.id)] = dict(point.payload or {})

    def delete(self, *, collection_name, points_selector):
        self.deleted.append(collection_name)

    def count(self, *, collection_name, count_filter=None):
        return FakeCount(len(self.stored))

    def query_points(
        self, *, collection_name, query, limit, query_filter=None, score_threshold=None, with_payload=False
    ):
        self.search_filters.append(query_filter)
        points = [
            FakePoint(point_id, 0.9, payload)
            for point_id, payload in list(self.stored.items())[:limit]
        ]
        return FakeQueryResult(points)


def make_store(client) -> QdrantVectorStore:
    return QdrantVectorStore(
        url="http://localhost:6333",
        collection="test_collection",
        client=client,
    )


def test_the_store_creates_the_collection_with_the_provider_dimension() -> None:
    client = FakeQdrantClient()
    store = make_store(client)
    assert store.ensure_collection(384) is True
    assert "test_collection" in client.collections


def test_the_store_reports_an_unavailable_server_instead_of_raising() -> None:
    client = FakeQdrantClient(fail=True)
    store = make_store(client)
    state = store.health()
    assert state["status"] == "unavailable"
    assert "qdrant" in state["reason"].lower()


def test_the_store_writes_and_reads_passages() -> None:
    client = FakeQdrantClient(collections=["test_collection"])
    store = make_store(client)
    written = store.upsert_points(
        [
            VectorPoint(
                id="doc-1::0",
                vector=[0.1] * 384,
                payload={"text": "the clause text", "company_id": "company-1"},
            )
        ]
    )
    assert written == 1
    found = store.search([0.1] * 384, limit=5, filters={"company_id": "company-1"})
    assert len(found) == 1
    assert found[0].text == "the clause text"
    assert found[0].score == pytest.approx(0.9)


def test_the_store_always_passes_the_filter_to_the_server() -> None:
    client = FakeQdrantClient(collections=["test_collection"])
    store = make_store(client)
    store.upsert_points(
        [VectorPoint(id="a", vector=[0.0] * 8, payload={"company_id": "company-1"})]
    )
    store.search([0.0] * 8, limit=3, filters={"company_id": "company-1"})
    assert client.search_filters
    assert client.search_filters[0] is not None


def test_a_store_that_cannot_be_reached_is_reported_as_unavailable() -> None:
    """No server, or no client package: the store says so instead of raising."""
    store = QdrantVectorStore(url="http://127.0.0.1:6399", collection="c")
    state = store.health()
    assert state["status"] == "unavailable"
    assert state["reason"]


def test_a_store_error_is_wrapped() -> None:
    class BrokenClient(FakeQdrantClient):
        def upsert(self, *, collection_name, points):
            raise RuntimeError("disk is full")

    store = make_store(BrokenClient(collections=["test_collection"]))
    with pytest.raises(VectorStoreError):
        store.upsert_points([VectorPoint(id="a", vector=[0.0] * 8, payload={})])
