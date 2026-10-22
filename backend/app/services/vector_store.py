"""The Qdrant vector store.

Everything Qdrant-specific lives here. The rest of the application talks to
this interface, never to the client directly.

Two rules shape the code:

* **Qdrant is an index, not a source of truth.** The documents, the
  requirements and the decisions stay in MongoDB and on disk. A collection can
  be wiped and rebuilt from them.
* **It must never take the application down.** If Qdrant is missing, stopped
  or slow, the calls here raise :class:`VectorStoreUnavailable` and the
  caller decides. Nothing here is allowed to break an unrelated request.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

DISTANCE_COSINE = "Cosine"


class VectorStoreUnavailable(RuntimeError):
    """The vector store could not be reached or is not usable right now."""


class VectorStoreError(RuntimeError):
    """The vector store rejected an operation."""


@dataclass(slots=True)
class VectorPoint:
    """One passage to store."""

    id: str
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScoredPassage:
    """One passage returned by a search."""

    id: str
    score: float
    payload: dict[str, Any]

    @property
    def text(self) -> str:
        return str(self.payload.get("text") or "")


def _require_client():
    try:
        from qdrant_client import QdrantClient  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise VectorStoreUnavailable(
            "The qdrant-client package is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc
    return QdrantClient


class QdrantVectorStore:
    """A thin, defensive wrapper over the Qdrant client."""

    def __init__(
        self,
        *,
        url: str,
        api_key: str = "",
        collection: str = "bidkaro_knowledge",
        timeout_seconds: int = 10,
        client: Any | None = None,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.collection_name = collection
        self.timeout_seconds = timeout_seconds
        self._client = client

    # ------------------------------------------------------------------ setup
    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "QdrantVectorStore":
        current = settings or get_settings()
        return cls(
            url=current.qdrant_url,
            api_key=current.qdrant_api_key,
            collection=current.qdrant_collection_name,
            timeout_seconds=current.qdrant_timeout_seconds,
        )

    @property
    def client(self):
        """The Qdrant client, created on first use."""
        if self._client is None:
            factory = _require_client()
            try:
                self._client = factory(
                    url=self.url,
                    api_key=self.api_key or None,
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001 - the client must not raise here
                raise VectorStoreUnavailable(f"Qdrant could not be reached: {exc}") from exc
        return self._client

    # ----------------------------------------------------------------- health
    def health(self) -> dict[str, Any]:
        """A report a health endpoint can show. Never raises."""
        if not self._client:
            try:
                self.client  # noqa: B018 - the point is to attempt the connection
            except VectorStoreUnavailable as exc:
                return {
                    "status": "unavailable",
                    "reason": str(exc),
                    "collection": self.collection_name,
                    "url": self.url,
                }
        try:
            collections = [
                item.name for item in self.client.get_collections().collections
            ]
        except Exception as exc:  # noqa: BLE001 - health must not raise
            return {
                "status": "unavailable",
                "reason": f"Qdrant did not answer: {exc}",
                "collection": self.collection_name,
                "url": self.url,
            }
        return {
            "status": "ok",
            "url": self.url,
            "collection": self.collection_name,
            "collection_exists": self.collection_name in collections,
            "collections": collections,
        }

    def ensure_collection(self, dimension: int, *, distance: str = DISTANCE_COSINE) -> bool:
        """Create the collection if it is missing. True when it is ready."""
        if dimension <= 0:
            raise VectorStoreError("A collection needs a positive vector size.")
        try:
            existing = [
                item.name for item in self.client.get_collections().collections
            ]
            if self.collection_name in existing:
                return True
            from qdrant_client.models import Distance, VectorParams  # type: ignore[import-not-found]

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=Distance.COSINE
                    if distance == DISTANCE_COSINE
                    else Distance.DOT,
                ),
            )
            return True
        except VectorStoreUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as a store failure
            raise VectorStoreError(f"The collection could not be created: {exc}") from exc

    # ----------------------------------------------------------------- writing
    def upsert_points(self, points: Sequence[VectorPoint]) -> int:
        """Store passages. Returns how many were written."""
        if not points:
            return 0
        try:
            from qdrant_client.models import PointStruct  # type: ignore[import-not-found]

            payload = [
                PointStruct(id=point.id, vector=point.vector, payload=point.payload)
                for point in points
            ]
            self.client.upsert(collection_name=self.collection_name, points=payload)
            return len(payload)
        except VectorStoreUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as a store failure
            raise VectorStoreError(f"The passages could not be stored: {exc}") from exc

    def delete_document(self, document_id: str) -> int:
        """Remove every passage of one document. Returns how many were removed."""
        try:
            from qdrant_client.models import FilterSelector, Filter  # type: ignore[import-not-found]

            selector = FilterSelector(
                filter=Filter(
                    must=[
                        {"key": "document_id", "match": {"value": document_id}},
                    ]
                )
            )
            self.client.delete(collection_name=self.collection_name, points_selector=selector)
            return 1
        except VectorStoreUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as a store failure
            raise VectorStoreError(f"The passages could not be removed: {exc}") from exc

    def count(self, filters: dict[str, Any] | None = None) -> int:
        """How many passages are stored, optionally inside a filter."""
        try:
            result = self.client.count(
                collection_name=self.collection_name,
                count_filter=_to_filter(filters) if filters else None,
            )
            return int(getattr(result, "count", 0))
        except VectorStoreUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as a store failure
            raise VectorStoreError(f"The passages could not be counted: {exc}") from exc

    # ----------------------------------------------------------------- reading
    def search(
        self,
        vector: list[float],
        *,
        limit: int = 8,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[ScoredPassage]:
        """Search inside the collection, always inside the given filter."""
        try:
            from qdrant_client.models import Filter  # type: ignore[import-not-found]

            query_filter = _to_filter(filters) if filters else None
            hits = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                limit=max(limit, 1),
                query_filter=query_filter,
                score_threshold=score_threshold,
                with_payload=True,
            ).points
            return [
                ScoredPassage(id=str(hit.id), score=float(hit.score), payload=dict(hit.payload or {}))
                for hit in hits
            ]
        except VectorStoreUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as a store failure
            raise VectorStoreError(f"The passages could not be searched: {exc}") from exc


def _to_filter(filters: dict[str, Any] | None):
    """Turn a simple filter mapping into a Qdrant filter."""
    if not filters:
        return None
    from qdrant_client.models import Filter  # type: ignore[import-not-found]

    must = []
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            must.append({"key": key, "match": {"any": list(value)}})
        else:
            must.append({"key": key, "match": {"value": value}})
    if not must:
        return None
    return Filter(must=must)


def build_vector_store(settings: Settings | None = None) -> QdrantVectorStore | None:
    """The configured vector store, or None when it is switched off."""
    current = settings or get_settings()
    if not current.qdrant_enabled:
        return None
    return QdrantVectorStore.from_settings(current)


def iter_batches(items: Sequence[Any], size: int) -> Iterable[list[Any]]:
    """Split a list into batches, for embedding and writing in steps."""
    step = max(size, 1)
    for index in range(0, len(items), step):
        yield list(items[index : index + step])
