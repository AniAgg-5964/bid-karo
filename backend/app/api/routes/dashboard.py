from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company, get_current_user
from app.models.dashboard import DashboardSummary, InboxItem, InboxResponse
from app.services.dashboard_service import DashboardService
from app.services.inbox_service import InboxService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> DashboardSummary:
    return DashboardService(db).summary(user=user, company=company)


@router.get("/inbox", response_model=InboxResponse)
def dashboard_inbox(
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> InboxResponse:
    """The prioritised list of what needs a person, from the company's records."""
    result = InboxService(db).build(company["id"])
    return InboxResponse(
        items=[InboxItem.model_validate(item) for item in result["items"]],
        total=result["total"],
    )
