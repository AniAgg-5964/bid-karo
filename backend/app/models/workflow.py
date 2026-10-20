from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

ChangeReviewStatus = Literal["pending", "acknowledged", "dismissed"]
ReminderStatus = Literal["pending", "acknowledged", "dismissed", "sent", "cancelled"]
TaskPhase = Literal["pre_award", "post_award"]


class ChecklistTaskOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    tender_id: str | None = None
    requirement_id: str | None = None
    title: str
    category: str | None = None
    phase: TaskPhase = "pre_award"
    trigger_type: str | None = None
    action: str | None = None
    acceptance_criteria: str | None = None
    evidence_check: str | None = None
    issuer: str | None = None
    signatory: str | None = None
    deadline_text: str | None = None
    trigger: str | None = None
    consequence: str | None = None
    source_document_title: str | None = None
    page_index: int | None = None
    printed_page: str | None = None
    clause_reference: str | None = None
    excerpt: str | None = None
    source_url: str | None = None
    source_retrieved_at: datetime | None = None
    status: str
    owner: str | None = None
    due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ChecklistTaskListResponse(BaseModel):
    items: list[ChecklistTaskOut]
    total: int


class ChangeOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    tender_id: str | None = None
    tender_title: str | None = None
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    summary: str
    severity: str = "info"
    review_status: ChangeReviewStatus = "pending"
    from_snapshot_id: str | None = None
    to_snapshot_id: str | None = None
    source_url: str | None = None
    detected_at: datetime
    reviewed_at: datetime | None = None


class ChangeListResponse(BaseModel):
    items: list[ChangeOut]
    total: int


class ChangeReviewRequest(BaseModel):
    review_status: ChangeReviewStatus


class TenderSnapshotOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    tender_id: str
    source_url: str | None = None
    content_hash: str
    captured_at: datetime
    source_retrieved_at: datetime | None = None
    fields: dict[str, Any]
    requirement_count: int = 0


class TenderSnapshotListResponse(BaseModel):
    items: list[TenderSnapshotOut]
    total: int


class SnapshotCaptureResponse(BaseModel):
    snapshot: TenderSnapshotOut
    created: bool
    changes: list[ChangeOut]


class ReminderOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    type: str
    title: str
    body: str
    due_at: datetime
    href: str
    tender_id: str | None = None
    task_id: str | None = None
    document_id: str | None = None
    lead_days: int | None = None
    status: ReminderStatus = "pending"
    sent_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime


class ReminderListResponse(BaseModel):
    items: list[ReminderOut]
    total: int
    email_enabled: bool = False
    email_configured: bool = False


class ReminderUpdate(BaseModel):
    status: Literal["pending", "acknowledged", "dismissed"]


class LegalObligationOut(BaseModel):
    requirement_id: str
    title: str
    category: str
    obligation: str
    excerpt: str
    page_index: int
    printed_page: str | None = None
    clause_reference: str | None = None
    document_title: str | None = None
    deadline_text: str | None = None
    consequence_text: str | None = None
    verification_status: str
    source_url: str | None = None


class LegalObligationListResponse(BaseModel):
    items: list[LegalObligationOut]
    total: int
    disclaimer: str
