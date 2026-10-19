from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["official", "aggregator", "unknown"]
FetchStatus = Literal["not_fetched", "fetched", "blocked", "error"]
TenderStatus = Literal["new", "saved", "dismissed"]

# Fields we attempt to extract deterministically from source text. Anything not
# found stays null and is reported as unknown; we never guess a value.
EXTRACTED_FIELDS = (
    "authority",
    "reference_number",
    "deadline",
    "value",
    "location",
)


class ExtractedTender(BaseModel):
    """Deterministic extraction result, with the verbatim excerpt for each field."""

    authority: str | None = None
    reference_number: str | None = None
    deadline: str | None = None  # ISO date (YYYY-MM-DD) when it could be parsed
    deadline_raw: str | None = None  # exact text the deadline was parsed from
    value_amount: float | None = None
    value_currency: str | None = None
    value_raw: str | None = None
    location: str | None = None
    evidence: dict[str, str] = Field(default_factory=dict)  # field -> excerpt


class Relevance(BaseModel):
    """Deterministic profile-fit signal. Separate from eligibility and suitability."""

    score: float = 0.0
    matched_terms: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    threshold: float = 0.0


class DiscoveredTender(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    source: str = "tinyfish"
    source_type: SourceType = "unknown"
    source_url: str
    site_name: str = ""
    title: str
    snippet: str = ""
    query: str = ""
    retrieved_at: datetime
    published_hint: str | None = None
    extracted: ExtractedTender = Field(default_factory=ExtractedTender)
    relevance: Relevance = Field(default_factory=Relevance)
    fetch_status: FetchStatus = "not_fetched"
    fetch_error: str | None = None
    is_listing_page: bool = False
    is_award_notice: bool = False
    extracted_from: str | None = None
    parent_url: str | None = None
    content_excerpt: str | None = None
    content_hash: str | None = None
    status: TenderStatus = "new"
    first_seen_at: datetime
    last_seen_at: datetime


class DiscoveryStats(BaseModel):
    queries: int = 0
    search_hits: int = 0
    unique_candidates: int = 0
    prequalified: int = 0
    fetched: int = 0
    fetch_failed: int = 0
    matched: int = 0
    listed: int = 0
    skipped_low_relevance: int = 0
    skipped_listing: int = 0
    skipped_non_tender: int = 0
    skipped_closed: int = 0
    skipped_unverified: int = 0
    tenders_from_listings: int = 0


class DiscoveryRun(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    company_id: str
    status: str
    queries: list[str] = Field(default_factory=list)
    stats: DiscoveryStats = Field(default_factory=DiscoveryStats)
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class DiscoveryTenderListResponse(BaseModel):
    items: list[DiscoveredTender]
    total: int


class DiscoveryRunListResponse(BaseModel):
    items: list[DiscoveryRun]
    total: int


class DiscoveryRunRequest(BaseModel):
    keywords: str | None = Field(default=None, max_length=200)
    max_candidates: int | None = Field(default=None, ge=1, le=50)
    fetch_limit: int | None = Field(default=None, ge=0, le=10)
    min_score: float | None = Field(default=None, ge=0.0, le=1.0)


class DiscoveryRunResponse(BaseModel):
    run: DiscoveryRun
    items: list[DiscoveredTender]
    sources: list[DiscoveredTender] = Field(default_factory=list)
    total: int


class DiscoveryStatusResponse(BaseModel):
    configured: bool
    provider: str = "tinyfish"
    base_url: str
    min_score: float
    max_candidates: int
    fetch_limit: int
    official_only: bool = False


class SaveTenderRequest(BaseModel):
    status: Literal["saved", "preparing", "submitted"] = "saved"
