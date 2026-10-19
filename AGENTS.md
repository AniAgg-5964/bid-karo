# AGENTS.md

## Repository state
- Phases 0 and 1 are implemented and committed. The workspace contains `backend/` (FastAPI) and `frontend/` (React + Vite), plus `docs/`, `scripts/`, and git-ignored `.env`, storage and local MongoDB data.
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
Main orchestrator plus Discovery (TinyFish), Extraction, Analysis, Compliance, and Monitoring components, backed by deterministic validation and persistence. Persist tenders, documents, requirements, evidence matches, checklist tasks, and change snapshots with provenance. Phases 0-1 are built as a modular monolith (`routes -> services -> repositories -> MongoDB`) with company-scoped queries; discovery, extraction, scoring and monitoring components land in later phases and must remain honest about being unavailable until then.

## Open decisions
Stack, frontend language (JavaScript, not TypeScript), database, and web-automation vendor (TinyFish) are decided and locked. Still open: model/provider access keys, the first official tender source, calendar integration, and hosting. Confirm with the user before Phase 2 discovery work.
