"""What the agents propose, and what the gate decided about it.

These records hold a *proposal* and the gate's verdict on it. They never hold
a fact on their own: a recommendation is only useful next to the clause it
rests on, and a legal source is only useful next to the page it was read from.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RecommendationKind = Literal[
    "document_to_prepare",
    "clarification_to_raise",
    "red_flag",
    "format_requirement",
    "timeline_note",
    "verification",
]
GroundingStatus = Literal["grounded", "verified", "unverified", "needs_review", "rejected"]
TaskStatus = Literal["missing", "incomplete", "needs_verification", "in_progress", "complete", "not_applicable"]


class RecommendationOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    tender_id: str
    document_id: str | None = None
    kind: RecommendationKind
    title: str
    claim: str
    action: str | None = None
    acceptance_criteria: str | None = None
    suggested_owner: str | None = None
    suggested_due_at: datetime | None = None
    requirement_refs: list[str] = Field(default_factory=list)
    grounded_requirements: list[str] = Field(default_factory=list)
    dropped_claims: list[str] = Field(default_factory=list)
    grounding_status: GroundingStatus = "unverified"
    grounding_note: str | None = None
    # The task this proposal would create, for a human to confirm.
    proposed_task: dict | None = None
    model: str | None = None
    prompt_version: str | None = None
    created_at: datetime
    updated_at: datetime


class RecommendationListResponse(BaseModel):
    items: list[RecommendationOut]
    total: int


class LegalSourceOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    tender_id: str
    requirement_id: str | None = None
    topic: str
    question: str
    quote: str
    source_url: str
    source_title: str | None = None
    source_class: str = "central_official"
    section: str | None = None
    retrieved_at: datetime
    applies_to_us: str | None = None
    must_hold: list[str] = Field(default_factory=list)
    gap: str | None = None
    next_action: str | None = None
    grounding_status: GroundingStatus = "verified"
    grounding_note: str | None = None
    disclaimer: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    created_at: datetime
    updated_at: datetime


class LegalSourceListResponse(BaseModel):
    items: list[LegalSourceOut]
    total: int
    disclaimer: str


class ApplyRecommendationRequest(BaseModel):
    """Turn a proposal into a real checklist task."""

    owner: str | None = None
    due_at: datetime | None = None
    title: str | None = None
