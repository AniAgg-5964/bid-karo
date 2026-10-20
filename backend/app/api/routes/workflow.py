from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company, get_current_user
from app.models.workflow import (
    ChangeListResponse,
    ChangeOut,
    ChangeReviewRequest,
    ChecklistTaskListResponse,
    ChecklistTaskOut,
    ReminderListResponse,
    ReminderOut,
    ReminderUpdate,
    SnapshotCaptureResponse,
    TenderSnapshotListResponse,
)
from app.repositories.tenders import ChecklistRepository
from app.services.calendar import CalendarService
from app.services.reminders import ReminderService
from app.services.workflow import WorkflowService

router = APIRouter(tags=["workflow"])


@router.get("/checklist", response_model=ChecklistTaskListResponse)
def list_checklist_tasks(
    phase: str | None = Query(default=None, pattern="^(pre_award|post_award)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ChecklistTaskListResponse:
    items, total = ChecklistRepository(db).list_for_company(
        company["id"], limit=limit, offset=offset, phase=phase
    )
    return ChecklistTaskListResponse(
        items=[ChecklistTaskOut.model_validate(item) for item in items], total=total
    )


@router.get("/changes", response_model=ChangeListResponse)
def list_changes(
    tender_id: str | None = Query(default=None),
    review_status: str | None = Query(default=None, pattern="^(pending|acknowledged|dismissed)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ChangeListResponse:
    items, total = WorkflowService(db).list_changes(
        company_id=company["id"],
        limit=limit,
        offset=offset,
        tender_id=tender_id,
        review_status=review_status,
    )
    return ChangeListResponse(items=items, total=total)


@router.patch("/changes/{change_id}/review", response_model=ChangeOut)
def review_change(
    change_id: str,
    payload: ChangeReviewRequest,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ChangeOut:
    return WorkflowService(db).review_change(
        change_id=change_id,
        company_id=company["id"],
        user_id=user["id"],
        review_status=payload.review_status,
    )


@router.get("/tenders/{tender_id}/changes", response_model=ChangeListResponse)
def list_tender_changes(
    tender_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ChangeListResponse:
    items, total = WorkflowService(db).list_changes(
        company_id=company["id"], limit=limit, offset=offset, tender_id=tender_id
    )
    return ChangeListResponse(items=items, total=total)


@router.get("/tenders/{tender_id}/snapshots", response_model=TenderSnapshotListResponse)
def list_snapshots(
    tender_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> TenderSnapshotListResponse:
    service = WorkflowService(db)
    items = service.list_snapshots(
        tender_id=tender_id, company_id=company["id"], limit=limit, offset=offset
    )
    _, total = service.snapshots.list_for_tender(
        company["id"], tender_id, limit=limit, offset=offset
    )
    return TenderSnapshotListResponse(items=items, total=total)


@router.post("/tenders/{tender_id}/snapshots", response_model=SnapshotCaptureResponse)
def capture_snapshot(
    tender_id: str,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> SnapshotCaptureResponse:
    return WorkflowService(db).capture_snapshot(
        tender_id=tender_id, company_id=company["id"], user_id=user["id"]
    )


@router.post("/tenders/{tender_id}/refresh", response_model=SnapshotCaptureResponse)
def refresh_tender(
    tender_id: str,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> SnapshotCaptureResponse:
    return WorkflowService(db).refresh_tender(
        tender_id=tender_id, company_id=company["id"], user_id=user["id"]
    )


@router.get("/reminders", response_model=ReminderListResponse)
def list_reminders(
    status: str | None = Query(default=None, pattern="^(pending|acknowledged|dismissed|sent|cancelled)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ReminderListResponse:
    return ReminderService(db).list(
        company, status=status, limit=limit, offset=offset
    )


@router.patch("/reminders/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    reminder_id: str,
    payload: ReminderUpdate,
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ReminderOut:
    return ReminderService(db).update(
        reminder_id=reminder_id, company_id=company["id"], status=payload.status
    )


@router.get("/tenders/{tender_id}/calendar.ics")
def tender_calendar(
    tender_id: str,
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> Response:
    content = CalendarService(db).tender_calendar(
        company_id=company["id"], tender_id=tender_id
    )
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="bidkaro-tender-{tender_id}.ics"'
        },
    )


@router.get("/calendar.ics")
def company_calendar(
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> Response:
    content = CalendarService(db).company_calendar(company_id=company["id"])
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="bidkaro-calendar.ics"'},
    )
