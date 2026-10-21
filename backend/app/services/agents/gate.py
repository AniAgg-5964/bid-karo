"""The deterministic gate.

Everything a model proposes is a *claim*. This module decides which claims may
become facts, and it does so with code only: string containment, set
membership, arithmetic and schema validation. No model is called here, so the
verdict is free, instant, reproducible and auditable.

Two rule sets:

``quote gate``
    Applies to anything that quotes a document. The quote must exist on the
    page it was cited from, after whitespace and typography normalisation. A
    paraphrase never passes, and neither does a quote from the wrong page.

``grounding gate``
    Applies to a recommendation, which is not a quote but a statement about
    what to do. It may only refer to clauses that passed the quote gate, and
    it may not introduce a number, date or threshold that is not already in
    those clauses or in the stored tender record.

A failed check never disappears silently: the item is kept with the reason, so
the user can see that the app looked for it and did not find it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

QuoteVerdict = str  # verified | unverified | needs_review

_QUOTE_MAP = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "′": "'",
        "″": '"',
        "–": "-",
        "—": "-",
        "−": "-",
        "…": "...",
        " ": " ",
    }
)

# A number, a percentage, a currency amount or a date inside free text.
_NUMBER_RE = re.compile(
    r"(?:inr|rs\.?|₹)\s*[\d][\d,]*(?:\.\d+)?\s*(?:crore|cr|lakh|lac|lacs|thousand|k)?"
    r"|\b\d[\d,]*(?:\.\d+)?\s*(?:%|percent|crore|cr|lakh|lac|lacs|thousand)\b"
    r"|\b\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}\b"
    r"|\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b"
    r"|\b(?:19|20)\d{2}\b",
    re.IGNORECASE,
)

# Words that mean the date before them is not a closing date.
_PUBLISH_WORDS = re.compile(
    r"\b(publish|published|publication|issued|issue|opening|opened|clarification start"
    r"|upload|uploaded|released)\b",
    re.IGNORECASE,
)


def normalize_for_match(text: str) -> str:
    """Whitespace- and typography-insensitive form, used only for checks."""
    normalized = unicodedata.normalize("NFKC", text or "").translate(_QUOTE_MAP)
    return " ".join(normalized.split()).lower()


@dataclass(slots=True)
class QuoteCheck:
    """The result of checking one quote against one page."""

    status: QuoteVerdict
    reason: str | None = None


def check_quote(
    quote: str,
    *,
    page_text: str | None,
    text_source: str = "text_layer",
    min_chars: int = 20,
    max_chars: int = 5000,
) -> QuoteCheck:
    """Check that a quote really is on the page it was cited from."""
    excerpt = (quote or "").strip()
    if len(excerpt) < min_chars:
        return QuoteCheck("unverified", "Excerpt is too short to verify.")
    if len(excerpt) > max_chars:
        return QuoteCheck("unverified", "Excerpt is too long to verify.")
    if page_text is None:
        return QuoteCheck("unverified", "The cited page does not exist in this document.")
    if not page_text.strip():
        return QuoteCheck("unverified", "The cited page has no extractable text.")
    if normalize_for_match(excerpt) not in normalize_for_match(page_text):
        return QuoteCheck("unverified", "The excerpt was not found verbatim on the cited page.")
    if text_source == "ocr":
        return QuoteCheck(
            "needs_review",
            "Excerpt matched OCR text only; verify it visually against the page image.",
        )
    return QuoteCheck("verified", None)


@dataclass(slots=True)
class GroundingCheck:
    """The result of checking a recommendation against the stored records."""

    grounded: bool
    reason: str | None = None
    dropped_claims: list[str] = field(default_factory=list)
    grounded_requirements: list[str] = field(default_factory=list)
    unsupported_requirements: list[str] = field(default_factory=list)


_AMOUNT_RE = re.compile(
    r"(?:inr|rs\.?|₹)?\s*([\d][\d,]*(?:\.\d+)?)\s*(crore|cr|lakh|lac|lacs|thousand|k)?\b",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*(?:%|percent)\b", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b(\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}"
    r"|\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?\s+\d{4}"
    r"|\d{4})\b",
    re.IGNORECASE,
)
_MULTIPLIERS = {
    "crore": 1e7,
    "cr": 1e7,
    "lakh": 1e5,
    "lac": 1e5,
    "lacs": 1e5,
    "thousand": 1e3,
    "k": 1e3,
}


def _numbers(text: str) -> set[str]:
    """The figures in a text, compared by value rather than by spelling.

    "INR 25 crore" and "250000000" are the same figure, so both become
    ``num:250000000.00``. Dates keep their shape.
    """
    values: set[str] = set()
    for match in _AMOUNT_RE.finditer(text or ""):
        try:
            value = float(match.group(1).replace(",", ""))
        except ValueError:  # pragma: no cover - the pattern only matches digits
            continue
        unit = (match.group(2) or "").lower()
        value *= _MULTIPLIERS.get(unit, 1)
        values.add(f"num:{value:.2f}")
    for match in _PERCENT_RE.finditer(text or ""):
        values.add(f"num:{float(match.group(1).replace(',', '')):.2f}")
    for match in _DATE_RE.finditer(text or ""):
        values.add("date:" + re.sub(r"[\s./-]+", " ", match.group(1).lower()).strip())
    return values


def check_grounding(
    claim: str,
    *,
    requirement_ids: Iterable[str],
    known_requirements: dict[str, dict],
    stored_fields: dict[str, Any] | None = None,
    allowed_kinds: Iterable[str] = (),
) -> GroundingCheck:
    """Check that a recommendation rests on clauses that were already verified.

    * every clause it refers to must exist in the gated requirement set;
    * a clause that was not verified may be referred to, but it is reported as
      unsupported so it cannot be used as a fact;
    * every number, date or threshold in the text must already exist in one of
      the referenced clauses or in the stored tender record.
    """
    known = {_normalise_ref(item): item for item in requirement_ids}
    referenced = [str(item) for item in _referenced_ids(claim)]
    grounded = [known[_normalise_ref(item)] for item in referenced if _normalise_ref(item) in known]
    unsupported = [item for item in referenced if _normalise_ref(item) not in known]

    check = GroundingCheck(
        grounded=bool(grounded),
        grounded_requirements=grounded,
        unsupported_requirements=unsupported,
    )
    if allowed_kinds and not allowed_kinds:
        check.grounded = False
        check.reason = "The recommendation has no allowed kind."
    if not grounded:
        check.reason = "The recommendation does not rest on any stored clause."
        return check

    # Numbers in the claim must already be in a referenced clause or the record.
    haystack: set[str] = set()
    for item in grounded:
        record = known_requirements.get(item) or {}
        for field in ("excerpt", "obligation", "deadline_text", "consequence_text", "title"):
            value = record.get(field)
            if value:
                haystack |= _numbers(str(value))
    for value in (stored_fields or {}).values():
        if isinstance(value, (int, float)):
            haystack.add(f"num:{float(value):.2f}")
        elif value:
            haystack |= _numbers(str(value))

    claim_numbers = _numbers(_REF_RE.sub(" ", claim))
    missing = sorted(number for number in claim_numbers if number not in haystack)
    if missing:
        check.dropped_claims = missing
        check.reason = (
            "The recommendation stated a figure that is not in the clause it "
            "refers to."
        )
        check.grounded = False
    return check


_REF_RE = re.compile(
    r"\b(?:clause|requirement|req|section|item|para(?:graph)?)\s*"
    r"([0-9][0-9A-Za-z.\-()]{0,12})",
    re.IGNORECASE,
)


def _normalise_ref(value: str) -> str:
    """Compare clause references by their characters only.

    "3.1", "3-1" and "Clause 3.1" all mean the same clause, and a
    requirement id is a 32 character id.
    """
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _referenced_ids(claim: str) -> list[str]:
    """The clauses a claim refers to.

    A model may refer to a clause by its number ("clause 3.1") or by its id
    ("req 5f3a..."). Anything else refers to nothing.
    """
    return [match.group(1).rstrip(".,;:)") for match in _REF_RE.finditer(claim or "")]
