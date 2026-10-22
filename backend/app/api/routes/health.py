from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.database import Database, get_database
from app.core.dependencies import get_vector_store
from app.services.vector_store import QdrantVectorStore

router = APIRouter(tags=["health"])


@router.get("/health")
def health(
    db: Database = Depends(get_database),
    store: QdrantVectorStore | None = Depends(get_vector_store),
) -> dict:
    try:
        db.ping()
        database = "ok"
    except Exception:
        database = "unavailable"

    # The vector store is an index. When it is down the application is degraded
    # for retrieval, but it is still serving everything else.
    if store is None:
        vector_store = "disabled"
    else:
        try:
            vector_store = store.health().get("status", "unavailable")
        except Exception:
            vector_store = "unavailable"

    status = "ok" if database == "ok" and vector_store in {"ok", "disabled"} else "degraded"
    return {
        "status": status,
        "service": get_settings().app_name,
        "database": database,
        "vector_store": vector_store,
    }
