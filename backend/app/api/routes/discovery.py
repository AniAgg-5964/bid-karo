from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_company, get_current_user, get_discovery_service
from app.models.dashboard import MessageResponse
from app.models.discovery import (
    DiscoveredTender,
    DiscoveryRunListResponse,
    DiscoveryRunRequest,
    DiscoveryRunResponse,
    DiscoveryStatusResponse,
    DiscoveryTenderListResponse,
    SaveTenderRequest,
)
from app.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/status", response_model=DiscoveryStatusResponse)
def discovery_status(
    company: dict = Depends(get_current_company),
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveryStatusResponse:
    return service.status()


@router.post("/run", response_model=DiscoveryRunResponse)
def run_discovery(
    payload: DiscoveryRunRequest | None = None,
    company: dict = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveryRunResponse:
    run, items, total, sources = service.run(company, user["id"], payload)
    return DiscoveryRunResponse(run=run, items=items, sources=sources, total=total)


@router.get("/tenders", response_model=DiscoveryTenderListResponse)
def list_discovered_tenders(
    min_score: float | None = Query(default=None, ge=0.0, le=1.0),
    status: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveryTenderListResponse:
    items, total = service.list_tenders(
        company["id"], min_score=min_score, statuses=status, limit=limit, offset=offset
    )
    return DiscoveryTenderListResponse(items=items, total=total)


@router.get("/sources", response_model=DiscoveryTenderListResponse)
def list_discovery_sources(
    limit: int = Query(default=8, ge=1, le=20),
    company: dict = Depends(get_current_company),
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveryTenderListResponse:
    items = service.list_sources(company["id"], limit=limit)
    return DiscoveryTenderListResponse(items=items, total=len(items))


@router.get("/tenders/{tender_id}", response_model=DiscoveredTender)
def get_discovered_tender(
    tender_id: str,
    company: dict = Depends(get_current_company),
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveredTender:
    return DiscoveredTender.model_validate(service.get_tender(tender_id, company["id"]))


@router.post("/tenders/{tender_id}/save", response_model=MessageResponse)
def save_discovered_tender(
    tender_id: str,
    payload: SaveTenderRequest | None = None,
    company: dict = Depends(get_current_company),
    user: dict = Depends(get_current_user),
    service: DiscoveryService = Depends(get_discovery_service),
) -> MessageResponse:
    status = (payload or SaveTenderRequest()).status
    tender = service.save_tender(tender_id, company["id"], user["id"], status)
    return MessageResponse(message=f"Tender saved to your workspace (id: {tender['id']}).")


@router.post("/tenders/{tender_id}/dismiss", response_model=DiscoveredTender)
def dismiss_discovered_tender(
    tender_id: str,
    company: dict = Depends(get_current_company),
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveredTender:
    document = service.set_status(tender_id, company["id"], "dismissed")
    return DiscoveredTender.model_validate(document)


@router.get("/runs", response_model=DiscoveryRunListResponse)
def list_discovery_runs(
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveryRunListResponse:
    items, total = service.list_runs(company["id"], limit=limit, offset=offset)
    return DiscoveryRunListResponse(items=items, total=total)
