from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BusinessType = Literal["proprietorship", "partnership", "llp", "private_limited", "public_limited", "other"]


class CompanyPreferences(BaseModel):
    sectors: list[str] = Field(default_factory=list, max_length=50)
    regions: list[str] = Field(default_factory=list, max_length=50)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    min_value: float | None = Field(default=None, ge=0)
    max_value: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_value_range(self) -> "CompanyPreferences":
        if self.min_value is not None and self.max_value is not None and self.max_value < self.min_value:
            raise ValueError("Maximum contract value cannot be below the minimum.")
        return self


class CompanyBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=250)
    business_type: BusinessType | None = None
    description: str | None = Field(default=None, max_length=2000)
    products_services: list[str] = Field(default_factory=list, max_length=100)
    sectors: list[str] = Field(default_factory=list, max_length=50)
    regions: list[str] = Field(default_factory=list, max_length=50)
    certifications: list[str] = Field(default_factory=list, max_length=100)
    annual_turnover: float | None = Field(default=None, ge=0)
    turnover_currency: str = Field(default="INR", min_length=3, max_length=3)
    employee_count: int | None = Field(default=None, ge=0)
    established_year: int | None = Field(default=None, ge=1900, le=2100)
    preferences: CompanyPreferences = Field(default_factory=CompanyPreferences)
    reminder_email_enabled: bool = False
    reminder_lead_days: list[int] = Field(default_factory=lambda: [7, 3, 1], max_length=5)

    @field_validator("reminder_lead_days")
    @classmethod
    def normalize_reminder_lead_days(cls, value: list[int]) -> list[int]:
        days = sorted({int(day) for day in value if 1 <= int(day) <= 90}, reverse=True)
        return days or [7, 3, 1]


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    legal_name: str | None = Field(default=None, max_length=250)
    business_type: BusinessType | None = None
    description: str | None = Field(default=None, max_length=2000)
    products_services: list[str] | None = Field(default=None, max_length=100)
    sectors: list[str] | None = Field(default=None, max_length=50)
    regions: list[str] | None = Field(default=None, max_length=50)
    certifications: list[str] | None = Field(default=None, max_length=100)
    annual_turnover: float | None = Field(default=None, ge=0)
    turnover_currency: str | None = Field(default=None, min_length=3, max_length=3)
    employee_count: int | None = Field(default=None, ge=0)
    established_year: int | None = Field(default=None, ge=1900, le=2100)
    preferences: CompanyPreferences | None = None
    reminder_email_enabled: bool | None = None
    reminder_lead_days: list[int] | None = Field(default=None, max_length=5)
    onboarding_completed: bool | None = None

    @field_validator("reminder_lead_days")
    @classmethod
    def normalize_reminder_lead_days(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        days = sorted({int(day) for day in value if 1 <= int(day) <= 90}, reverse=True)
        return days or [7, 3, 1]

    @field_validator("turnover_currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class CompanyOut(CompanyBase):
    model_config = ConfigDict(extra="ignore")

    id: str
    onboarding_completed: bool = False
    profile_completeness: int = 0
    created_at: datetime
    updated_at: datetime


def calculate_profile_completeness(company: dict) -> int:
    """Deterministic completeness score across the fields needed for assessment."""
    checks = [
        bool(company.get("name")),
        bool(company.get("legal_name")),
        bool(company.get("business_type")),
        bool(company.get("description")),
        bool(company.get("products_services")),
        bool(company.get("sectors")),
        bool(company.get("regions")),
        company.get("annual_turnover") is not None,
        company.get("employee_count") is not None,
        bool(company.get("certifications")),
        bool(company.get("preferences", {}).get("sectors")),
        bool(company.get("preferences", {}).get("regions")),
    ]
    return round((sum(1 for check in checks if check) / len(checks)) * 100)
