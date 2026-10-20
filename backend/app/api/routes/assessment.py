from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company, get_current_user
from app.models.assessment import (
    AssessmentOut,
    ChecklistGenerateResponse,
    ChecklistTaskUpdate,
    EvidenceDecision,
    RequirementEvidenceOut,
)
from app.models.workflow import (
    ChecklistTaskListResponse,
    ChecklistTaskOut,
    LegalObligationListResponse,
)
from app.services.assessment import AssessmentService

router = APIRouter(tags=["assessment"])

LEGAL_DISCLAIMER = (
    "Extracted obligations with source citations only. This is not legal advice and "
    "does not replace review by a qualified professional."
)


@router.get("/tenders/{tender_id}/assessment", response_model=AssessmentOut)
def get_assessment(
    tender_id: str,
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> AssessmentOut:
    return AssessmentService(db).assess(tender_id=tender_id, company=company)


@router.get(
    "/tenders/{tender_id}/requirements/{requirement_id}/evidence",
    response_model=RequirementEvidenceOut,
)
def get_requirement_evidence(
    tender_id: str,
    requirement_id: str,
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> RequirementEvidenceOut:
    return AssessmentService(db).evidence_for_requirement(
        tender_id=tender_id, requirement_id=requirement_id, company=company
    )


@router.post(
    "/tenders/{tender_id}/requirements/{requirement_id}/evidence",
    response_model=RequirementEvidenceOut,
)
def decide_requirement_evidence(
    tender_id: str,
    requirement_id: str,
    payload: EvidenceDecision,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> RequirementEvidenceOut:
    return AssessmentService(db).decide_evidence(
        tender_id=tender_id,
        requirement_id=requirement_id,
        company=company,
        user_id=user["id"],
        payload=payload,
    )


@router.get("/tenders/{tender_id}/legal", response_model=LegalObligationListResponse)
def list_legal_obligations(
    tender_id: str,
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> LegalObligationListResponse:
    items = AssessmentService(db).list_legal_obligations(
        tender_id=tender_id, company_id=company["id"]
    )
    return LegalObligationListResponse(
        items=items, total=len(items), disclaimer=LEGAL_DISCLAIMER
    )


@router.get("/tenders/{tender_id}/checklist", response_model=ChecklistTaskListResponse)
def list_tender_checklist(
    tender_id: str,
    phase: str | None = Query(default=None, pattern="^(pre_award|post_award)$"),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ChecklistTaskListResponse:
    items, total = AssessmentService(db).list_tasks(
        tender_id=tender_id, company_id=company["id"], phase=phase
    )
    return ChecklistTaskListResponse(
        items=[ChecklistTaskOut.model_validate(item) for item in items], total=total
    )


@router.post(
    "/tenders/{tender_id}/checklist/generate",
    response_model=ChecklistGenerateResponse,
)
def generate_tender_checklist(
    tender_id: str,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ChecklistGenerateResponse:
    created, skipped, total = AssessmentService(db).generate_checklist(
        tender_id=tender_id, company=company, user_id=user["id"]
    )
    return ChecklistGenerateResponse(
        created=len(created),
        skipped=skipped,
        total=total,
        items=[ChecklistTaskOut.model_validate(item) for item in created],
        message=(
            f"Created {len(created)} tender-specific checklist tasks"
            + (f"; {skipped} already existed." if skipped else ".")
        ),
    )


@router.get(
    "/tenders/{tender_id}/obligations", response_model=ChecklistTaskListResponse
)
def list_post_award_obligations(
    tender_id: str,
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ChecklistTaskListResponse:
    items, total = AssessmentService(db).list_tasks(
        tender_id=tender_id, company_id=company["id"], phase="post_award"
    )
    return ChecklistTaskListResponse(
        items=[ChecklistTaskOut.model_validate(item) for item in items], total=total
    )


@router.post(
    "/tenders/{tender_id}/obligations/generate",
    response_model=ChecklistGenerateResponse,
)
def generate_post_award_obligations(
    tender_id: str,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ChecklistGenerateResponse:
    created, skipped, total = AssessmentService(db).generate_obligations(
        tender_id=tender_id, company=company, user_id=user["id"]
    )
    return ChecklistGenerateResponse(
        created=len(created),
        skipped=skipped,
        total=total,
        items=[ChecklistTaskOut.model_validate(item) for item in created],
        message=(
            f"Created {len(created)} cited post-award obligations"
            + (f"; {skipped} already existed." if skipped else ".")
        ),
    )


@router.patch("/checklist/{task_id}", response_model=ChecklistTaskOut)
def update_checklist_task(
    task_id: str,
    payload: ChecklistTaskUpdate,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> ChecklistTaskOut:
    changes = payload.model_dump(exclude_unset=True)
    updated = AssessmentService(db).update_task(
        task_id=task_id,
        company_id=company["id"],
        user_id=user["id"],
        changes=changes,
    )
    return ChecklistTaskOut.model_validate(updated)
