# AGENTS.md

## Repository state
- Phases 0, 1 and 2 are implemented and committed. The workspace contains `backend/` (FastAPI) and `frontend/` (React + Vite), plus `docs/`, `scripts/`, and git-ignored `.env`, storage and local MongoDB data.
- Phase 2 is live tender discovery: TinyFish search/fetch, deterministic dedupe and relevance, provenance, save/dismiss. Tender attachment collection and PDF extraction are Phase 3.
- Exact commands (run from the repo root):
  - Backend tests: `cd backend; .\.venv\Scripts\python.exe -m pytest` (uses `mongomock`; no live MongoDB needed).
  - Backend dev server: `cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000` (API docs at `/docs`).
  - Frontend dev server: `cd frontend; npm run dev` (port 5173, proxies `/api` to `http://localhost:8000`).
  - Frontend unit tests: `cd frontend; npm test` (Vitest + Testing Library).
  - Frontend build: `cd frontend; npm run build`.
  - Local MongoDB: `.\scripts\start-mongo.ps1` (data in `.data/mongo`, listens on `localhost:27017`).
- Local environment: copy `.env.example` to `.env` and set a real `JWT_SECRET`. `.env` files are git-ignored; never commit secrets or connection strings.
- The official product spec lives outside the repo as `BidPilot_AI_Project_Workflow_and_Execution_Plan.docx` (developer Downloads). It is not tracked; treat the phase plan in `docs/PHASES.md` and this file as the in-repo contract.

## Product context
BidPilot AI is an AI-assisted tender discovery, eligibility, and compliance workflow. The planned MVP proves one official tender source end to end: discover/fetch with TinyFish, collect documents, extract source-cited requirements, compare them against a company profile and evidence library, then produce a fit report and compliance checklist.

## Non-negotiable domain rules
- Every requirement shown to a user needs source document, page (viewer and printed page if they differ), clause/form reference when available, verbatim excerpt, and source URL plus retrieval time. If it cannot be verified, mark it Unverified / partial / conflicting; never fabricate citations, requirements, authorities, deadlines, or consequences.
- Keep mandatory eligibility (`Pass` / `Fail` / `Unknown`) separate from the soft fit score. Unknown or missing evidence is never a pass, and a high score must not hide a failed mandatory criterion.
- Checklist items must be tender-specific: exact document/action, acceptance criteria, issuer/signatory, evidence checks, deadline or trigger, and consequence only when the source states it. No generic filler such as "check legal requirements".
- Do not assume standard requirements (notarization, stamp paper, affidavit, licence, validity period); extract each from the actual tender.
- TinyFish is the required web discovery/extraction integration and should do real work on a real source. Manual PDF upload is only a fallback for blocked sources.
- Use deterministic code for scoring, date normalization, deduplication, schema validation, and citation checks. Treat model output as untrusted until validated.
- The product supports decisions; it must not claim legal eligibility or submit bids autonomously.

## Implemented shape
Main orchestrator plus Discovery (TinyFish), Extraction, Analysis, Compliance, and Monitoring components, backed by deterministic validation and persistence. Persist tenders, documents, requirements, evidence matches, checklist tasks, and change snapshots with provenance. Built as a modular monolith (`routes -> services -> repositories -> MongoDB`) with company-scoped queries.

- Discovery: `app/integrations/tinyfish.py` (REST `GET /v1/search`, `POST /v1/fetch`, header `X-API-Key`), `services/discovery_service.py` (query building, prequalify, batched fetch, store, qualify), `services/tender_extraction.py` (deterministic fields, source type, dedupe, listing detection, listing-table rows), `services/relevance.py` (profile fit with reasons), `repositories/discovery.py`, routes under `/api/discovery` (`status`, `run`, `runs`, `sources`, `tenders`, `tenders/{id}`, `save`, `dismiss`).
- Config knobs: `TINYFISH_API_KEY`, `TINYFISH_BASE_URL`, `DISCOVERY_MAX_CANDIDATES` (20), `DISCOVERY_FETCH_LIMIT` (12, capped at 10 per fetch), `DISCOVERY_MIN_SCORE` (0.3), `DISCOVERY_CACHE_HOURS` (24).
- Discovery rules: a run needs at least one sector/product/keyword in the company profile (else 422); a missing key returns 503. Only individual, still-open tenders are listed: a deadline or reference must be extracted, index/award pages are excluded, and past deadlines are dropped. Portal/index pages are stored, shown separately (`GET /api/discovery/sources`) and never listed as tenders. Dated tables on listing pages are parsed into individual tenders (`extracted_from: listing_table`). Social hosts are blocked before scoring. Relevance is profile fit only, never eligibility. Date-only deadlines are anchored at noon UTC so the calendar day survives IST display.
- Analysis, compliance, scoring and monitoring remain Phase 3-5 work and must stay honest about being unavailable until then.

## Open decisions
Stack, frontend language (JavaScript, not TypeScript), database, web-automation vendor (TinyFish) and the AI provider (Groq, `llama-3.3-70b-versatile`, configurable through `AI_PROVIDER`) are decided and locked. Still open: the first officially prioritised tender source beyond TinyFish's general web results, calendar integration, and hosting. Phase 2 discovery is implemented and verified against the live API; confirm Phase 3 scope (PDF extraction, AI requirement extraction) with the user before starting it.
