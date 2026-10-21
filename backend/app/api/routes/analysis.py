"""Starting and watching the tender analysis job, and reading what it found."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company, get_current_user
from app.models.agents import (
    ApplyRecommendationRequest,
    LegalSourceListResponse,
    LegalSourceOut,
    RecommendationListResponse,
    RecommendationOut,
)
from app.models.jobs import JobOut
from app.services.agents.legal_researcher import DISCLAIMER
from app.services.analysis import AnalysisService

router = APIRouter(prefix="/analysis", tags=["analysis"])


def get_analysis_service(db: Database = Depends(get_database)) -> AnalysisService:
    return AnalysisService(db)


@router.post(
    "/tenders/{tender_id}",
    response_model=JobOut,
    status_code=202,
)
def start_tender_analysis(
    tender_id: str,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    service: AnalysisService = Depends(get_analysis_service),
) -> JobOut:
    """Queue the analysis of a tender. The job shows what it is doing."""
    return service.start(
        tender_id=tender_id,
        company_id=company["id"],
        user_id=user["id"],
    )


@router.get("/tenders/{tender_id}", response_model=JobOut | None)
def latest_tender_analysis(
    tender_id: str,
    company: dict = Depends(get_current_company),
    service: AnalysisService = Depends(get_analysis_service),
) -> JobOut | None:
    return service.latest(tender_id=tender_id, company_id=company["id"])


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_analysis_job(
    job_id: str,
    company: dict = Depends(get_current_company),
    service: AnalysisService = Depends(get_analysis_service),
) -> JobOut:
    return service.get(job_id, company["id"])


@router.get(
    "/tenders/{tender_id}/recommendations",
    response_model=RecommendationListResponse,
)
def list_recommendations(
    tender_id: str,
    kind: str | None = Query(default=None),
    company: dict = Depends(get_current_company),
    service: AnalysisService = Depends(get_analysis_service),
) -> RecommendationListResponse:
    """What the agent proposed, with the gate's verdict on each proposal."""
    items = service.recommendations(company["id"], tender_id, kind=kind)
    return RecommendationListResponse(
        items=[RecommendationOut.model_validate(item) for item in items], total=len(items)
    )


@router.get(
    "/tenders/{tender_id}/legal-sources",
    response_model=LegalSourceListResponse,
)
def list_legal_sources(
    tender_id: str,
    company: dict = Depends(get_current_company),
    service: AnalysisService = Depends(get_analysis_service),
) -> LegalSourceListResponse:
    """Official provisions read for this tender, quoted and dated."""
    items = service.legal_sources(company["id"], tender_id)
    return LegalSourceListResponse(
        items=[LegalSourceOut.model_validate(item) for item in items],
        total=len(items),
        disclaimer=DISCLAIMER,
    )


@router.post(
    "/tenders/{tender_id}/recommendations/{recommendation_id}/apply",
    response_model=dict,
)
def apply_recommendation(
    tender_id: str,
    recommendation_id: str,
    payload: ApplyRecommendationRequest | None = None,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    service: AnalysisService = Depends(get_analysis_service),
) -> dict:
    """Turn a grounded proposal into a checklist task. A human confirms it."""
    body = payload or ApplyRecommendationRequest()
    task = service.apply_recommendation(
        company_id=company["id"],
        tender_id=tender_id,
        recommendation_id=recommendation_id,
        owner=body.owner,
        due_at=body.due_at,
        title=body.title,
    )
    return {"task_id": task["id"], "message": "The proposal was added to the checklist."}
