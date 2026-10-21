"""Starting and watching the tender analysis job."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company, get_current_user
from app.models.jobs import JobOut
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
