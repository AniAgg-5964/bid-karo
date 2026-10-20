"""Web-wide tender discovery through TinyFish, scoped to a company profile.

Flow per run:

1. Build search queries deterministically from the company profile.
2. Search (free) and de-duplicate candidate URLs.
3. Pre-score every candidate from its title/snippet.
4. Fetch the most promising candidates (free) in batches of 10.
5. Re-score with the fetched text and extract tender fields deterministically.
6. Persist every candidate with provenance; list only those at/above the threshold.

Everything is deterministic except the raw text that TinyFish returns, which is
treated as untrusted input.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

from app.core.config import Settings, get_settings
from app.core.database import Database, utcnow
from app.core.exceptions import NotConfiguredError, NotFoundError, UpstreamError, ValidationError
from app.integrations.tinyfish import TinyFishClient, TinyFishError, TinyFishNotConfigured
from app.models.discovery import (
    DiscoveryRunRequest,
    DiscoveryStatusResponse,
    ExtractedTender,
    TenderStatus,
)
from app.repositories.audit import AuditRepository
from app.repositories.discovery import DiscoveryRunRepository, DiscoveryTenderRepository
from app.repositories.tenders import TenderRepository
from app.services import tender_extraction as extraction
from app.services.relevance import company_terms, has_any_terms, score_tender

MAX_QUERIES = 12
FETCH_BATCH = 10

logger = logging.getLogger(__name__)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    # Deadlines here are calendar dates with no stated time. Anchor them at noon UTC
    # so the same calendar day survives display in timezones such as IST (UTC+5:30).
    return datetime.combine(parsed, time(12, 0), tzinfo=timezone.utc)


def _interleave(*groups: list[str]) -> list[str]:
    """Alternate between groups so every kind of profile term gets a turn.

    A company with five keywords and nine services must not spend the whole
    query budget on keywords, and a company with only services must not lose
    them to a keyword that happens to be listed first.
    """
    result: list[str] = []
    lists = [list(group) for group in groups if group]
    for index in range(max((len(group) for group in lists), default=0)):
        for group in lists:
            if index < len(group):
                result.append(group[index])
    seen: set[str] = set()
    unique: list[str] = []
    for item in result:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


class DiscoveryService:
    def __init__(
        self,
        db: Database,
        *,
        client: TinyFishClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.client = client or TinyFishClient.from_settings(self.settings)
        self.tenders = DiscoveryTenderRepository(db)
        self.runs = DiscoveryRunRepository(db)
        self.saved = TenderRepository(db)
        self.audit = AuditRepository(db)

    # ------------------------------------------------------------------ status
    def status(self) -> DiscoveryStatusResponse:
        return DiscoveryStatusResponse(
            configured=self.client.configured,
            base_url=self.client.base_url,
            min_score=self.settings.discovery_min_score,
            max_candidates=self.settings.discovery_max_candidates,
            fetch_limit=self.settings.discovery_fetch_limit,
        )

    # ----------------------------------------------------------------- queries
    def build_queries(self, company: dict, keywords_override: str | None = None) -> list[str]:
        """Build search queries from every part of the company profile.

        Every service, sector, keyword and region the company declared gets a
        turn, because the profile is the only dictionary the matcher has. The
        official portals are queried as well, so notices from the source of
        record are looked for directly.
        """
        terms = company_terms(company)
        regions = terms["regions"][:3]
        topics = _interleave(terms["keywords"], terms["capability"])[:5]
        region = regions[0].title() if regions else "India"

        queries: list[str] = []
        seen: set[str] = set()

        def add(query: str) -> None:
            cleaned = " ".join(query.split())
            key = cleaned.lower()
            if cleaned and key not in seen and len(queries) < MAX_QUERIES:
                seen.add(key)
                queries.append(cleaned)

        override = (keywords_override or "").strip()
        if override:
            add(f"{override} tender {region}")
            add(f"{override} tender India")

        # Different queries use different profile terms, so one narrow keyword
        # cannot take the whole budget.
        for topic in topics[:2]:
            for candidate_region in regions[:2]:
                add(f"{topic} tender {candidate_region.title()}")
        for topic in topics[2:4]:
            add(f"{topic} tender notice closing date {region}")
        for topic in topics[0:1] + topics[4:5]:
            add(f"{topic} tender {region} last date of submission")
        for topic in topics[1:2] + topics[2:3]:
            add(f"{topic} tender India")
        for topic in topics[:2]:
            add(f"{topic} tender site:etenders.gov.in")
        for topic in topics[1:2]:
            add(f"{topic} tender site:eprocure.gov.in")

        return queries[:MAX_QUERIES]

    def _purpose(self, company: dict) -> str:
        terms = company_terms(company)
        bits = []
        if terms["capability"]:
            bits.append("capabilities: " + ", ".join(terms["capability"][:6]))
        if terms["regions"]:
            bits.append("regions: " + ", ".join(terms["regions"][:4]))
        context = "; ".join(bits) or "general civil works"
        return f"Find open public procurement tenders in India matching a company's {context}."

    # --------------------------------------------------------------------- run
    def run(
        self,
        company: dict,
        user_id: str,
        request: DiscoveryRunRequest | None = None,
    ) -> tuple[dict, list[dict], int]:
        request = request or DiscoveryRunRequest()
        if not self.client.configured:
            raise NotConfiguredError(
                "TinyFish is not configured. Add TINYFISH_API_KEY to enable live discovery."
            )
        if not has_any_terms(company):
            raise ValidationError(
                "Add at least one sector, product/service or keyword to your company profile "
                "before running discovery."
            )

        company_id = company["id"]
        queries = self.build_queries(company, request.keywords)
        if not queries:
            raise ValidationError("No search queries could be built from the company profile.")

        min_score = request.min_score if request.min_score is not None else self.settings.discovery_min_score
        max_candidates = request.max_candidates or self.settings.discovery_max_candidates
        fetch_limit = self.settings.discovery_fetch_limit if request.fetch_limit is None else request.fetch_limit
        fetch_limit = max(0, min(fetch_limit, FETCH_BATCH))

        run = self.runs.create(company_id, queries)
        stats = {
            "queries": len(queries),
            "search_hits": 0,
            "unique_candidates": 0,
            "prequalified": 0,
            "fetched": 0,
            "fetch_failed": 0,
            "matched": 0,
            "listed": 0,
            "skipped_low_relevance": 0,
            "skipped_non_tender": 0,
            "tenders_from_listings": 0,
            "notices_from_search_results": 0,
            "rows_found": 0,
            "skipped_no_work_match": 0,
            "skipped_no_deadline": 0,
            "skipped_no_work_description": 0,
            "skipped_foreign": 0,
        }

        stored: list[dict] = []
        try:
            candidates = self._collect_candidates(queries, company, stats)
            stats["unique_candidates"] = len(candidates)

            # Score every candidate first, then keep the best ones. Slicing the
            # raw search order would drop relevant results from later queries.
            ordered = self._prequalify(candidates, company, min_score, stats)
            selected = ordered[:max_candidates]
            fetch_urls = self._select_fetch_urls(selected, fetch_limit)
            stored = self._fetch_and_store(selected, fetch_urls, company, min_score, stats)
        except TinyFishNotConfigured as exc:
            self.runs.finish(run["id"], company_id, status="failed", stats=stats, error=str(exc))
            raise NotConfiguredError(str(exc)) from exc
        except TinyFishError as exc:
            self.runs.finish(run["id"], company_id, status="failed", stats=stats, error=str(exc))
            raise UpstreamError(f"Discovery failed while contacting TinyFish: {exc}") from exc

        listed, sources, counts = self._qualify(stored, min_score)
        stats.update(counts)
        listed = self._sort_listed(listed)
        stats["listed"] = len(listed)
        finished = self.runs.finish(run["id"], company_id, status="completed", stats=stats)

        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="discovery.run",
            entity_type="discovery_run",
            entity_id=run["id"],
            metadata={"queries": len(queries), "listed": len(listed), "matched": stats["matched"]},
        )
        return finished, listed, len(listed), sources

    @staticmethod
    def _sort_listed(items: list[dict]) -> list[dict]:
        """Rank the listed tenders: the company's own regions first, then the
        strongest profile fit, then official sources, then the closest date."""
        return sorted(
            items,
            key=lambda item: (
                (item.get("relevance") or {}).get("region_match", False),
                (item.get("relevance") or {}).get("score", 0),
                item.get("source_type") == "official",
                (item.get("extracted") or {}).get("deadline") or "",
            ),
            reverse=True,
        )

    def _collect_candidates(
        self, queries: list[str], company: dict, stats: dict
    ) -> list[dict]:
        purpose = self._purpose(company)
        by_url: dict[str, dict] = {}
        for query in queries:
            hits = self.client.search(
                query, purpose=purpose, location="in", language="en"
            )
            stats["search_hits"] += len(hits)
            for hit in hits:
                if hit.url in by_url:
                    continue
                if extraction.is_blocked_host(hit.url):
                    continue
                by_url[hit.url] = {
                    "query": query,
                    "title": hit.title or hit.url,
                    "url": hit.url,
                    "snippet": hit.snippet,
                    "site_name": hit.site_name,
                    "published_hint": hit.published_date,
                }
        return list(by_url.values())

    @staticmethod
    def _select_fetch_urls(ordered: list[dict], limit: int) -> set[str]:
        """Pick which candidates to fetch: mostly notice pages, plus a couple of listings.

        Listing pages are the only way to reach tenders that are published as
        table rows, so a small budget is always reserved for them.
        """
        if limit <= 0:
            return set()
        listing_budget = min(2, limit)
        detail_budget = limit - listing_budget
        details: list[str] = []
        listings: list[str] = []
        for candidate in ordered:
            is_listing = extraction.is_listing_page(candidate["title"])
            if is_listing and len(listings) < listing_budget:
                listings.append(candidate["url"])
            elif not is_listing and len(details) < detail_budget:
                details.append(candidate["url"])
            if len(details) >= detail_budget and len(listings) >= listing_budget:
                break
        remaining = [
            candidate["url"]
            for candidate in ordered
            if candidate["url"] not in details and candidate["url"] not in listings
        ]
        chosen = (details + listings + remaining)[:limit]
        return set(chosen)

    def _prequalify(
        self,
        candidates: list[dict],
        company: dict,
        min_score: float,
        stats: dict,
    ) -> list[dict]:
        threshold = min_score
        scored: list[tuple[float, dict]] = []
        for candidate in candidates:
            source_type = extraction.classify_source(candidate["url"], candidate["site_name"])
            relevance = score_tender(
                company,
                title=candidate["title"],
                snippet=candidate["snippet"],
                threshold=threshold,
            )
            candidate["source_type"] = source_type
            candidate["source_kind"] = extraction.source_kind(candidate["url"])
            candidate["pre_relevance"] = relevance
            scored.append((relevance.score, candidate))

        # Individual notice pages first, then official sources, then the
        # strongest profile fit. Portal roots are fetched last because they
        # rarely carry a single tender's deadline or reference.
        def order_key(item: tuple[float, dict]) -> tuple[bool, bool, bool, bool, float]:
            score, candidate = item
            listing = extraction.is_listing_page(candidate["title"])
            relevance = candidate.get("pre_relevance")
            work_match = bool(relevance and relevance.work_type_match)
            return (
                work_match,
                extraction.is_detail_url(candidate["url"]) and not listing,
                candidate["source_type"] == "official" and not listing,
                not listing,
                score,
            )

        scored.sort(key=order_key, reverse=True)
        ordered = [candidate for _score, candidate in scored]
        stats["prequalified"] = sum(
            1
            for _score, candidate in scored
            if (candidate.get("pre_relevance") or None)
            and candidate["pre_relevance"].work_type_match
        )
        return ordered

    def _fetch_and_store(
        self,
        candidates: list[dict],
        fetch_urls: set[str],
        company: dict,
        min_score: float,
        stats: dict,
    ) -> list[dict]:
        company_id = company["id"]
        now = utcnow()
        purpose = self._purpose(company)

        to_fetch = [c for c in candidates if c["url"] in fetch_urls]
        cache = self._recent_cache(company_id, to_fetch)
        pending = [c for c in to_fetch if c["url"] not in cache]

        fetched_pages: dict[str, object] = {}
        fetch_errors: dict[str, str] = {}
        for index in range(0, len(pending), FETCH_BATCH):
            chunk = [c["url"] for c in pending[index : index + FETCH_BATCH]]
            batch = self.client.fetch(chunk, purpose=purpose)
            for page in batch.pages:
                fetched_pages[page.url] = page
            fetch_errors.update(batch.errors)

        stored: dict[str, dict] = {}
        for candidate in candidates:
            key = extraction.dedupe_key(candidate["url"], candidate["title"], candidate["site_name"])
            cached = cache.get(candidate["url"])
            if cached:
                stored[key] = cached
                for child in self.tenders.list_children(company_id, candidate["url"]):
                    stored[child["dedupe_key"]] = child
                continue

            page = fetched_pages.get(candidate["url"])
            fetch_status = "not_fetched"
            fetch_error = None
            text = ""
            page_title = None
            if page is not None:
                text = page.text or ""
                page_title = page.title
                fetch_status = "fetched"
                stats["fetched"] += 1
            elif candidate["url"] in fetch_errors:
                fetch_status = (
                    "blocked" if "block" in fetch_errors[candidate["url"]].lower() else "error"
                )
                fetch_error = fetch_errors[candidate["url"]]
                stats["fetch_failed"] += 1

            title = candidate["title"] or page_title or candidate["url"]
            rows = extraction.extract_table_rows(text) if text else []
            stats["rows_found"] += len(rows)
            is_award = extraction.is_award_notice(title, candidate["snippet"])
            # A page is a listing when its title reads like a category, or when
            # it is mostly a table of notices. A page that states a closing date
            # for one work stays a single tender, even when it also carries a
            # small table of its own.
            title_is_listing = extraction.is_listing_page(title)
            single_notice = extraction.looks_like_single_notice(
                text or candidate["snippet"] or ""
            )
            if title_is_listing:
                is_listing = True
            elif single_notice:
                is_listing = False
            else:
                is_listing = bool(rows) or extraction.has_many_dated_rows(text)

            # A search result often describes one notice even when the page it
            # points at is a category page.
            snippet_notice = extraction.notice_from_snippet(title, candidate["snippet"])

            record_title = title
            has_work_description = True
            if fetch_status == "not_fetched" and snippet_notice and not is_listing:
                # Without the page we only have the search result, so the work
                # name is taken from the snippet rather than the page title.
                record_title = snippet_notice.title
            elif not is_listing and extraction.is_generic_title(record_title):
                # Many aggregator pages are called "<Authority> Tender". The work
                # description on the page itself is the useful title. When the
                # page has no description either, it is not a tender.
                from_page = extraction.work_name_from_text(text)
                if from_page:
                    record_title = from_page
                else:
                    has_work_description = False

            if is_listing:
                extracted = ExtractedTender()
            else:
                extracted = extraction.extract_fields(
                    record_title, candidate["snippet"], text
                )
                if not extracted.deadline:
                    facts = extraction.read_close_date(candidate["snippet"])
                    if facts.deadline and facts.context in {"closing", "inferred"}:
                        extracted.deadline = facts.deadline.isoformat()
                        extracted.deadline_raw = facts.deadline_raw
                        extracted.evidence["deadline"] = candidate["snippet"][:300]

            relevance = score_tender(
                company,
                title=record_title,
                snippet=candidate["snippet"],
                text="" if is_listing else text,
                location=extracted.location,
                context=title,
                threshold=min_score,
            )
            is_foreign = extraction.is_foreign_notice(
                " ".join([record_title, candidate["snippet"], text[:2000]])
            )

            values = {
                "source": "tinyfish",
                "source_type": candidate["source_type"],
                "source_kind": candidate.get("source_kind", "unknown"),
                "source_url": candidate["url"],
                "site_name": candidate["site_name"],
                "title": record_title[:400],
                "snippet": candidate["snippet"][:1000],
                "query": candidate["query"],
                "retrieved_at": now,
                "published_hint": candidate.get("published_hint"),
                "extracted": extracted.model_dump(),
                "relevance": relevance.model_dump(),
                "fetch_status": fetch_status,
                "fetch_error": fetch_error,
                "is_listing_page": is_listing,
                "is_award_notice": is_award,
                "is_foreign": is_foreign,
                "has_work_description": has_work_description,
                "content_excerpt": text[:4000] or None,
                "content_hash": extraction.content_hash(text) if text else None,
            }
            if fetch_status == "not_fetched":
                document, _created = self.tenders.ensure(company_id, key, values)
            else:
                document, _created = self.tenders.upsert(company_id, key, values)
            stored[key] = document

            if is_listing and snippet_notice:
                notice_document = self._store_snippet_notice(
                    company, candidate, snippet_notice, now, min_score, fetch_status
                )
                stored[notice_document["dedupe_key"]] = notice_document
                stats["notices_from_search_results"] += 1

            for row in rows:
                child = self._store_row(company, candidate, row, now, min_score)
                stored[child["dedupe_key"]] = child
                stats["tenders_from_listings"] += 1

        unique_stored = list(stored.values())
        return unique_stored

    def _store_snippet_notice(
        self,
        company: dict,
        candidate: dict,
        notice: extraction.SnippetNotice,
        now: datetime,
        min_score: float,
        fetch_status: str,
    ) -> dict:
        """Store one tender that was read out of a search result.

        The source URL stays the page the result pointed at, because that is
        where the notice was seen. The record is marked ``search_result`` so the
        user knows it was not read from the notice's own page.
        """
        extracted = ExtractedTender(
            deadline=notice.deadline,
            deadline_raw=notice.deadline_raw,
            reference_number=notice.reference_number,
            evidence={"deadline": notice.excerpt, "title": notice.excerpt},
        )
        # Anything else the notice states itself is taken from the same text.
        details = extraction.extract_fields(notice.title, notice.excerpt, "")
        extracted.authority = details.authority or None
        extracted.value_amount = details.value_amount
        extracted.value_currency = details.value_currency
        extracted.value_raw = details.value_raw
        extracted.location = details.location or None
        for field in ("authority", "value", "location"):
            if details.evidence.get(field):
                extracted.evidence[field] = details.evidence[field][:300]
        relevance = score_tender(
            company,
            title=notice.title,
            snippet=notice.excerpt,
            context=candidate.get("title") or "",
            threshold=min_score,
        )
        values = {
            "source": "tinyfish",
            "source_type": candidate["source_type"],
            "source_kind": candidate.get("source_kind", "unknown"),
            "source_url": candidate["url"],
            "site_name": candidate["site_name"],
            "title": notice.title,
            "snippet": notice.excerpt,
            "query": candidate["query"],
            "retrieved_at": now,
            "published_hint": notice.published,
            "extracted": extracted.model_dump(),
            "relevance": relevance.model_dump(),
            "fetch_status": fetch_status,
            "fetch_error": None,
            "is_listing_page": False,
            "is_award_notice": extraction.is_award_notice(notice.title),
            "is_foreign": extraction.is_foreign_notice(notice.excerpt),
            "parent_url": candidate["url"],
            "extracted_from": "search_result",
            "content_excerpt": notice.excerpt,
            "content_hash": extraction.content_hash(notice.excerpt),
        }
        key = extraction.row_dedupe_key(candidate["url"], notice.title)
        document, _created = self.tenders.upsert(company["id"], key, values)
        return document

    @staticmethod
    def _is_non_tender(item: dict) -> bool:
        return bool(item.get("is_listing_page") or item.get("is_award_notice"))

    def _qualify(
        self, stored: list[dict], min_score: float
    ) -> tuple[list[dict], list[dict], dict]:
        """Split stored candidates into listed tenders, sources and counts.

        A tender is listed when all of these are true:

        * it is one specific work, not an index page and not an award notice;
        * the work matches the company's own work types (services, sectors or
          keywords). The region only decides the order, not the visibility;
        * a closing date was read from the source and that date is still in the
          future. An expired tender is never shown, and a notice without a
          closing date is not a tender;
        * the notice is an Indian one.

        Everything else is counted with its reason. Nothing is silently promoted
        to a tender and nothing is silently dropped.
        """
        today = date.today().isoformat()
        listed: list[dict] = []
        sources: list[dict] = []
        closed = 0
        unverified = 0
        low = 0
        no_work_match = 0
        no_deadline = 0
        no_description = 0
        foreign = 0
        for item in stored:
            score = (item.get("relevance") or {}).get("score", 0)
            relevance = item.get("relevance") or {}
            extracted = item.get("extracted") or {}
            deadline = extracted.get("deadline")

            if item.get("is_foreign"):
                foreign += 1
                self._mark(item, listed=False, reason="foreign_notice")
                continue
            if self._is_non_tender(item):
                # Official portals and strong index pages are worth showing as
                # places the user can check.
                if item.get("source_type") == "official" or score >= min_score:
                    sources.append(item)
                self._mark(item, listed=False, reason="index_page")
                continue
            if not relevance.get("work_type_match"):
                no_work_match += 1
                self._mark(item, listed=False, reason="no_work_match")
                continue
            if item.get("has_work_description") is False:
                no_description += 1
                self._mark(item, listed=False, reason="no_work_description")
                continue
            if not deadline:
                no_deadline += 1
                self._mark(item, listed=False, reason="no_closing_date")
                continue
            if deadline < today:
                closed += 1
                self._mark(item, listed=False, reason="already_closed")
                continue
            listed.append(item)
            self._mark(item, listed=True, reason=None)

        sources.sort(
            key=lambda item: (
                item.get("source_type") == "official",
                (item.get("relevance") or {}).get("score", 0),
            ),
            reverse=True,
        )
        counts = {
            "matched": len(listed),
            "listed": len(listed),
            "skipped_low_relevance": low,
            "skipped_non_tender": len(sources),
            "skipped_listing": sum(1 for item in sources if item.get("is_listing_page")),
            "skipped_closed": closed,
            "skipped_unverified": unverified,
            "skipped_no_work_match": no_work_match,
            "skipped_no_deadline": no_deadline,
            "skipped_no_work_description": no_description,
            "skipped_foreign": foreign,
        }
        return listed, sources[:8], counts

    def _mark(self, item: dict, *, listed: bool, reason: str | None) -> None:
        """Store the listing decision so the reason can be shown to the user."""
        company_id = item.get("company_id")
        tender_id = item.get("id")
        if not company_id or not tender_id:
            return
        self.tenders.set_listing_state(company_id, tender_id, listed=listed, reason=reason)

    def _store_row(
        self,
        company: dict,
        candidate: dict,
        row: extraction.TableRowTender,
        now: datetime,
        min_score: float,
    ) -> dict:
        """Persist one tender parsed out of a listing table.

        The source URL stays the listing page (that is where the row was read
        from) and the verbatim table row is kept as the evidence excerpt.
        """
        extracted = ExtractedTender(
            deadline=row.deadline,
            deadline_raw=row.deadline_raw,
            evidence={"deadline": row.excerpt, "title": row.excerpt},
        )
        relevance = score_tender(
            company, title=row.title, snippet=row.excerpt, threshold=min_score
        )
        values = {
            "source": "tinyfish",
            "source_type": candidate["source_type"],
            "source_kind": candidate.get("source_kind", "unknown"),
            "source_url": candidate["url"],
            "site_name": candidate["site_name"],
            "title": row.title,
            "snippet": row.excerpt,
            "query": candidate["query"],
            "retrieved_at": now,
            "published_hint": row.published,
            "extracted": extracted.model_dump(),
            "relevance": relevance.model_dump(),
            "fetch_status": "fetched",
            "fetch_error": None,
            "is_listing_page": False,
            "is_award_notice": extraction.is_award_notice(row.title),
            "is_foreign": extraction.is_foreign_notice(f"{row.title} {row.excerpt}"),
            "parent_url": candidate["url"],
            "extracted_from": "listing_table",
            "content_excerpt": row.excerpt,
            "content_hash": extraction.content_hash(row.excerpt),
        }
        key = extraction.row_dedupe_key(candidate["url"], row.title)
        document, _created = self.tenders.upsert(company["id"], key, values)
        return document

    def _recent_cache(self, company_id: str, candidates: list[dict]) -> dict[str, dict]:
        keys = [
            extraction.dedupe_key(c["url"], c["title"], c["site_name"]) for c in candidates
        ]
        if not keys:
            return {}
        cutoff = utcnow() - timedelta(hours=self.settings.discovery_cache_hours)
        cursor = self.db.discovered_tenders.find(
            {
                "company_id": company_id,
                "dedupe_key": {"$in": keys},
                "fetch_status": "fetched",
                "content_hash": {"$ne": None},
                "last_seen_at": {"$gte": cutoff},
            }
        )
        cache: dict[str, dict] = {}
        for item in cursor:
            payload = {key: value for key, value in item.items() if key != "_id"}
            payload["id"] = item["_id"]
            cache[item["source_url"]] = payload
        return cache

    # ---------------------------------------------------------------- read API
    def list_tenders(
        self,
        company_id: str,
        *,
        min_score: float | None = None,
        statuses: list[str] | None = None,
        exclude_non_tender: bool = True,
        ready_only: bool = True,
        listed_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        return self.tenders.list_for_company(
            company_id,
            min_score=min_score,
            statuses=statuses,
            exclude_non_tender=exclude_non_tender,
            ready_only=ready_only,
            listed_only=listed_only,
            limit=limit,
            offset=offset,
        )

    def list_sources(self, company_id: str, limit: int = 8) -> list[dict]:
        return self.tenders.list_sources(company_id, limit=limit)

    def get_tender(self, tender_id: str, company_id: str) -> dict:
        document = self.tenders.find_for_company(tender_id, company_id)
        if not document:
            raise NotFoundError("Discovered tender not found.")
        return document

    def list_runs(self, company_id: str, limit: int = 10, offset: int = 0) -> tuple[list[dict], int]:
        return self.runs.list_for_company(company_id, limit=limit, offset=offset)

    def set_status(self, tender_id: str, company_id: str, status: TenderStatus) -> dict:
        document = self.tenders.set_status(tender_id, company_id, status)
        if not document:
            raise NotFoundError("Discovered tender not found.")
        return document

    def save_tender(self, tender_id: str, company_id: str, user_id: str, status: str = "saved") -> dict:
        document = self.get_tender(tender_id, company_id)
        existing = self.saved.find_by_discovered(tender_id, company_id)
        if existing:
            return existing

        extracted = ExtractedTender.model_validate(document.get("extracted") or {})
        tender = self.saved.create(
            {
                "company_id": company_id,
                "title": document["title"],
                "authority": extracted.authority,
                "reference_number": extracted.reference_number,
                "deadline": _parse_iso(extracted.deadline),
                "status": status,
                "source_url": document["source_url"],
                "source_type": document.get("source_type"),
                "source_retrieved_at": document.get("retrieved_at"),
                "description": document.get("snippet"),
                "discovered_tender_id": tender_id,
                "discovery_extracted": extracted.model_dump(),
            }
        )
        self.tenders.set_status(tender_id, company_id, "saved")
        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="tender.saved",
            entity_type="tender",
            entity_id=tender["id"],
            metadata={"title": tender["title"], "source_url": tender["source_url"]},
        )
        try:
            from app.services.workflow import WorkflowService

            WorkflowService(self.db).capture_snapshot(
                tender_id=tender["id"], company_id=company_id, user_id=user_id
            )
        except Exception:  # noqa: BLE001 - saving must not fail after the write
            logger.exception("Could not capture the first snapshot for %s", tender["id"])
        return tender
