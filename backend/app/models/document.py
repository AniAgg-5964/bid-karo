from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DocumentVerificationStatus = Literal["self_declared", "verified", "rejected", "expired"]


class DocumentOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    original_filename: str
    stored_filename: str
    title: str
    document_type: str
    issuer: str | None = None
    signatory: str | None = None
    financial_year: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    project_value: float | None = None
    notes: str | None = None
    mime_type: str
    size_bytes: int
    sha256: str
    verification_status: DocumentVerificationStatus
    created_at: datetime
    updated_at: datetime

    @field_validator("issue_date", "expiry_date", mode="before")
    @classmethod
    def normalize_date(cls, value):
        if isinstance(value, datetime):
            return value.date()
        return value


class DocumentListResponse(BaseModel):
    items: list[DocumentOut]
    total: int


class DocumentMetadata(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    document_type: str = Field(min_length=1, max_length=80)
    issuer: str | None = Field(default=None, max_length=200)
    signatory: str | None = Field(default=None, max_length=200)
    financial_year: str | None = Field(default=None, max_length=20)
    issue_date: date | None = None
    expiry_date: date | None = None
    project_value: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=1000)


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    document_type: str | None = Field(default=None, min_length=1, max_length=80)
    issuer: str | None = Field(default=None, max_length=200)
    signatory: str | None = Field(default=None, max_length=200)
    financial_year: str | None = Field(default=None, max_length=20)
    issue_date: date | None = None
    expiry_date: date | None = None
    project_value: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=1000)
