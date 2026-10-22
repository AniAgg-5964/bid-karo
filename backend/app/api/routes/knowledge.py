"""The retrieval layer's own endpoints.

Phase 1 exposes the health of the vector store and the embedding provider, so
a developer can see whether retrieval is usable. The indexing, search and
findings routes arrive with the phases that need them.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.dependencies import get_embedding_provider, get_vector_store
from app.services.embeddings import EmbeddingProvider
from app.services.vector_store import QdrantVectorStore, VectorStoreUnavailable

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/health")
def knowledge_health(
    store: QdrantVectorStore | None = Depends(get_vector_store),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Whether retrieval is available, and with which model."""
    embedding_state = {
        "provider": embeddings.name,
        "model": embeddings.model,
        "available": False,
        "dimension": None,
        "reason": None,
    }
    try:
        embedding_state["available"] = embeddings.available
        embedding_state["dimension"] = embeddings.dimension
    except Exception as exc:  # noqa: BLE001 - health must not raise
        embedding_state["reason"] = str(exc)

    if store is None:
        return {
            "status": "disabled",
            "enabled": False,
            "vector_store": {
                "status": "disabled",
                "reason": "QDRANT_ENABLED is false.",
                "collection": settings.qdrant_collection_name,
                "url": settings.qdrant_url,
            },
            "embeddings": embedding_state,
        }

    state = store.health()
    return {
        "status": "ok" if state.get("status") == "ok" else "degraded",
        "enabled": True,
        "vector_store": state,
        "embeddings": embedding_state,
    }


@router.get("/collection")
def collection_state(
    store: QdrantVectorStore | None = Depends(get_vector_store),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
) -> dict:
    """Create the collection if it is missing, and report the result."""
    if store is None:
        return {"status": "disabled", "collection": None, "created": False}
    try:
        dimension = embeddings.dimension
    except Exception as exc:  # noqa: BLE001 - reported honestly
        return {
            "status": "unavailable",
            "collection": store.collection_name,
            "created": False,
            "reason": str(exc),
        }
    try:
        created = store.ensure_collection(dimension)
    except VectorStoreUnavailable as exc:
        return {
            "status": "unavailable",
            "collection": store.collection_name,
            "created": False,
            "reason": str(exc),
        }
    except Exception as exc:  # noqa: BLE001 - reported honestly
        return {
            "status": "error",
            "collection": store.collection_name,
            "created": False,
            "reason": str(exc),
        }
    return {
        "status": "ok",
        "collection": store.collection_name,
        "dimension": dimension,
        "created": created,
        "points": store.count(),
    }
