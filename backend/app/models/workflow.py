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
    category: str | None = None
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
