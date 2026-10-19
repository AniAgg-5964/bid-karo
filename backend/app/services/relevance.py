"""Deterministic, explainable profile-fit scoring for discovered tenders.

This is a *discovery relevance* signal: how well a tender matches the company's
declared sectors, products, keywords and regions. It is intentionally separate
from mandatory eligibility and from the Bid Suitability Score (Phase 4), and it
never hides a failed requirement.
"""

from __future__ import annotations

import re

from app.models.discovery import Relevance

KEYWORD_WEIGHT = 0.4
CAPABILITY_WEIGHT = 0.35
REGION_WEIGHT = 0.25
MIN_TERM_LENGTH = 3


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def _dedupe_terms(terms: list[str] | None) -> list[str]:
    seen: dict[str, str] = {}
    for term in terms or []:
        cleaned = _normalize(term)
        if len(cleaned) >= MIN_TERM_LENGTH and cleaned not in seen:
            seen[cleaned] = cleaned
    return list(seen.values())


def company_terms(company: dict) -> dict[str, list[str]]:
    preferences = company.get("preferences") or {}
    keywords = _dedupe_terms(preferences.get("keywords"))
    capability = _dedupe_terms(
        list(company.get("products_services") or [])
        + list(company.get("sectors") or [])
        + list(preferences.get("sectors") or [])
    )
    regions = _dedupe_terms(
        list(company.get("regions") or []) + list(preferences.get("regions") or [])
    )
    return {"keywords": keywords, "capability": capability, "regions": regions}


def has_any_terms(company: dict) -> bool:
    terms = company_terms(company)
    return any(terms.values())


def _matches(haystack: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term in haystack]


def score_tender(
    company: dict,
    *,
    title: str,
    snippet: str = "",
    text: str = "",
    location: str | None = None,
    threshold: float = 0.3,
) -> Relevance:
    terms = company_terms(company)
    haystack = _normalize(" \n ".join([title or "", snippet or "", (text or "")[:40_000], location or ""]))

    categories = [
        ("keyword", terms["keywords"], KEYWORD_WEIGHT),
        ("capability", terms["capability"], CAPABILITY_WEIGHT),
        ("region", terms["regions"], REGION_WEIGHT),
    ]

    active = [(name, items, weight) for name, items, weight in categories if items]
    if not active:
        return Relevance(score=0.0, matched_terms=[], reasons=[], threshold=threshold)

    total_weight = sum(weight for _, _, weight in active)
    score = 0.0
    reasons: list[str] = []
    matched_terms: list[str] = []

    for name, items, weight in active:
        found = _matches(haystack, items)
        normalized_weight = weight / total_weight
        coverage = len(found) / len(items)
        score += normalized_weight * coverage
        if found:
            matched_terms.extend(found)
            label = {"keyword": "keyword", "capability": "capability", "region": "region"}[name]
            reasons.append(f"Matches {label}: {', '.join(found)}")

    if location and _matches(_normalize(location), terms["regions"]):
        reasons.append(f"Extracted location matches region: {location}")

    score = round(min(max(score, 0.0), 1.0), 4)
    if not reasons:
        reasons.append("No declared sector, capability or region matched this source")

    return Relevance(
        score=score,
        matched_terms=sorted(set(matched_terms)),
        reasons=reasons,
        threshold=threshold,
    )
