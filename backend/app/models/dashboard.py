from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DashboardMetrics(BaseModel):
    active_bids: int = 0
    open_tasks: int = 0
    upcoming_deadlines: int = 0
    evidence_documents: int = 0
    pending_changes: int = 0
    pending_reminders: int = 0


class PriorityAction(BaseModel):
    key: str
    title: str
    description: str
    href: str
    tone: Literal["info", "warning", "danger", "success"] = "info"


class ActivityItem(BaseModel):
    id: str
    action: str
    entity_type: str
    summary: str
    created_at: datetime


class TenderCard(BaseModel):
    id: str
    title: str
    authority: str | None = None
    reference_number: str | None = None
    deadline: datetime | None = None
    status: str = "saved"
    source_url: str | None = None
    created_at: datetime


class DeadlineItem(BaseModel):
    id: str
    title: str
    due_at: datetime
    status: str
    href: str


class DashboardSummary(BaseModel):
    company_name: str
    user_name: str
    profile_completeness: int
    onboarding_completed: bool
    metrics: DashboardMetrics
    priority_actions: list[PriorityAction]
    recent_tenders: list[TenderCard]
    recent_activity: list[ActivityItem]
    upcoming_deadlines: list[DeadlineItem]


class InboxItem(BaseModel):
    id: str
    kind: Literal[
        "eligibility",
        "evidence",
        "change",
        "deadline",
        "reminder",
        "source",
    ]
    title: str
    description: str
    href: str
    severity: Literal["info", "warning", "danger", "success"] = "info"
    due_at: datetime | None = None
    tender_id: str | None = None
    tender_title: str | None = None
    action_label: str


class InboxResponse(BaseModel):
    items: list[InboxItem]
    total: int
    truncated: bool = False


class MessageResponse(BaseModel):
    message: str


class TenderDetail(TenderCard):
    model_config = ConfigDict(extra="allow")

    company_id: str
    description: str | None = None
    source_retrieved_at: datetime | None = None
    document_count: int = 0


class TenderListResponse(BaseModel):
    items: list[TenderCard]
    total: int
