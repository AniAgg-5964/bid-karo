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

MAX_QUERIES = 6
FETCH_BATCH = 10


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
        terms = company_terms(company)
        regions = terms["regions"]
        region = regions[0].title() if regions else "India"
        topics = terms["keywords"] + terms["capability"]

        queries: list[str] = []
        seen: set[str] = set()

        def add(query: str) -> None:
            cleaned = " ".join(query.split())
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                queries.append(cleaned)

        override = (keywords_override or "").strip()
        if override:
            add(f"{override} tender {region}")
            add(f"{override} tender India")

        for topic in topics[:2]:
            add(f"{topic} tender {region}")
            # Detail-page queries: these surface individual notices and e-tenders
            # rather than portal index pages.
            add(f"{topic} tender notice closing date {region}")
        for topic in topics:
            add(f"{topic} tender {region} last date of submission")
            if len(queries) >= MAX_QUERIES:
                break
        for topic in topics:
            add(f"{topic} tender India")
            if len(queries) >= MAX_QUERIES:
                break

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
        return sorted(
            items,
            key=lambda item: (
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
            candidate["pre_relevance"] = relevance
            scored.append((relevance.score, candidate))

        # Individual notice pages first, then official sources, then the
        # strongest profile fit. Portal roots are fetched last because they
        # rarely carry a single tender's deadline or reference.
        def order_key(item: tuple[float, dict]) -> tuple[bool, bool, bool, float]:
            score, candidate = item
            listing = extraction.is_listing_page(candidate["title"])
            return (
                extraction.is_detail_url(candidate["url"]) and not listing,
                candidate["source_type"] == "official" and not listing,
                not listing,
                score,
            )

        scored.sort(key=order_key, reverse=True)
        ordered = [candidate for _score, candidate in scored]
        stats["prequalified"] = sum(1 for score, _c in scored if score >= threshold)
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
            is_award = extraction.is_award_notice(title, candidate["snippet"])
            # A page that yields individual rows, whose title reads like an index,
            # or that is mostly a dated table is a listing. It is kept for
            # provenance but never listed, and its fields are never extracted as
            # if the whole page were one tender.
            is_listing = (
                extraction.is_listing_page(title)
                or bool(rows)
                or extraction.has_many_dated_rows(text)
            )
            extracted = (
                ExtractedTender()
                if is_listing
                else extraction.extract_fields(title, candidate["snippet"], text)
            )
            relevance = score_tender(
                company,
                title=title,
                snippet=candidate["snippet"],
                text="" if is_listing else text,
                location=extracted.location,
                threshold=min_score,
            )

            values = {
                "source": "tinyfish",
                "source_type": candidate["source_type"],
                "source_url": candidate["url"],
                "site_name": candidate["site_name"],
                "title": title[:400],
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
                "content_excerpt": text[:4000] or None,
                "content_hash": extraction.content_hash(text) if text else None,
            }
            if fetch_status == "not_fetched":
                document, _created = self.tenders.ensure(company_id, key, values)
            else:
                document, _created = self.tenders.upsert(company_id, key, values)
            stored[key] = document

            for row in rows:
                child = self._store_row(company, candidate, row, now, min_score)
                stored[child["dedupe_key"]] = child
                stats["tenders_from_listings"] += 1

        unique_stored = list(stored.values())
        return unique_stored

    @staticmethod
    def _is_non_tender(item: dict) -> bool:
        return bool(item.get("is_listing_page") or item.get("is_award_notice"))

    def _qualify(
        self, stored: list[dict], min_score: float
    ) -> tuple[list[dict], list[dict], dict]:
        """Split stored candidates into listed tenders, portal sources and counts.

        A listed tender needs a profile-fit score at or above the threshold, must
        not be an index/award page, must still have a closing date in the future
        when one is known, and must carry at least a deadline or reference number.
        Everything else is either reported as a portal source or counted as
        skipped; nothing is silently promoted to a tender.
        """
        today = date.today().isoformat()
        listed: list[dict] = []
        sources: list[dict] = []
        closed = 0
        unverified = 0
        low = 0
        for item in stored:
            score = (item.get("relevance") or {}).get("score", 0)
            if self._is_non_tender(item):
                # Official portals are worth showing even at a lower profile fit.
                if item.get("source_type") == "official" or score >= min_score:
                    sources.append(item)
                continue
            if score < min_score:
                low += 1
                continue
            extracted = item.get("extracted") or {}
            deadline = extracted.get("deadline")
            if deadline and deadline < today:
                closed += 1
                continue
            if not (deadline or extracted.get("reference_number")):
                unverified += 1
                continue
            listed.append(item)

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
        }
        return listed, sources[:8], counts

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
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        return self.tenders.list_for_company(
            company_id,
            min_score=min_score,
            statuses=statuses,
            exclude_non_tender=exclude_non_tender,
            ready_only=ready_only,
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
        return tender
