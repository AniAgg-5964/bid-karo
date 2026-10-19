"""Thin, explicit client for the TinyFish Search and Fetch APIs.

Contract verified against the TinyFish SDK (``@tiny-fish/sdk``):

* Search: ``GET  {base}/v1/search`` with ``X-API-Key`` and query parameters.
* Fetch:  ``POST {base}/v1/fetch``  with ``X-API-Key`` and a JSON body.

Only reads are performed. Nothing here writes to the web.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings, get_settings

DEFAULT_BASE_URL = "https://agent.tinyfish.ai"
MAX_FETCH_URLS = 10


class TinyFishError(RuntimeError):
    """Any failure talking to TinyFish (network, auth, or API error)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TinyFishNotConfigured(TinyFishError):
    """Raised when no API key is configured, so discovery cannot run."""


@dataclass(slots=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    site_name: str
    position: int = 0
    published_date: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SearchHit":
        return cls(
            title=(payload.get("title") or "").strip(),
            url=(payload.get("url") or "").strip(),
            snippet=(payload.get("snippet") or "").strip(),
            site_name=(payload.get("site_name") or "").strip(),
            position=int(payload.get("position") or 0),
            published_date=(payload.get("date") or None) or None,
        )


@dataclass(slots=True)
class FetchedPage:
    url: str
    final_url: str | None
    title: str | None
    description: str | None
    text: str
    language: str | None = None
    published_date: str | None = None


@dataclass(slots=True)
class FetchBatch:
    pages: list[FetchedPage] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)


class TinyFishClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout_seconds: int = 120,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = http_client

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "TinyFishClient":
        current = settings or get_settings()
        return cls(
            current.tinyfish_api_key,
            base_url=current.tinyfish_base_url or DEFAULT_BASE_URL,
            timeout_seconds=current.tinyfish_agent_timeout_seconds,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if not self.configured:
            raise TinyFishNotConfigured(
                "TinyFish is not configured. Set TINYFISH_API_KEY to enable discovery."
            )
        url = f"{self.base_url}{path}"
        try:
            if self._client is not None:
                response = self._client.request(method, url, headers=self._headers(), **kwargs)
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.request(method, url, headers=self._headers(), **kwargs)
        except httpx.HTTPError as exc:  # network, DNS, timeout
            raise TinyFishError(f"TinyFish request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text[:300]
            raise TinyFishError(
                f"TinyFish returned HTTP {response.status_code}: {detail}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise TinyFishError("TinyFish returned a non-JSON response.") from exc

    def search(
        self,
        query: str,
        *,
        purpose: str | None = None,
        location: str | None = None,
        language: str | None = None,
        page: int | None = None,
    ) -> list[SearchHit]:
        params: dict[str, Any] = {"query": query}
        if purpose:
            params["purpose"] = purpose
        if location:
            params["location"] = location
        if language:
            params["language"] = language
        if page is not None:
            params["page"] = page

        payload = self._request("GET", "/v1/search", params=params)
        results = payload.get("results") or []
        return [SearchHit.from_payload(item) for item in results if item.get("url")]

    def fetch(
        self,
        urls: list[str],
        *,
        purpose: str | None = None,
        output_format: str = "markdown",
        timeout: float | None = None,
    ) -> FetchBatch:
        if not urls:
            return FetchBatch()
        if len(urls) > MAX_FETCH_URLS:
            raise TinyFishError(f"TinyFish fetch accepts at most {MAX_FETCH_URLS} URLs per call.")

        body: dict[str, Any] = {"urls": urls, "format": output_format}
        if purpose:
            body["purpose"] = purpose

        kwargs: dict[str, Any] = {"json": body}
        if timeout is not None:
            kwargs["timeout"] = timeout

        payload = self._request("POST", "/v1/fetch", **kwargs)
        batch = FetchBatch()
        for item in payload.get("results") or []:
            text = item.get("text")
            if not isinstance(text, str):
                text = ""
            batch.pages.append(
                FetchedPage(
                    url=item.get("url") or "",
                    final_url=item.get("final_url"),
                    title=item.get("title"),
                    description=item.get("description"),
                    text=text,
                    language=item.get("language"),
                    published_date=item.get("published_date"),
                )
            )
        for item in payload.get("errors") or []:
            if item.get("url"):
                batch.errors[item["url"]] = str(item.get("error") or "fetch_failed")
        return batch
