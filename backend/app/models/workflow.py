from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChecklistTaskOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    tender_id: str | None = None
    requirement_id: str | None = None
    title: str
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
    summary: str
    review_status: str = "pending"
    detected_at: datetime


class ChangeListResponse(BaseModel):
    items: list[ChangeOut]
    total: int
