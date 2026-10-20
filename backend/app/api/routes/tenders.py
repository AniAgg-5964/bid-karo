from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company
from app.models.dashboard import TenderDetail, TenderListResponse
from app.repositories.tender_documents import TenderDocumentRepository
from app.repositories.tenders import TenderRepository
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.get("", response_model=TenderListResponse)
def list_tenders(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> TenderListResponse:
    items, total = TenderRepository(db).list_for_company(company["id"], limit=limit, offset=offset)
    service = DashboardService(db)
    return TenderListResponse(
        items=[service.to_tender_card(item) for item in items], total=total
    )


@router.get("/{tender_id}", response_model=TenderDetail)
def get_tender(
    tender_id: str,
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> TenderDetail:
    tender = TenderRepository(db).find_for_company(tender_id, company["id"])
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found.")
    tender["document_count"] = TenderDocumentRepository(db).count_for_tender(
        company["id"], tender_id
    )
    return TenderDetail.model_validate(tender)
