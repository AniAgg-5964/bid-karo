"""Deterministic, explainable profile-fit scoring for discovered tenders.

This is a *discovery relevance* signal: how well a tender matches the company's
declared sectors, products, keywords and regions. It is intentionally separate
from mandatory eligibility and from the Bid Suitability Score (Phase 4), and it
never hides a failed requirement.

Matching is plain text: the company's own words are compared with the tender's
words. There is no model and no embedding lookup, so every match can be
explained. A profile term is matched with a small number of deterministic
variants (plural form and the "B of A" word order) so that one term covers the
way the same work is usually written.
"""

from __future__ import annotations

import re

from app.models.discovery import Relevance

KEYWORD_WEIGHT = 0.4
CAPABILITY_WEIGHT = 0.35
REGION_WEIGHT = 0.25
MIN_TERM_LENGTH = 3
EXTRA_MATCH_BONUS = 0.05
MAX_EXTRA_BONUS = 0.10

# Words that are part of a written work description rather than a category of
# many tenders. A snippet that only contains one of these is not one work.
STOP_WORDS = {"tender", "tenders", "notice", "notices"}


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


def term_variants(term: str) -> list[str]:
    """Deterministic variants of one profile term.

    * the term itself;
    * its plural form, so a company that writes "road" also matches "roads"
      (the reverse is never applied, which avoids false pairs such as
      "electronics" and "electronic");
    * the "B of A" word order for two-word terms, so "road construction" also
      matches "construction of road" and "construction of roads".
    """
    base = _normalize(term)
    if not base:
        return []
    variants: list[str] = [base]
    if not base.endswith("s"):
        if base.endswith(("s", "x", "z", "ch", "sh")):
            variants.append(f"{base}es")
        else:
            variants.append(f"{base}s")
    words = base.split()
    if len(words) == 2:
        variants.append(f"{words[1]} of {words[0]}")
        plural = f"{words[1]}s of {words[0]}" if not words[1].endswith("s") else f"{words[1]} of {words[0]}"
        variants.append(plural)
    seen: set[str] = set()
    unique: list[str] = []
    for variant in variants:
        if variant not in seen:
            seen.add(variant)
            unique.append(variant)
    return unique


def _contains(haystack: str, phrase: str) -> bool:
    pattern = re.escape(phrase).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", haystack))


def _matches(haystack: str, terms: list[str]) -> list[tuple[str, str]]:
    """Return (term, matched variant) for every term present in the haystack."""
    found: list[tuple[str, str]] = []
    for term in terms:
        for variant in term_variants(term):
            if _contains(haystack, variant):
                found.append((term, variant))
                break
    return found


def score_tender(
    company: dict,
    *,
    title: str,
    snippet: str = "",
    text: str = "",
    location: str | None = None,
    context: str = "",
    threshold: float = 0.3,
) -> Relevance:
    """Score a tender against the company profile.

    ``title``, ``snippet`` and ``text`` are the notice's own words and decide
    whether the *work* matches. ``context`` is the page the notice was read
    from, for example the title of a category page. Context is used for the
    region only, so a notice is not treated as road work just because it sits
    on a "Road Construction tenders" listing.
    """
    terms = company_terms(company)
    own_words = _normalize(" \n ".join([title or "", snippet or "", (text or "")[:40_000], location or ""]))
    region_words = _normalize(f"{own_words} {context or ''}")

    categories = [
        ("keyword", terms["keywords"], KEYWORD_WEIGHT),
        ("capability", terms["capability"], CAPABILITY_WEIGHT),
        ("region", terms["regions"], REGION_WEIGHT),
    ]

    active = [(name, items, weight) for name, items, weight in categories if items]
    if not active:
        return Relevance(score=0.0, matched_terms=[], reasons=[], threshold=threshold)

    total_weight = sum(weight for _name, _items, weight in active)
    score = 0.0
    reasons: list[str] = []
    matched_terms: list[str] = []
    extra_matches = 0
    capability_match = False
    keyword_match = False
    region_match = False

    for name, items, weight in active:
        haystack = region_words if name == "region" else own_words
        found = _matches(haystack, items)
        if not found:
            continue
        normalized_weight = weight / total_weight
        score += normalized_weight
        extra_matches += max(0, len(found) - 1)
        matched_terms.extend(term for term, _variant in found)
        label = {"keyword": "keyword", "capability": "capability", "region": "region"}[name]
        for term, variant in found:
            if variant == term:
                reasons.append(f"Matches {label}: {term}")
            else:
                reasons.append(f"Matches {label}: {term} (written as '{variant}')")
        if name == "capability":
            capability_match = True
        elif name == "keyword":
            keyword_match = True
        else:
            region_match = True

    # A capability match is the work itself. A keyword on its own can be an
    # ambiguous acronym ("AMC" is an annual maintenance contract in roads and
    # something else entirely elsewhere), so a keyword only counts when the
    # notice is also in one of the company's regions.
    work_type_match = capability_match or (keyword_match and region_match)

    score += min(extra_matches * EXTRA_MATCH_BONUS, MAX_EXTRA_BONUS)
    score = round(min(max(score, 0.0), 1.0), 4)
    if not reasons:
        reasons.append("No declared sector, capability or region matched this source")

    return Relevance(
        score=score,
        matched_terms=sorted(set(matched_terms)),
        reasons=reasons,
        threshold=threshold,
        work_type_match=work_type_match,
        region_match=region_match,
    )
