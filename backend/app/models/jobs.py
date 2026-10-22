"""Jobs: long-running work with visible, honest state.

The agent pipeline is slow by nature: a model call, a page read, a citation
check. A job records that work so the user can see where it is, so a failure
says what failed, and so one step can be re-run without redoing the rest.

A job never pretends to have done something it did not do. A step that is not
implemented reports "not available yet" and the job continues; a step that
raised reports the error and the job fails.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JobKind = Literal[
    "package_ingest",
    "tender_analysis",
    "legal_research",
    "knowledge_index",
]
JobStatus = Literal["queued", "running", "done", "failed"]
StepStatus = Literal["pending", "running", "done", "failed", "skipped"]


class JobStep(BaseModel):
    """One step of a job."""

    key: str
    label: str
    status: StepStatus = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    summary: dict = Field(default_factory=dict)


class JobOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    kind: JobKind
    status: JobStatus
    tender_id: str | None = None
    document_id: str | None = None
    payload: dict = Field(default_factory=dict)
    steps: list[JobStep] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobListResponse(BaseModel):
    items: list[JobOut]
    total: int
