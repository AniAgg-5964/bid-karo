"""The retrieval layer's own endpoints.

Phase 1 exposes the health of the vector store and the embedding provider, so
a developer can see whether retrieval is usable. Phase 2 adds the indexing:
the documents are read, split into passages, embedded and written, and the
state of that work is visible here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.database import Database, get_database
from app.core.dependencies import (
    get_current_company,
    get_current_user,
    get_embedding_provider,
    get_vector_store,
)
from app.models.jobs import JobOut
from app.repositories.documents import DocumentRepository
from app.repositories.tender_documents import TenderDocumentRepository
from app.services.embeddings import EmbeddingProvider
from app.services.retrieval import SCOPES, RetrievalService
from app.services.vector_store import (
    QdrantVectorStore,
    VectorStoreError,
    VectorStoreUnavailable,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

INDEX_STEP = {"key": "indexing", "label": "Index the documents for retrieval"}


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
    dimension = None
    try:
        dimension = store.collection_dimension()
    except Exception:  # noqa: BLE001 - health must not raise
        dimension = None
    model_dimension = embedding_state.get("dimension")
    mismatch = bool(dimension and model_dimension and dimension != model_dimension)
    if mismatch:
        state = {
            **state,
            "status": "degraded",
            "collection_dimension": dimension,
            "reason": (
                f"The collection holds vectors of {dimension} dimensions, but the "
                f"embedding model produces {model_dimension}. Delete the collection "
                f"and index again, or use the model it was built with."
            ),
        }
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
    except (VectorStoreUnavailable, VectorStoreError) as exc:
        return {
            "status": "unavailable",
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


# ------------------------------------------------------------------ indexing


@router.post("/tenders/{tender_id}/index", response_model=JobOut, status_code=202)
def index_tender_documents(
    tender_id: str,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> JobOut:
    """Queue the indexing of a tender's documents.

    The work runs in the job worker, so a large document does not hold the
    request open.
    """
    from app.services.analysis import build_handlers
    from app.services.job_runner import JobRunner

    runner = JobRunner(db, handlers=build_handlers())
    job = runner.enqueue(
        "knowledge_index",
        company["id"],
        tender_id=tender_id,
        payload={"user_id": user["id"]},
        steps=[INDEX_STEP],
    )
    return JobOut.model_validate(job)


@router.get("/tenders/{tender_id}/status")
def tender_index_status(
    tender_id: str,
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> dict:
    """How far the indexing of a tender's documents got."""
    documents = TenderDocumentRepository(db).list_for_tender(company["id"], tender_id)
    items = [
        {
            "document_id": document.get("id"),
            "title": document.get("title"),
            "kind": document.get("kind"),
            "index_status": document.get("index_status") or "pending",
            "indexed_at": document.get("indexed_at"),
            "index_chunk_count": document.get("index_chunk_count") or 0,
            "index_model": document.get("index_model"),
            "index_error": document.get("index_error"),
        }
        for document in documents
    ]
    return {
        "tender_id": tender_id,
        "documents": len(items),
        "indexed": sum(1 for item in items if item["index_status"] == "indexed"),
        "failed": sum(1 for item in items if item["index_status"] == "failed"),
        "pending": sum(1 for item in items if item["index_status"] == "pending"),
        "items": items,
    }


@router.get("/documents/status")
def company_index_status(
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> dict:
    """How far the indexing of the company's own documents got."""
    documents, _total = DocumentRepository(db).list_for_company(company["id"], limit=500)
    items = [
        {
            "document_id": document.get("id"),
            "title": document.get("title"),
            "document_type": document.get("document_type"),
            "index_status": document.get("index_status") or "pending",
            "indexed_at": document.get("indexed_at"),
            "index_chunk_count": document.get("index_chunk_count") or 0,
            "index_model": document.get("index_model"),
            "index_error": document.get("index_error"),
        }
        for document in documents
    ]
    return {
        "documents": len(items),
        "indexed": sum(1 for item in items if item["index_status"] == "indexed"),
        "failed": sum(1 for item in items if item["index_status"] == "failed"),
        "pending": sum(1 for item in items if item["index_status"] == "pending"),
        "items": items,
    }


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    scope: str = Field(default="tender")
    tender_id: str | None = None
    limit: int = Field(default=8, ge=1, le=50)
    min_score: float | None = Field(default=None, ge=-1.0, le=1.0)


class SearchResponse(BaseModel):
    query: str
    scope: str
    tender_id: str | None = None
    count: int
    items: list[dict[str, Any]]


def get_retrieval_service(
    db: Database = Depends(get_database),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    store: QdrantVectorStore | None = Depends(get_vector_store),
    settings: Settings = Depends(get_settings),
) -> RetrievalService:
    return RetrievalService(db, embeddings, store, settings=settings)


@router.post("/search", response_model=SearchResponse)
def search_knowledge(
    payload: SearchRequest,
    company: dict = Depends(get_current_company),
    service: RetrievalService = Depends(get_retrieval_service),
) -> SearchResponse:
    """Find the passages that answer a question.

    The company comes from the authenticated user, so a search can only ever
    reach the passages of that company.
    """
    scope = payload.scope if payload.scope in SCOPES else "tender"
    try:
        passages = service.search(
            query=payload.query,
            company_id=company["id"],
            scope=scope,
            tender_id=payload.tender_id,
            limit=payload.limit,
            min_score=payload.min_score,
        )
    except (VectorStoreUnavailable, VectorStoreError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return SearchResponse(
        query=payload.query,
        scope=scope,
        tender_id=payload.tender_id,
        count=len(passages),
        items=[passage.to_dict() for passage in passages],
    )


@router.post("/documents/index", response_model=JobOut, status_code=202)
def index_company_documents(
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> JobOut:
    """Queue the indexing of the company's own documents."""
    from app.services.analysis import build_handlers
    from app.services.job_runner import JobRunner

    runner = JobRunner(db, handlers=build_handlers())
    job = runner.enqueue(
        "knowledge_index",
        company["id"],
        payload={"user_id": user["id"], "scope": "company"},
        steps=[{"key": "index_company", "label": "Index the company documents"}],
    )
    return JobOut.model_validate(job)
