from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentKind = Literal["main", "corrigendum", "boq", "form", "other"]
DocumentSource = Literal["uploaded", "downloaded"]
DocumentStatus = Literal["extracted", "no_text_layer", "failed"]
OcrStatus = Literal["disabled", "not_needed", "applied", "partial", "failed", "unavailable"]
TextSource = Literal["text_layer", "ocr", "empty"]

RequirementCategory = Literal[
    "eligibility",
    "technical",
    "financial",
    "compliance",
    "submission",
    "performance",
    "other",
]
RequirementVerification = Literal["verified", "unverified", "needs_review", "rejected"]
MandatoryFlag = Literal["yes", "no", "unknown"]

CATEGORIES: tuple[str, ...] = (
    "eligibility",
    "technical",
    "financial",
    "compliance",
    "submission",
    "performance",
    "other",
)


class TenderDocumentOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    tender_id: str
    kind: DocumentKind
    title: str
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    source: DocumentSource
    source_url: str | None = None
    retrieved_at: datetime
    status: DocumentStatus
    page_count: int = 0
    text_page_count: int = 0
    ocr_page_count: int = 0
    ocr_status: OcrStatus = "disabled"
    truncated: bool = False
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class TenderDocumentListResponse(BaseModel):
    items: list[TenderDocumentOut]
    total: int


class TenderPageOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page_index: int
    printed_label: str
    char_count: int
    has_text: bool
    text_source: TextSource = "text_layer"


class TenderPageText(TenderPageOut):
    text: str


class TenderPageListResponse(BaseModel):
    document_id: str
    page_count: int
    text_page_count: int
    items: list[TenderPageOut]


class RequirementOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    tender_id: str
    document_id: str
    category: RequirementCategory
    title: str
    obligation: str
    excerpt: str
    page_index: int
    printed_page: str | None = None
    text_source: TextSource = "text_layer"
    clause_reference: str | None = None
    form_reference: str | None = None
    mandatory: MandatoryFlag
    deadline_text: str | None = None
    consequence_text: str | None = None
    verification_status: RequirementVerification
    verification_notes: str | None = None
    evidence_status: Literal["none", "suggested", "confirmed", "contradicted", "rejected"] = "none"
    evidence_document_id: str | None = None
    evidence_document_title: str | None = None
    document_title: str | None = None
    document_retrieved_at: datetime | None = None
    source_url: str | None = None
    origin: Literal["ai", "manual"] = "ai"
    model: str | None = None
    prompt_version: str | None = None
    created_at: datetime
    updated_at: datetime


class RequirementListResponse(BaseModel):
    items: list[RequirementOut]
    total: int


class RequirementSummary(BaseModel):
    total: int = 0
    verified: int = 0
    unverified: int = 0
    needs_review: int = 0
    documents: int = 0


class RequirementReview(BaseModel):
    verification_status: Literal["verified", "needs_review", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class RequirementExtractionRequest(BaseModel):
    replace: bool = False


class RequirementExtractionResponse(BaseModel):
    document_id: str
    status: Literal["completed", "partial", "not_configured", "no_text"]
    chunks: int = 0
    skipped_chunks: int = 0
    created: int = 0
    duplicates: int = 0
    invalid: int = 0
    verified: int = 0
    unverified: int = 0
    needs_review: int = 0
    failed_chunks: int = 0
    model: str | None = None
    message: str


class DownloadRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    kind: DocumentKind = "main"
    title: str | None = Field(default=None, max_length=200)
