"""Deterministic extraction of tender fields from source text.

Rules:
* Extraction is regex/heuristic based, never model based, so it is reproducible.
* Every extracted field keeps the verbatim excerpt it came from.
* If a field cannot be found it stays ``None`` and is reported as unknown. We do
  not infer or invent authorities, deadlines, values or locations.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qsl, urlsplit

from app.models.discovery import ExtractedTender

MAX_TEXT_CHARS = 40_000

OFFICIAL_SUFFIXES = (".gov.in", ".nic.in", ".gov", ".mil.in")
OFFICIAL_HOSTS = {
    "eprocure.gov.in",
    "gem.gov.in",
    "gov.in",
    "nic.in",
    "ireps.gov.in",
    "etenders.gov.in",
    "mahatenders.gov.in",
}

# National e-procurement portals, where tender notices are actually published.
# A government body's own site is a different kind of source (an authority).
OFFICIAL_PORTAL_HOSTS = {
    "eprocure.gov.in",
    "gem.gov.in",
    "ireps.gov.in",
    "etenders.gov.in",
    "mahatenders.gov.in",
}

# Drop only well-known tracking parameters when de-duplicating. Anything else in
# the query string may identify the tender itself (e.g. eProcure's ``sp`` token).
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
}

# Aggregator index / search-result pages, not individual tenders.
LISTING_PATTERNS = (
    r"^\s*\d[\d,]*\s+.{0,100}?\btenders\b",
    r"^\s*latest\b.{0,80}?\btenders\b",
    r"\btenders\s+(?:in|from|of|for)\s+(?:india|[a-z][a-z ]{2,30})\b",
    r"\btender\s+notices\b",
    r"\blist\s+of\b.{0,60}?\btenders\b",
    r"\bbrowse\b.{0,40}?\btenders\b",
    r"^\s*tenders\b",
    r"^\s*tender\s+notices?\b(?!\s*(?:no\.?|number|ref)\b).{0,45}$",
    r"^\s*(?:e-?procurement|government\s+e-?procurement|eprocure|gem|mahatenders|ireps|etenders)\b",
    r"\btenders\b[^|]{0,40}\b20\d{2}\b",
    r"\btenders\b\s*$",
)

INDIAN_STATES = (
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa",
    "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka", "kerala",
    "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland",
    "odisha", "orissa", "punjab", "rajasthan", "sikkim", "tamil nadu", "telangana",
    "tripura", "uttar pradesh", "uttarakhand", "west bengal", "delhi", "jammu",
    "kashmir", "ladakh", "puducherry", "chandigarh", "andaman", "nicobar",
)

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

_DATE_TOKEN = (
    r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    r"|\d{1,2}[-/.](?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[-/.]\d{4}"
    r"|\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?\s+\d{4}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}"
    r"|\d{4}-\d{2}-\d{2})"
)

DEADLINE_LABELS = (
    "last date and time of submission",
    "last date of submission",
    "last date for submission",
    "bid submission end date",
    "bid submission closing date",
    "bid submission end",
    "bid closing date",
    "date of submission of bids",
    "submission deadline",
    "closing date",
    "closes",
    "due date",
    "last date",
    "deadline",
)

# Words that mark a date as the *publishing* date rather than the closing date.
# A publish date is never used as a closing date, otherwise an open tender would
# be discarded because its notice was published weeks ago.
PUBLISH_CONTEXT_LABELS = (
    "published date",
    "publish date",
    "date of publication",
    "published on",
    "published",
    "issue date",
    "issued on",
    "issued",
    "opening date",
    "opened on",
    "opening",
    "clarification start",
    "tender published",
    "released on",
    "uploaded on",
    "uploaded",
)

# Extra closing words that are common in short notices and table headers.
CLOSING_CONTEXT_LABELS = DEADLINE_LABELS + (
    "closing",
    "close",
    "submission end",
    "submission ends",
    "till",
    "upto",
    "up to",
    "bid end date",
    "bid end",
)

# Positive evidence that a notice is not an Indian tender. Only used when no
# Indian marker is present, so an unknown notice is never dropped on a guess.
FOREIGN_MARKERS = (
    "united states",
    "united kingdom",
    "usa",
    "u.s.a",
    "uae",
    "dubai",
    "abu dhabi",
    "singapore",
    "saudi arabia",
    "saudi",
    "australia",
    "canada",
    "germany",
    "france",
    "italy",
    "spain",
    "netherlands",
    "belgium",
    "switzerland",
    "qatar",
    "kuwait",
    "bahrain",
    "oman",
    "sri lanka",
    "bangladesh",
    "myanmar",
    "south africa",
    "nigeria",
    "kenya",
    "egypt",
    "turkey",
    "israel",
    "iran",
    "iraq",
    "brazil",
    "mexico",
    "japan",
    "south korea",
    "china",
    "hong kong",
    "taiwan",
    "malaysia",
    "indonesia",
    "philippines",
    "thailand",
    "vietnam",
    "new zealand",
)

FOREIGN_CURRENCY_MARKERS = ("usd", "gbp", "eur", "aed", "sgd", "cad", "aud", "jpy")

VALUE_LABELS = (
    "estimated cost",
    "estimated value",
    "tender value",
    "contract value",
    "project cost",
    "bid value",
    "total value",
    "estimated amount",
)

VALUE_TOKEN = (
    r"(?:INR|RS\.?|₹)\s*([\d][\d,]*(?:\.\d+)?)\s*(crore|cr|lakh|lac|lacs|thousand|k)?"
    r"|([\d][\d,]*(?:\.\d+)?)\s*(crore|cr|lakh|lac|lacs|thousand)\b"
)

AUTHORITY_LABELS = (
    "organisation name",
    "organization name",
    "tender inviting authority",
    "inviting authority",
    "issuing authority",
    "name of the department",
    "department name",
    "authority name",
    "authority",
    "organisation",
    "organization",
    "department",
)

# Reference numbers are only taken from explicit labels with a word boundary so
# prose such as "Tender Notices" is never misread as a reference.
REFERENCE_PATTERNS = (
    r"\b(?:tender|bid|nit|rfp|rfq|eoi)\s*(?:no|number|ref(?:erence)?)\b\.?\s*[:#\-–—]?\s*([A-Za-z0-9][A-Za-z0-9/\-\.]{2,40})",
    r"\bref(?:erence)?\s*(?:no|number)?\b\.?\s*[:#\-–—]\s*([A-Za-z0-9][A-Za-z0-9/\-\.]{2,40})",
)

# Social platforms and forums never publish official tender documents, so they
# are excluded before any scoring or fetching happens.
BLOCKED_HOSTS = (
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "youtu.be",
    "pinterest.com",
    "reddit.com",
    "quora.com",
    "t.me",
    "whatsapp.com",
)

# Award, result and cancellation notices are not open opportunities.
AWARD_PATTERNS = (
    r"\bawarded\b",
    r"\baward\s+of\s+(?:contract|work|tender)\b",
    r"\bletter\s+of\s+award\b",
    r"\bsuccessful\s+bidder\b",
    r"\b(?:tender|bid)\s+results?\b",
    r"\bcancell?ed\b",
    r"\bcancellation\s+of\s+(?:tender|bid)\b",
)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _clean(value: str) -> str:
    return normalize_text(value).strip(" :-–—\t\r\n").strip()


def _host(url: str) -> str:
    try:
        netloc = urlsplit(url).netloc.lower()
    except ValueError:
        return ""
    if ":" in netloc:
        netloc = netloc.split(":", 1)[0]
    return netloc[4:] if netloc.startswith("www.") else netloc


def is_listing_page(title: str) -> bool:
    """Detect aggregator index/search pages that are not an individual tender.

    Only plural "tenders" phrasing and explicit index patterns are treated as
    listings, so a real title such as "Road construction tender in Maharashtra"
    is not filtered out.
    """
    text = normalize_text(title).lower()
    if not text:
        return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in LISTING_PATTERNS)


def is_blocked_host(url: str) -> bool:
    host = _host(url)
    if not host:
        return False
    return any(host == blocked or host.endswith(f".{blocked}") for blocked in BLOCKED_HOSTS)


def is_award_notice(title: str, snippet: str = "") -> bool:
    """True for award, result or cancellation notices rather than open tenders."""
    text = normalize_text(f"{title} {snippet}").lower()
    if not text:
        return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in AWARD_PATTERNS)


def is_non_tender(title: str, snippet: str = "") -> bool:
    return is_listing_page(title) or is_award_notice(title, snippet)


# --------------------------------------------------------------- listing tables
# Government portals often render tenders as an HTML table. TinyFish returns it
# as a markdown table, so individual tenders can be ingested from the page text.

NAME_HEADERS = (
    "tender name",
    "name of work",
    "work name",
    "tender",
    "work",
    "description",
    "subject",
    "title",
    "particulars",
)
CLOSE_HEADERS = (
    "closing date",
    "closing",
    "last date",
    "due date",
    "submission",
    "end date",
    "deadline",
)
PUBLISH_HEADERS = (
    "publish",
    "published",
    "start date",
    "date of publication",
    "upload",
    "issue date",
)
_DATE_IN_CELL = re.compile(
    r"(\d{1,2}[\s,./-][A-Za-z]{3,9}[\s,./-]\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})"
)
_TABLE_SEPARATOR = re.compile(r"^:?-{2,}:?$")


@dataclass(slots=True)
class TableRowTender:
    title: str
    deadline: str | None
    deadline_raw: str | None
    published: str | None
    excerpt: str


def _table_cells(line: str) -> list[str]:
    return [_clean(cell) for cell in line.strip().strip("|").split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(_TABLE_SEPARATOR.match(cell.replace(" ", "")) for cell in cells)


def _column_index(headers: list[str], terms: tuple[str, ...], *, exclude: set[int]) -> int | None:
    for index, header in enumerate(headers):
        if index in exclude:
            continue
        lowered = header.lower()
        if any(term in lowered for term in terms):
            return index
    return None


def extract_table_rows(
    text: str, *, max_rows: int = 12, today: date | None = None
) -> list[TableRowTender]:
    """Pull individual tenders out of markdown table listings.

    Only rows with a name and a parseable closing date in the future are kept,
    so tables of organisations, counts or past results are ignored.
    """
    if not text:
        return []
    current_day = today or date.today()
    lines = [line.strip() for line in text.splitlines()]
    rows: list[TableRowTender] = []
    index = 0
    while index < len(lines) and len(rows) < max_rows:
        if not (lines[index].startswith("|") and lines[index].count("|") >= 3):
            index += 1
            continue
        block: list[str] = []
        while index < len(lines) and lines[index].startswith("|") and lines[index].count("|") >= 3:
            block.append(lines[index])
            index += 1
        if len(block) < 2:
            continue

        headers = _table_cells(block[0])
        close_idx = _column_index(headers, CLOSE_HEADERS, exclude=set())
        publish_idx = _column_index(
            headers, PUBLISH_HEADERS, exclude={close_idx} if close_idx is not None else set()
        )
        name_idx = _column_index(
            headers,
            NAME_HEADERS,
            exclude={position for position in (close_idx, publish_idx) if position is not None},
        )
        if close_idx is None or name_idx is None:
            # No usable headings. Many portals and aggregators publish their
            # tables without column names, so each row is read positionally.
            for raw_row in block[1:]:
                cells = _table_cells(raw_row)
                if _is_separator_row(cells):
                    continue
                inferred = infer_row_tender(cells, today=current_day)
                if inferred:
                    rows.append(inferred)
                    if len(rows) >= max_rows:
                        break
            continue

        for raw_row in block[1:]:
            cells = _table_cells(raw_row)
            if _is_separator_row(cells):
                continue
            if max(name_idx, close_idx) >= len(cells):
                continue
            title = cells[name_idx]
            if not title or len(title) < 15 or title.lower() in {"tender name", "name of work"}:
                continue
            match = _DATE_IN_CELL.search(cells[close_idx])
            if not match:
                continue
            deadline = parse_date_token(match.group(1))
            if deadline is None or deadline < current_day:
                continue
            published = None
            if publish_idx is not None and publish_idx < len(cells):
                published_match = _DATE_IN_CELL.search(cells[publish_idx])
                if published_match:
                    published = parse_date_token(published_match.group(1))
            rows.append(
                TableRowTender(
                    title=title[:400],
                    deadline=deadline.isoformat(),
                    deadline_raw=match.group(1),
                    published=published.isoformat() if published else None,
                    excerpt=_clean(raw_row)[:400],
                )
            )
            if len(rows) >= max_rows:
                break
    return rows


def row_dedupe_key(url: str, title: str) -> str:
    base = f"{dedupe_key(url, title)}::{normalize_text(title).lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def is_detail_url(url: str) -> bool:
    """True when the URL looks like an individual record rather than a section root."""
    try:
        path = urlsplit(url).path
    except ValueError:
        return False
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) >= 3:
        return True
    return len(segments) == 2 and len(segments[1]) >= 20


def has_many_dated_rows(text: str, *, minimum: int = 4) -> bool:
    """True when the page is mostly a dated table, i.e. a listing rather than one tender."""
    if not text:
        return False
    dated = 0
    for line in text.splitlines():
        if line.count("|") >= 3 and _DATE_IN_CELL.search(line):
            dated += 1
            if dated >= minimum:
                return True
    return False


def classify_source(url: str, site_name: str = "") -> str:
    host = _host(url)
    if not host:
        return "unknown"
    if host in OFFICIAL_HOSTS or host.endswith(OFFICIAL_SUFFIXES):
        return "official"
    return "aggregator"


def dedupe_key(url: str, title: str, site_name: str = "") -> str:
    """Stable per-company key so the same tender updates rather than duplicates.

    Meaningful query parameters are kept because several official portals encode
    the tender id in the query string. Common tracking parameters are dropped.
    """
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/").lower()
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    query.sort()
    query_string = "&".join(f"{key}={value}" for key, value in query)
    if path or query_string:
        base = f"{host}{path}" + (f"?{query_string}" if query_string else "")
    else:
        base = f"{host}:{normalize_text(title).lower()}|{normalize_text(site_name).lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def parse_date_token(token: str) -> date | None:
    token = _clean(token).replace(",", " ").replace(".", " ")
    token = re.sub(r"\s+", " ", token).strip()
    # dd mm yyyy or dd-mm-yyyy
    match = re.fullmatch(r"(\d{1,2})[-/ ](\d{1,2})[-/ ](\d{2,4})", token)
    if match:
        day, month, year = (int(part) for part in match.groups())
        year = _expand_year(year)
        return _safe_date(year, month, day)
    # dd Mon yyyy
    match = re.fullmatch(r"(\d{1,2})[-/.]([a-z]+)[-/.](\d{4})", token.lower())
    if match:
        day, month_name, year = match.groups()
        month = _MONTHS.get(month_name)
        if month:
            return _safe_date(int(year), month, int(day))
    # dd Mon yyyy
    match = re.fullmatch(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", token.lower())
    if match:
        day, month_name, year = match.groups()
        month = _MONTHS.get(month_name)
        if month:
            return _safe_date(int(year), month, int(day))
    # Mon dd yyyy
    match = re.fullmatch(r"([a-z]+)\s+(\d{1,2})\s+(\d{4})", token.lower())
    if match:
        month_name, day, year = match.groups()
        month = _MONTHS.get(month_name)
        if month:
            return _safe_date(int(year), month, int(day))
    # yyyy-mm-dd
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", token)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return _safe_date(year, month, day)
    return None


# ---------------------------------------------------------------------------
# Closing-date rules
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DateFacts:
    """Closing and publish dates read out of a short piece of source text."""

    deadline: date | None = None
    published: date | None = None
    deadline_raw: str | None = None
    context: str = "unknown"  # how the closing date was identified


def _date_tokens(text: str) -> list[tuple[int, str, date]]:
    found: list[tuple[int, str, date]] = []
    for match in re.finditer(_DATE_TOKEN, text, re.IGNORECASE):
        parsed = parse_date_token(match.group(1))
        if parsed:
            found.append((match.start(), match.group(1), parsed))
    return found


def _date_context(text: str, index: int) -> str:
    """Classify a date by the words immediately before it."""
    window = text[max(0, index - 70) : index].lower()
    best_kind = "unknown"
    best_position = -1
    for labels, kind in (
        (PUBLISH_CONTEXT_LABELS, "publish"),
        (CLOSING_CONTEXT_LABELS, "closing"),
    ):
        for label in labels:
            position = window.rfind(label)
            if position > best_position:
                best_position = position
                best_kind = kind
    return best_kind


def read_close_date(text: str, *, today: date | None = None) -> DateFacts:
    """Read the closing date out of a short notice, row or snippet.

    Rules, in order:

    1. A date with a closing/submission word next to it is the closing date.
    2. A date with a publish/open word next to it is never the closing date.
    3. If no date has a closing word, the latest remaining date is used as the
       closing date and the earlier one is kept as the publish date.
    4. A notice that only states a publish date has no closing date at all.
    """
    current_day = today or date.today()
    if not text:
        return DateFacts()
    tokens = _date_tokens(text)
    if not tokens:
        return DateFacts()

    closing = [item for item in tokens if _date_context(text, item[0]) == "closing"]
    published = [item for item in tokens if _date_context(text, item[0]) == "publish"]
    unlabelled = [item for item in tokens if _date_context(text, item[0]) == "unknown"]

    facts = DateFacts()
    if closing:
        _index, raw, parsed = closing[0]
        facts.deadline = parsed
        facts.deadline_raw = raw
        facts.context = "closing"
    elif unlabelled:
        _index, raw, parsed = max(unlabelled, key=lambda item: item[2])
        facts.deadline = parsed
        facts.deadline_raw = raw
        facts.context = "inferred"
    if published:
        facts.published = min(item[2] for item in published)
    if facts.published is None and facts.deadline is not None:
        earlier = [item[2] for item in tokens if item[2] < facts.deadline]
        if earlier:
            facts.published = min(earlier)
    if facts.deadline is not None and facts.deadline < current_day:
        # Expired. The caller decides what to do with it, but we never report an
        # expired date as a usable closing date.
        facts.context = f"{facts.context}:expired"
    return facts


def looks_like_single_notice(text: str) -> bool:
    """True when the page states a closing date for a single work."""
    if not text:
        return False
    lowered = text.lower()
    return any(label in lowered for label in CLOSING_CONTEXT_LABELS)


_GENERIC_TITLE_ENDINGS = ("tender", "tenders", "tender notice", "e-tender", "bid notice")

# Section headings a page uses for its own data, never a description of work.
_LABEL_PHRASE_STARTS = (
    "tender opening",
    "tender closing",
    "tender date",
    "tender amount",
    "tender title",
    "tender value",
    "tender type",
    "tender fee",
    "bid opening",
    "bid closing",
    "bid submission",
    "bid end",
    "bid start",
    "document download",
    "download start",
    "download end",
    "opening date",
    "closing date",
    "last date",
    "first date",
    "published date",
    "publish date",
    "amended date",
    "corrigendum",
    "extension",
    "e-tender",
    "etender",
)


def _looks_like_label_phrase(text: str) -> bool:
    """True for a section heading such as "Tender Opening Date"."""
    lowered = normalize_text(text).lower().strip(" .:|-")
    if not lowered:
        return True
    return lowered.startswith(_LABEL_PHRASE_STARTS)


def is_generic_title(title: str) -> bool:
    """True when a title names an authority or a portal, not a piece of work.

    Aggregators publish many pages called "... Tender" or "Authority - Tender".
    Those titles are useless on a card, so the work description has to come
    from the page itself.
    """
    text = normalize_text(title).lower().strip(" .-|")
    if not text:
        return True
    if _looks_like_label_phrase(text):
        return True
    words = text.split()
    if len(words) <= 8:
        for ending in _GENERIC_TITLE_ENDINGS:
            if text.endswith(ending):
                return True
    if len(text) < 15:
        return True
    return False


def work_name_from_text(text: str) -> str | None:
    """Read a work description from the top of a page.

    The first meaningful line of a notice is its title, e.g.
    "Pune Road Surface Marking Project for Enhanced Safety".
    """
    if not text:
        return None
    for raw_line in text.splitlines():
        line = _clean(raw_line).lstrip("#").strip()
        if len(line) < 20 or len(line) > 200:
            continue
        if line.endswith(":"):
            continue
        if re.search(r"https?://", line, re.IGNORECASE):
            continue
        if _DATE_IN_CELL.search(line) and len(line) < 40:
            continue
        lowered = line.lower()
        if any(
            lowered.startswith(prefix)
            for prefix in (
                "tender no",
                "tender reference",
                "organisation",
                "organization",
                "department",
                "authority",
                "last date",
                "closing date",
                "bid submission",
                "opening date",
                "estimated cost",
                "tender value",
                "work location",
            )
        ):
            continue
        if any(label in lowered for label in DEADLINE_LABELS[:6]):
            continue
        if _looks_like_label_phrase(line):
            continue
        return line
    return None


def is_foreign_notice(text: str) -> bool:
    """True only when the text positively points to a notice outside India."""
    if not text:
        return False
    lowered = text.lower()
    indian_markers = ("india", "inr", "lakh", "crore", "lakhs", "crores", "rupees")
    indian_markers += INDIAN_STATES
    if any(marker in lowered for marker in indian_markers):
        return False
    for marker in FOREIGN_MARKERS:
        if re.search(rf"\b{re.escape(marker)}\b", lowered):
            return True
    for marker in FOREIGN_CURRENCY_MARKERS:
        if re.search(rf"\b{re.escape(marker)}\b", lowered):
            return True
    return False


def _looks_like_reference(cell: str) -> bool:
    """A cell that is only an identifier, not a work description."""
    cleaned = _clean(cell)
    if not cleaned:
        return False
    if len(cleaned) > 40:
        return False
    digits = sum(character.isdigit() for character in cleaned)
    if digits >= 6 and digits >= len(cleaned) * 0.5:
        return True
    return bool(_REFERENCE_CELL_RE.search(cleaned))


_REFERENCE_CELL_RE = re.compile(
    r"\b(?:tender|bid|nit|rfp|rfq|eoi)\s*(?:no|number|ref(?:erence)?)\b", re.IGNORECASE
)


def _looks_like_value(cell: str) -> bool:
    return bool(re.search(VALUE_TOKEN, cell, re.IGNORECASE))


def _looks_like_location(cell: str) -> bool:
    """A cell that names a place rather than describing the work."""
    lowered = cell.lower()
    if "india" in lowered:
        return True
    return any(state in lowered for state in INDIAN_STATES)


def infer_row_tender(cells: list[str], *, today: date | None = None) -> TableRowTender | None:
    """Read one tender out of a table row that has no usable header.

    Many aggregator and government tables are published without column headings.
    The row is read positionally instead: the closing date is the latest date in
    the row, the work description is the longest piece of text, and the
    reference is the cell that is only an identifier.
    """
    current_day = today or date.today()
    if len(cells) < 2:
        return None

    dated: list[tuple[int, date, str]] = []
    for index, cell in enumerate(cells):
        for match in _DATE_IN_CELL.finditer(cell):
            parsed = parse_date_token(match.group(1))
            if parsed:
                dated.append((index, parsed, match.group(1)))
    if not dated:
        return None
    future = [item for item in dated if item[1] >= current_day]
    if not future:
        return None
    close_index, close_date, close_raw = max(future, key=lambda item: item[1])
    published = min((item[1] for item in dated if item[1] < close_date), default=None)

    name = ""
    for index, cell in enumerate(cells):
        if index == close_index:
            continue
        if _DATE_IN_CELL.search(cell):
            continue
        if _looks_like_reference(cell):
            continue
        if _looks_like_value(cell):
            continue
        if _looks_like_location(cell):
            continue
        if len(cell) > len(name):
            name = cell
    # A work description is a sentence, not a column heading.
    if len(name) < 25 or _looks_like_label_phrase(name):
        return None
    return TableRowTender(
        title=name[:400],
        deadline=close_date.isoformat(),
        deadline_raw=close_raw,
        published=published.isoformat() if published else None,
        excerpt=_clean(" | ".join(cells))[:400],
    )


@dataclass(slots=True)
class SnippetNotice:
    """One tender read out of a search result snippet."""

    title: str
    deadline: str | None
    deadline_raw: str | None
    published: str | None
    reference_number: str | None
    excerpt: str
    context: str = "unknown"


def notice_from_snippet(title: str, snippet: str, *, today: date | None = None) -> SnippetNotice | None:
    """Read one tender out of a search result snippet.

    A search result often describes a single notice even when the page it
    points at is a category page. The work description is the text before the
    closing date and the closing date follows the same rules as a table row.
    """
    current_day = today or date.today()
    if not snippet:
        return None
    facts = read_close_date(snippet, today=current_day)
    if facts.deadline is None or facts.deadline < current_day:
        return None

    # The work description is whatever precedes the closing date.
    head = snippet
    if facts.deadline_raw:
        position = snippet.find(facts.deadline_raw)
        if position > 0:
            head = snippet[:position]
    for separator in ("·", "|", "•"):
        if separator in head:
            head = head.split(separator, 1)[0]
    # Drop the closing word itself, e.g. "... Under Ward No. 47. Closes".
    head = re.sub(
        r"\b(?:closing date|closes|close|due date|deadline|last date)\b\s*[:\-]?\s*$",
        "",
        head,
        flags=re.IGNORECASE,
    )
    name = _clean(head).strip(" ,.;:-—–")
    if len(name) < 15:
        return None
    if is_listing_page(name) or _looks_like_label_phrase(name):
        # The snippet only describes a category or a section, not one work.
        return None

    reference = _extract_reference(snippet)
    return SnippetNotice(
        title=name[:400],
        deadline=facts.deadline.isoformat(),
        deadline_raw=facts.deadline_raw,
        published=facts.published.isoformat() if facts.published else None,
        reference_number=reference[0] if reference else None,
        excerpt=_clean(snippet)[:400],
        context=facts.context,
    )


def source_kind(url: str) -> str:
    """Classify where a page comes from.

    * ``official_portal`` - a national e-procurement portal.
    * ``authority`` - a government body's own site.
    * ``aggregator`` - a commercial third-party listing site.
    """
    host = _host(url)
    if not host:
        return "unknown"
    if host in OFFICIAL_HOSTS or host in OFFICIAL_PORTAL_HOSTS:
        return "official_portal"
    if host.endswith(OFFICIAL_SUFFIXES):
        return "authority"
    return "aggregator"


def _expand_year(year: int) -> int:
    if year >= 100:
        return year
    return 2000 + year if year < 70 else 1900 + year


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _search_labeled(
    text: str, labels: tuple[str, ...], value_pattern: str
) -> tuple[str, str] | None:
    """Find ``label ... value`` and return (raw_value, excerpt)."""
    for label in labels:
        pattern = re.compile(
            rf"\b{re.escape(label)}\b\s*[:\-–—]?\s*({value_pattern})",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            raw = _clean(match.group(1))
            if raw:
                return raw, _clean(match.group(0))
    return None


def _extract_authority(text: str) -> tuple[str, str] | None:
    for label in AUTHORITY_LABELS:
        pattern = re.compile(
            rf"\b{re.escape(label)}\b\s*[:\-–—]\s*([^\n\r|]{{3,120}})", re.IGNORECASE
        )
        match = pattern.search(text)
        if match:
            value = _clean(match.group(1))
            value = re.split(r"\s{2,}|\t", value)[0]
            if 3 <= len(value) <= 120:
                return value, _clean(match.group(0))
    return None


def _extract_deadline(text: str) -> tuple[date, str, str] | None:
    for label in DEADLINE_LABELS:
        pattern = re.compile(
            rf"\b{re.escape(label)}\b[^\d\n\r]{{0,40}}?({_DATE_TOKEN})",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            parsed = parse_date_token(match.group(1))
            if parsed:
                return parsed, _clean(match.group(1)), _clean(match.group(0))
    return None


def _extract_value(text: str, *, require_label: bool = True) -> tuple[float, str, str] | None:
    if require_label:
        result = _search_labeled(text, VALUE_LABELS, VALUE_TOKEN)
        if not result:
            return None
        raw, excerpt = result
        amount = _parse_amount(raw)
        if amount is None:
            return None
        return amount, raw, excerpt

    # Fallback: an explicit currency amount with a unit, e.g. "₹ 43.90 Crore".
    # Only ever applied to the short title/snippet, never to a whole fetched page.
    match = re.search(
        r"(?:INR|Rs\.?|₹)\s*[\d][\d,]*(?:\.\d+)?\s*(?:crore|cr|lakh|lac|lacs|thousand)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    raw = _clean(match.group(0))
    amount = _parse_amount(raw)
    if amount is None:
        return None
    return amount, raw, raw


def _extract_reference(text: str) -> tuple[str, str] | None:
    for pattern in REFERENCE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = _clean(match.group(1))
            # Reference numbers in practice contain at least one digit; rejecting
            # prose keeps labels like "Tender Notices" from inventing a reference.
            if value and re.search(r"\d", value):
                return value, _clean(match.group(0))[:300]
    return None


def _extract_location(text: str, brief: str) -> tuple[str, str] | None:
    labeled = _search_labeled(
        text, ("location", "place of work", "work location"), r"([A-Za-z][A-Za-z ,\.\-]{2,60})"
    )
    if labeled:
        return labeled[0], labeled[1]
    # Fall back to a state named in the tender's own title/snippet, never to a
    # state merely mentioned somewhere in the fetched page.
    lowered = brief.lower()
    best: tuple[int, str] | None = None
    for state in INDIAN_STATES:
        idx = lowered.find(state)
        if idx >= 0 and (best is None or idx < best[0]):
            best = (idx, state)
    if best is None:
        return None
    idx, state = best
    return state.title(), _clean(brief[max(0, idx - 20) : idx + len(state) + 20])


def extract_fields(title: str, snippet: str, page_text: str = "") -> ExtractedTender:
    brief = "\n".join(part for part in (title, snippet) if part)
    text = "\n".join(part for part in (title, snippet, (page_text or "")[:MAX_TEXT_CHARS]) if part)
    result = ExtractedTender()
    evidence: dict[str, str] = {}

    authority = _extract_authority(text)
    if authority:
        result.authority = authority[0]
        evidence["authority"] = authority[1][:300]

    reference = _extract_reference(text)
    if reference:
        result.reference_number = reference[0]
        evidence["reference_number"] = reference[1]

    deadline = _extract_deadline(text)
    if deadline:
        parsed, raw, excerpt = deadline
        result.deadline = parsed.isoformat()
        result.deadline_raw = raw
        evidence["deadline"] = excerpt[:300]

    value = _extract_value(text) or _extract_value(brief, require_label=False)
    if value:
        amount, raw, excerpt = value
        result.value_amount = amount
        result.value_currency = "INR"
        result.value_raw = raw
        evidence["value"] = excerpt[:300]

    location = _extract_location(text, brief)
    if location:
        result.location = location[0]
        evidence["location"] = location[1][:300]

    result.evidence = evidence
    return result


def _parse_amount(raw: str) -> float | None:
    match = re.search(VALUE_TOKEN, raw, re.IGNORECASE)
    if not match:
        return None
    amount_str = match.group(1) or match.group(3)
    unit = (match.group(2) or match.group(4) or "").lower()
    if not amount_str:
        return None
    try:
        amount = float(amount_str.replace(",", ""))
    except ValueError:
        return None
    if unit in {"crore", "cr"}:
        amount *= 10_000_000
    elif unit in {"lakh", "lac", "lacs"}:
        amount *= 100_000
    elif unit in {"thousand", "k"}:
        amount *= 1_000
    return amount


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()
