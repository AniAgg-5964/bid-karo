from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company, get_current_user
from app.models.dashboard import DashboardSummary
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> DashboardSummary:
    return DashboardService(db).summary(user=user, company=company)
