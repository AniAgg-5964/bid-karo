"""Configurable AI provider used for structured requirement extraction.

Only JSON responses are requested, and callers must treat the result as
untrusted input: validate it with Pydantic and verify every citation against
the source page before storing it.
"""

from __future__ import annotations

import json
import time
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3


class AIError(RuntimeError):
    """Any failure talking to the configured AI provider."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AINotConfigured(AIError):
    """Raised when the selected provider has no API key or model."""


class AIProvider(Protocol):
    model: str

    @property
    def configured(self) -> bool: ...

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]: ...


class GroqProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://api.groq.com/openai/v1",
        timeout_seconds: int = 60,
        max_output_tokens: int = 4000,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model and self.base_url)

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        if not self.configured:
            raise AINotConfigured("GROQ_API_KEY and GROQ_MODEL must be configured.")

        response = None
        for attempt in range(MAX_ATTEMPTS):
            body: dict[str, Any] = {
                "model": self.model,
                "temperature": 0,
                "max_tokens": self.max_output_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            if "gpt-oss" in self.model.lower():
                body["reasoning_effort"] = "low"
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                    timeout=self.timeout_seconds,
                )
            except httpx.HTTPError as exc:
                raise AIError(f"AI request failed ({type(exc).__name__}).") from exc

            if response.status_code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS - 1:
                break
            time.sleep(3 * (attempt + 1))

        if response is None:
            raise AIError("AI request failed before a response was received.")
        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json()
                detail = str((payload.get("error") or {}).get("message") or "")[:300]
            except (ValueError, AttributeError):
                detail = ""
            raise AIError(
                f"AI provider returned HTTP {response.status_code}."
                + (f" {detail}" if detail else ""),
                status_code=response.status_code,
            )
        try:
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AIError("AI provider returned an invalid JSON payload.") from exc


class GeminiProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: int = 60,
        max_output_tokens: int = 4000,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model and self.base_url)

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        if not self.configured:
            raise AINotConfigured("GEMINI_API_KEY and GEMINI_MODEL must be configured.")

        response = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = httpx.post(
                    f"{self.base_url}/models/{self.model}:generateContent",
                    params={"key": self.api_key},
                    json={
                        "systemInstruction": {"parts": [{"text": system}]},
                        "contents": [{"role": "user", "parts": [{"text": user}]}],
                        "generationConfig": {
                            "temperature": 0,
                            "maxOutputTokens": self.max_output_tokens,
                            "responseMimeType": "application/json",
                        },
                    },
                    timeout=self.timeout_seconds,
                )
            except httpx.HTTPError as exc:
                raise AIError(f"AI request failed ({type(exc).__name__}).") from exc

            if response.status_code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS - 1:
                break
            time.sleep(3 * (attempt + 1))

        if response is None:
            raise AIError("AI request failed before a response was received.")
        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json()
                detail = str((payload.get("error") or {}).get("message") or "")[:300]
            except (ValueError, AttributeError):
                detail = ""
            raise AIError(
                f"AI provider returned HTTP {response.status_code}."
                + (f" {detail}" if detail else ""),
                status_code=response.status_code,
            )
        try:
            content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AIError("AI provider returned an invalid JSON payload.") from exc


def build_ai_provider(settings: Settings | None = None) -> AIProvider:
    current = settings or get_settings()
    provider = (current.ai_provider or "").strip().lower()
    if provider == "gemini":
        return GeminiProvider(
            current.gemini_api_key,
            current.gemini_model,
            base_url=current.gemini_base_url,
            timeout_seconds=current.ai_request_timeout_seconds,
            max_output_tokens=current.ai_max_output_tokens,
        )
    if provider == "groq":
        return GroqProvider(
            current.groq_api_key,
            current.groq_model,
            base_url=current.groq_base_url,
            timeout_seconds=current.ai_request_timeout_seconds,
            max_output_tokens=current.ai_max_output_tokens,
        )
    return UnconfiguredProvider(
        f"Unsupported AI_PROVIDER '{current.ai_provider}'. Use 'groq' or 'gemini'."
    )


class UnconfiguredProvider:
    def __init__(self, reason: str) -> None:
        self.reason = reason
        self.model = ""

    @property
    def configured(self) -> bool:
        return False

    def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        raise AINotConfigured(self.reason)
