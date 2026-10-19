from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company
from app.models.workflow import ChangeListResponse, ChangeOut, ChecklistTaskListResponse, ChecklistTaskOut
from app.repositories.tenders import ChangeRepository, ChecklistRepository

router = APIRouter(tags=["workflow"])


@router.get("/checklist", response_model=ChecklistTaskListResponse)
def list_checklist_tasks(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ChecklistTaskListResponse:
    items, total = ChecklistRepository(db).list_for_company(
        company["id"], limit=limit, offset=offset
    )
    return ChecklistTaskListResponse(
        items=[ChecklistTaskOut.model_validate(item) for item in items], total=total
    )


@router.get("/changes", response_model=ChangeListResponse)
def list_changes(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ChangeListResponse:
    items, total = ChangeRepository(db).list_for_company(
        company["id"], limit=limit, offset=offset
    )
    return ChangeListResponse(
        items=[ChangeOut.model_validate(item) for item in items], total=total
    )
