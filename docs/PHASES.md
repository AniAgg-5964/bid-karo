# Implementation phases

Each phase is committed separately. A phase is complete only when its acceptance checks are verified.

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Repository assessment, architecture, folder structure, env template, data contracts, test strategy, ordered plan | Complete |
| 1 | React/Vite app, FastAPI, MongoDB, auth, onboarding, company profile, uploads, English/Hindi, responsive dashboard | Complete |
| 2 | Real TinyFish discovery and retrieval, tender ingestion, document collection, deduplication | Complete for discovery, retrieval, ingestion and deduplication; tender attachment collection moves with PDF extraction in Phase 3 |
| 3 | PDF extraction, structured requirements, citations, validation, processing status | Not started |
| 4 | Deterministic suitability score, eligibility, evidence matching, checklist, legal clauses | Not started |
| 5 | Tasks, reminders, snapshots, change detection, calendar/export, post-award obligations | Not started |
| 6 | Integration, polish, security review, full tests, docs, demo, known limitations | Not started |

## Phase 0 exit criteria

- Repository and toolchain inspected.
- Architecture and module boundaries documented.
- Environment template contains names and placeholders only.
- Data contracts and indexes defined.
- Test strategy defined.
- No secrets or existing work overwritten.

## Phase 1 exit criteria

- Application starts with documented commands.
- A user can register, log in and complete onboarding.
- Company data persists in MongoDB and is isolated by company.
- Files upload, list, download and delete with authorization checks.
- English/Hindi and light/dark switches work and persist.
- Dashboard metrics derive from stored records; empty states are honest.
- Backend tests cover auth, tenant isolation, profile updates and file access.
- Frontend builds and its navigation/auth flow tests pass.

Phase 1 verification on 2026-10-20: backend `pytest` 14 passed; frontend `npm run build` succeeded; frontend `npm test` 4 passed; manual browser run of register -> onboarding -> dashboard -> upload/download -> company profile -> settings covered English/Hindi and light/dark with real MongoDB persistence.

Dependency hardening (2026-10-20, after Phase 1): `react-router-dom` 6 -> 7, `vite` 8, `vitest` 5; `npm audit --omit=dev` now reports 0 vulnerabilities. Tailwind 3 -> 4 migration deferred deliberately; see [`DEPENDENCIES.md`](DEPENDENCIES.md).

## Phase 2 exit criteria

- Discovery queries are built from the company profile (sectors, products/services, keywords, regions); requesting a run without profile terms returns a 422 with guidance.
- Search and page retrieval go through the live TinyFish REST API (`/v1/search`, `/v1/fetch`); a missing `TINYFISH_API_KEY` yields an honest 503, never sample data.
- Candidates are deduplicated deterministically and namespaced per company, so re-runs update instead of duplicating.
- Relevance is a deterministic Python score in [0,1] with recorded reasons; it is labelled profile fit and kept separate from mandatory eligibility.
- Only individual, still-open tenders are listed. A listed tender needs a source-backed closing date or reference number, must not be an index/portal page, must not be an award/cancellation notice, and must not already be closed.
- Portal and index pages are still stored, exposed under `GET /api/discovery/sources` and shown separately as "Sources to check", never as tenders. Pages without a closing date or reference are counted, not promoted.
- Dated tender tables on official listing pages are parsed deterministically into individual tenders (`extracted_from: listing_table`), keeping the listing URL and the verbatim table row as evidence.
- Every discovered tender keeps source URL, source type (official/aggregator), retrieval time, fetch status and verbatim excerpts for each extracted field; missing fields are shown as "not stated in source".
- A discovered tender can be saved into the company workspace (idempotent) or dismissed, and saved tenders appear on the dashboard plus the tender deadline metric.
- All discovery data is company-scoped.

Phase 2 verification on 2026-10-20: backend `pytest` 46 passed; frontend `npm test` 10 passed; `npm run build` succeeded. Live runs against TinyFish with the demo profile executed 6 profile queries, returned 55-59 search results per run and fetched 6-8 pages (2-4 blocked). Official e-procurement portals were recognised as index pages and listed under sources; a search-result page whose only deadline was already past was counted as closed; pages without a deadline or reference were counted as unverified. The tender list was therefore empty on that date, which is the honest outcome: no open, source-backed, profile-matched tender was found. The ingestion path itself is exercised by tests, including a dated listing table and a saved tender that flows to the dashboard deadline metric. English/Hindi and light/dark were re-checked on the discovery page.

Known limitation: TinyFish fetch returns page text without hyperlinks and several official portals block automated retrieval (`blocked`). Listing pages are therefore the main route to individual notices, and a run can legitimately return no open tenders. Phase 3 adds document collection and PDF extraction from saved tenders.

## Later-phase guardrails

- Phase 2 is not complete with mocked TinyFish responses.
- Phase 3 must reject or flag requirements whose page/excerpt cannot be validated.
- Phase 4 must compute scores in Python and keep mandatory eligibility independent.
- Phase 5 must compare real stored versions; no fixed simulated change messages.
- Phase 6 must list unimplemented capabilities honestly.
