from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.workflow import ChecklistTaskOut

GateStatus = Literal["pass", "fail", "unknown"]
EvidenceStatus = Literal["none", "suggested", "confirmed", "contradicted", "rejected"]
FitBand = Literal["strong", "moderate", "weak", "insufficient"]
TaskStatus = Literal[
    "missing", "incomplete", "needs_verification", "in_progress", "complete", "not_applicable"
]


class EvidenceCandidate(BaseModel):
    document_id: str
    title: str
    document_type: str
    issuer: str | None = None
    expiry_date: date | None = None
    score: float
    matched_terms: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    valid: bool = True
    validity_note: str | None = None


class RequirementEvidenceOut(BaseModel):
    requirement_id: str
    status: EvidenceStatus = "none"
    document_id: str | None = None
    document_title: str | None = None
    note: str | None = None
    candidates: list[EvidenceCandidate] = Field(default_factory=list)


class EvidenceDecision(BaseModel):
    document_id: str
    status: Literal["confirmed", "contradicted", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class EligibilityItem(BaseModel):
    requirement_id: str
    title: str
    category: str
    mandatory: str
    excerpt: str
    page_index: int
    printed_page: str | None = None
    clause_reference: str | None = None
    document_id: str
    document_title: str | None = None
    gate: GateStatus = "unknown"
    evidence_status: EvidenceStatus = "none"
    evidence_document_id: str | None = None
    evidence_document_title: str | None = None
    profile_hints: list[str] = Field(default_factory=list)
    reason: str


class EligibilitySummary(BaseModel):
    status: GateStatus = "unknown"
    pass_count: int = 0
    fail_count: int = 0
    unknown_count: int = 0
    items: list[EligibilityItem] = Field(default_factory=list)
    message: str


class ScoreDimension(BaseModel):
    key: str
    label: str
    weight: int
    score: int
    contribution: float
    reason: str


class FitScore(BaseModel):
    value: int = 0
    band: FitBand = "insufficient"
    dimensions: list[ScoreDimension] = Field(default_factory=list)
    explanation: str
    gating_status: GateStatus = "unknown"
    generated_at: datetime


class AssessmentCounts(BaseModel):
    total: int = 0
    verified: int = 0
    mandatory_gating: int = 0
    checklist_total: int = 0
    checklist_open: int = 0


class AssessmentOut(BaseModel):
    tender_id: str
    score: FitScore
    eligibility: EligibilitySummary
    counts: AssessmentCounts
    generated_at: datetime


class ChecklistTaskUpdate(BaseModel):
    status: TaskStatus | None = None
    owner: str | None = Field(default=None, max_length=120)
    due_at: datetime | None = None


class ChecklistGenerateResponse(BaseModel):
    created: int = 0
    skipped: int = 0
    total: int = 0
    items: list[ChecklistTaskOut] = Field(default_factory=list)
    message: str
