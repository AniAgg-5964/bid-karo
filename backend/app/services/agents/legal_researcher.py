"""Agent 3: what does the official law say about this clause?

The research is done against official sources only: the allow-list in
``sources.py``. A law firm blog, a news site or a tender portal is refused,
not warned about.

The agent looks in our own index **first**. A page we have read before, and
that is still fresh enough, is used as it is, with the URL and the date it
was read. Only when the memory has nothing, or what it has has gone stale,
does the agent go to the web. Every page it reads is kept, so the next
question about the same provision is answered from the memory instead of the
web.

The shape of the answer is deliberately narrow:

* the index is **searched first**, and a fresh stored reading is used;
* otherwise TinyFish **searches** for the current official page and **reads**
  it, and the page is kept for next time;
* the model then picks the sentences that answer the question, copied
  verbatim from that page;
* the same quote gate we use for tender clauses checks that each sentence
  really is on the page we fetched. A sentence the model paraphrased is
  dropped with a reason;
* the gap against our own evidence is computed here, not by the model;
* the answer carries the URL and the retrieval time, because a reading of the
  law from last year is not a reading of today's law.

What this agent never does: state an obligation that is not in a surviving
quote, give an opinion on enforceability or fairness, or claim we are
compliant.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError

from app.core.exceptions import NotConfiguredError
from app.integrations.ai import AIError, AIProvider
from app.integrations.tinyfish import TinyFishClient
from app.services.agents.gate import check_quote
from app.services.agents.sources import (
    SourcePolicy,
    allows,
    policy_for,
    search_terms_for,
    source_class,
    start_urls_for,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = "legal-research-v1"
MAX_PAGES = 4
PAGE_TEXT_LIMIT = 6000
DISCLAIMER = (
    "Read from official sources on the date shown. This is a source summary, "
    "not legal advice, and it does not replace review by a qualified lawyer."
)

SEARCH_PURPOSE = (
    "Find the current official government page that states this provision, on "
    "official government domains only. Return pages from the government body "
    "that owns the law, not law firm articles or news."
)

FETCH_PURPOSE = (
    "Read this official page and return the text of the provision exactly as "
    "written, with its section number and the title of the instrument."
)

SYSTEM_PROMPT = """You read an official legal page and report what it says.

You are given the text of one official page and a question about one clause of
a tender.

Rules:
1. Answer only from the page text you are given.
2. Every sentence you quote must be copied character for character from that
   text. Never paraphrase, never summarise inside a quote, never join two
   sentences.
3. Give the section number or clause number the sentence belongs to, if the
   page shows one.
4. Say which registrations, records or documents the provision requires the
   company to hold, and the point in the contract or in time at which they
   are needed. Use only what the page supports.
5. If the page does not answer the question, return an empty list.
6. Do not give legal advice, do not comment on enforceability or fairness, and
   do not say the company is compliant.
7. Return JSON only: {"provisions": [...], "applies_to_us": "...", "must_hold": [...],
   "next_action": "..."}."""

USER_TEMPLATE = """Question: {question}

Context: {context}

The official page (title: {title}, url: {url}):

{page_text}
"""


class ProposedProvision(BaseModel):
    """One provision as the model read it."""

    model_config = ConfigDict(extra="ignore")

    quote: str
    section: str | None = None
    instrument: str | None = None


class LegalReading(BaseModel):
    """The model's reading of one page."""

    model_config = ConfigDict(extra="ignore")

    provisions: list[ProposedProvision] = Field(default_factory=list)
    applies_to_us: str | None = None
    must_hold: list[str] = Field(default_factory=list)
    next_action: str | None = None


def parse_reading(payload: Any) -> tuple[LegalReading | None, int]:
    if not isinstance(payload, dict):
        return None, 0
    try:
        reading = LegalReading.model_validate(payload)
    except PydanticValidationError:
        return None, 1
    return reading, 0


def build_question(
    *,
    title: str,
    excerpt: str,
    authority: str | None,
    location: str | None,
    project_type: str | None,
    company_type: str | None,
    employees: int | None,
) -> str:
    """The question the agent is asked, with the facts that decide applicability."""
    parts = [
        f"Which official provisions govern this tender clause, and what must the "
        f"contractor hold to comply with it? Clause: {title}."
    ]
    if excerpt:
        parts.append(f'The tender says: "{excerpt[:600]}"')
    if authority:
        parts.append(f"The authority is {authority}.")
    if location:
        parts.append(f"The work is in {location}.")
    if project_type:
        parts.append(f"The work is {project_type}.")
    if company_type:
        parts.append(f"The company is a {company_type}.")
    if employees:
        parts.append(f"The company has about {employees} employees.")
    return " ".join(parts)


def build_context(company: dict, tender: dict) -> str:
    parts = [
        f"Company: {company.get('name') or 'not stated'}",
        f"Legal form: {company.get('business_type') or 'not stated'}",
        f"Registered in: {', '.join(company.get('regions') or []) or 'not stated'}",
        f"Services: {', '.join(company.get('products_services') or []) or 'not stated'}",
        f"Employees: {company.get('employee_count') or 'not stated'}",
        f"Turnover: {company.get('annual_turnover') or 'not stated'}",
        f"Tender authority: {tender.get('authority') or 'not stated'}",
    ]
    return ". ".join(parts) + "."


def _opening_text(page_text: str, limit: int = 280) -> str:
    """The first words of a page, in the page's own words."""
    for block in page_text.split("\n"):
        line = block.strip().lstrip("#").strip()
        if len(line) >= 40:
            return line[:limit]
    return " ".join(page_text.split())[:limit]


def _evidence_gap(must_hold: list[str], documents: list[dict]) -> tuple[str, list[str]]:
    """Which of the required records we already hold, and which we do not."""
    titles = [
        f"{document.get('title') or ''} {document.get('document_type') or ''}".lower()
        for document in documents
    ]
    held: list[str] = []
    missing: list[str] = []
    for item in must_hold:
        tokens = [
            token
            for token in re.split(r"[^a-z0-9]+", item.lower())
            if len(token) > 3
        ]
        if not tokens:
            continue
        if any(
            all(token in title for token in tokens[:2]) or token in title
            for title in titles
            for token in tokens[:1]
        ):
            held.append(item)
        else:
            missing.append(item)
    if not must_hold:
        return "The official provision did not name a specific record.", []
    if not missing:
        return "We already hold what this provision names: " + ", ".join(held), []
    if held:
        return (
            "We hold "
            + ", ".join(held)
            + ". Still needed: "
            + ", ".join(missing),
            missing,
        )
    return "Not held yet: " + ", ".join(missing), missing


class LegalResearcher:
    """Reads official sources for a clause and keeps only what it can prove."""

    def __init__(
        self,
        *,
        ai: AIProvider,
        client: TinyFishClient,
        max_pages: int = MAX_PAGES,
    ) -> None:
        self.ai = ai
        self.client = client
        self.max_pages = max_pages

    def research(
        self,
        *,
        company: dict,
        tender: dict,
        requirement: dict,
        company_documents: list[dict],
        memory=None,
        retrieved_at: datetime | None = None,
    ) -> list[dict]:
        """Return the provisions found, quoted and checked."""
        if not self.ai.configured:
            raise NotConfiguredError(
                "The AI provider is not configured, so no legal source was read. "
                "Set AI_PROVIDER, the provider API key and model."
            )
        if not self.client.configured:
            raise NotConfiguredError(
                "TinyFish is not configured, so no official source could be read. "
                "Set TINYFISH_API_KEY on the server first."
            )

        excerpt = (requirement.get("excerpt") or "").strip()
        title = (requirement.get("title") or "the clause").strip()
        question = build_question(
            title=title,
            excerpt=excerpt,
            authority=tender.get("authority"),
            location=requirement.get("location") or (tender.get("discovery_extracted") or {}).get("location"),
            project_type=(tender.get("discovery_extracted") or {}).get("location"),
            company_type=company.get("business_type"),
            employees=company.get("employee_count"),
        )
        context = build_context(company, tender)
        policy: SourcePolicy = policy_for(f"{title} {excerpt}")

        # The index first: a reading we already have, if it is fresh enough.
        pages: list[Any] = []
        read_from = "our stored reading"
        if memory is not None:
            try:
                pages = memory.recall(
                    company_id=str(company.get("id") or ""),
                    question=question,
                    topic=policy.topic,
                )
            except Exception as exc:  # noqa: BLE001 - the memory is optional
                logger.info("The legal memory could not be read: %s", exc)
                pages = []

        if not pages:
            read_from = "the official source, read now"
            candidates = self._search(question, policy, f"{title} {excerpt}")
            pages = self._fetch(candidates)
            if memory is not None:
                for page in pages:
                    try:
                        memory.remember(
                            company_id=str(company.get("id") or ""),
                            url=page.url,
                            title=page.title,
                            text=page.text,
                            topic=policy.topic,
                        )
                    except Exception as exc:  # noqa: BLE001 - keeping it is optional
                        logger.info("The page could not be kept: %s", exc)

        results: list[dict] = []
        for page in pages:
            reading = self._read(page, question, context)
            if reading is None:
                continue
            gap, missing = _evidence_gap(reading.must_hold, company_documents)
            for provision in reading.provisions:
                verdict = check_quote(
                    provision.quote,
                    page_text=page.text,
                    min_chars=15,
                    max_chars=4000,
                )
                if verdict.status != "verified":
                    continue
                results.append(
                    {
                        "topic": policy.topic,
                        "question": question,
                        "quote": provision.quote.strip(),
                        "source_url": page.url,
                        "source_title": page.title,
                        "source_class": source_class(page.url),
                        "section": provision.section or provision.instrument,
                        "retrieved_at": retrieved_at or datetime.now(tz=None),
                        "read_from": read_from,
                        "applies_to_us": reading.applies_to_us,
                        "must_hold": list(reading.must_hold),
                        "gap": gap,
                        "next_action": reading.next_action,
                        "grounding_status": verdict.status,
                        "grounding_note": verdict.reason,
                        "disclaimer": DISCLAIMER,
                    }
                )
            if not reading.provisions and page.text.strip():
                # The page is official and we read it, but it does not state the
                # provision in a readable form. Say that, with the link and the
                # date, rather than returning nothing or inventing a clause.
                opening = _opening_text(page.text)
                verdict = check_quote(
                    opening,
                    page_text=page.text,
                    min_chars=15,
                    max_chars=1000,
                )
                if verdict.status == "verified":
                    results.append(
                        {
                            "topic": policy.topic,
                            "question": question,
                            "quote": opening,
                            "source_url": page.url,
                            "source_title": page.title,
                            "source_class": source_class(page.url),
                            "section": None,
                            "retrieved_at": retrieved_at or datetime.now(tz=None),
                            "read_from": read_from,
                            "applies_to_us": reading.applies_to_us,
                            "must_hold": list(reading.must_hold),
                            "gap": (
                                "The official page we could read does not state this "
                                "provision in a readable form. Open the source to read it."
                            ),
                            "next_action": reading.next_action,
                            "grounding_status": "verified",
                            "grounding_note": (
                                "The page was read but it does not contain the "
                                "provision text."
                            ),
                            "disclaimer": DISCLAIMER,
                        }
                    )
        return results

    # ------------------------------------------------------------- research
    def _search(self, question: str, policy: SourcePolicy, subject: str = "") -> list[str]:
        """Find the official pages for a question, and nothing else."""
        query = self._query_for(subject or question, policy)
        urls: list[str] = []
        seen: set[str] = set()
        try:
            hits = self.client.search(query, purpose=SEARCH_PURPOSE, language="en")
        except Exception as exc:  # noqa: BLE001 - a search problem is reported
            raise RuntimeError(f"The official source search failed: {exc}") from exc
        for hit in hits:
            url = hit.url or ""
            if url and url not in seen and allows(url, policy):
                seen.add(url)
                urls.append(url)
        if not urls:
            # The search gave nothing official. Start from the body that owns
            # the law, which is always on the allow-list.
            for url in start_urls_for(question):
                if url not in seen and allows(url, policy):
                    seen.add(url)
                    urls.append(url)
        return urls[: self.max_pages]

    def _query_for(self, subject: str, policy: SourcePolicy) -> str:
        """A short query: the clause, the instrument and the government domain.

        A long question returns the whole web; naming the instrument and the
        domain returns the official page.
        """
        terms = search_terms_for(subject, limit=1)
        primary = next(iter(sorted(policy.hosts)), "")
        words = [
            word
            for word in re.split(r"[^A-Za-z0-9 ]+", subject or "")
            if len(word) > 3
        ][:5]
        query = " ".join([" ".join(words), *terms]).strip()
        if primary:
            query = f"{query} site:{primary}"
        return query

    def _fetch(self, urls: list[str]) -> list:
        if not urls:
            return []
        batch = self.client.fetch(urls, purpose=FETCH_PURPOSE, output_format="markdown")
        return [page for page in batch.pages if page.text]

    def _read(self, page, question: str, context: str):
        page_text = page.text[:PAGE_TEXT_LIMIT]
        try:
            payload = self.ai.complete_json(
                system=SYSTEM_PROMPT,
                user=USER_TEMPLATE.format(
                    question=question,
                    context=context,
                    title=page.title or "official page",
                    url=page.url,
                    page_text=page_text,
                ),
            )
        except AIError:
            return None
        reading, _invalid = parse_reading(payload)
        return reading
