# BidKaro

BidKaro is an AI-assisted tender intelligence, bid-readiness, compliance and workflow platform for businesses, starting with Indian public procurement.

The defining principle is simple: every tender-specific claim must be traceable to its source, and uncertainty must stay visible.

## Current status

- **Phase 0 — architecture and repository foundation:** complete.
- **Phase 1 — functional foundation:** complete. Register/login, company onboarding, company profile, private document library, dashboard, English/Hindi and light/dark, tenant-isolated APIs.
- **Phase 2 — live tender discovery:** complete. Profile-driven TinyFish search and page retrieval, deterministic deduplication, relevance scoring with reasons, source provenance, save/dismiss into the workspace.
- Later phases are tracked in [`docs/PHASES.md`](docs/PHASES.md).

### What works now

- Real email/password auth (bcrypt + JWT); every company-scoped request is filtered by the authenticated company.
- 4-step onboarding and an editable company profile (details, capabilities, tender preferences, completeness score).
- Private evidence document library: upload (PDF/PNG/JPG, local storage), list/search/filter, download and delete.
- Live tender discovery: queries built from the company profile, real TinyFish search and page fetch, official sources flagged, aggregator index pages filtered out, and each result carrying source URL, retrieval time and verbatim excerpts for every extracted field.
- Deterministic profile-fit relevance with visible reasons; saved tenders flow into the dashboard, recent activity and the 14-day deadline metric.
- Dashboard metrics, priority actions, deadlines and recent activity derived from stored records only.
- Honest states everywhere: discovery reports a missing API key or incomplete profile instead of showing sample tenders, and assessment pages still state that requirement extraction is not enabled yet.
- English/Hindi and light/dark switches persist per user.

The repository started empty. The product specification is `BidPilot_AI_Project_Workflow_and_Execution_Plan.docx` (kept outside the repository by the project owner). The UI direction follows the supplied BidKaro mockup screenshots.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React 18, JavaScript, Vite, Tailwind CSS, React Router, i18next |
| Backend | Python, FastAPI, Pydantic v2 |
| Database | MongoDB via PyMongo |
| Files | Local storage in development; metadata in MongoDB |
| Web automation | TinyFish REST API (`/v1/search`, `/v1/fetch`) |
| AI | Gemini and/or Groq through a provider abstraction (from Phase 3) |

## Repository layout

```text
backend/    FastAPI application, repositories, services, tests
frontend/   React SPA
docs/       Architecture, data model, phase status
scripts/    Local development helpers (MongoDB startup)
storage/    Local uploaded files (git-ignored)
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+
- MongoDB 7+ running locally on `mongodb://localhost:27017` (or set `MONGODB_URI`)

## Local setup

### 1. Environment

Copy `.env.example` to `.env` in the repository root and set a real `JWT_SECRET`.
Copy `frontend/.env.example` to `frontend/.env` if the API is not on the default URL.

### 2. MongoDB

With `mongod` installed:

```powershell
.\scripts\start-mongo.ps1
```

The helper stores data in `.data/mongo` (git-ignored) and listens on `localhost:27017`.

**Local vs shared MongoDB:** the app always talks to the MongoDB server in `MONGODB_URI`, so all users of a running backend share the same database. Local `mongod` is the zero-cost development/demo server. For a hosted deployment or team access, use MongoDB Atlas or another shared MongoDB and set `MONGODB_URI` in `.env`; no application code changes are required. Never commit that URI because it contains credentials.

### 3. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### 4. Frontend

```powershell
cd frontend
npm install
npm run dev
```

App: `http://localhost:5173`

## Tender discovery

Discovery uses the live TinyFish REST API. Configure it in `.env`:

```text
TINYFISH_API_KEY=...
TINYFISH_BASE_URL=https://agent.tinyfish.ai
DISCOVERY_MAX_CANDIDATES=20
DISCOVERY_FETCH_LIMIT=12
DISCOVERY_MIN_SCORE=0.3
DISCOVERY_CACHE_HOURS=24
```

Open **Discover tenders**, then run discovery. The backend builds queries from the company profile (sectors, products/services, keywords, regions), searches TinyFish, pre-qualifies candidates deterministically, fetches pages in batches of up to 10, extracts fields with verbatim excerpts, and stores everything per company.

What the page promises:

- Results are live web results, never seeded samples. Without a key the API returns 503 and the page says so.
- Only individual, still-open tenders are listed: a row must carry a source-backed closing date or reference number, must not be an index page, an award notice or an already-closed tender.
- Portal and index pages are stored and shown separately as **Sources to check**, never as tenders.
- Dated tender tables on listing pages are parsed into individual tenders, with the listing URL and the verbatim table row kept as evidence.
- Relevance is a deterministic profile-fit score in `[0,1]` with recorded reasons. It is not eligibility and is not a Bid Suitability Score.
- Missing fields are labelled "not stated in source"; a field is only shown when the retrieved text supports it.
- Retrieval failures (for example `bot_blocked`) are labelled instead of hidden.

Run statistics separate the funnel: candidates searched, unique sources, pages read, pages not retrievable, non-tender pages, closed tenders hidden, pages without tender details, tenders read from listing tables, and tenders listed.

TinyFish's fetch response contains page text but no hyperlinks, and several official portals block automated retrieval. A run can therefore return no open tenders for a profile on a given day; the page says so instead of padding the list. Tender attachments (the tender PDFs themselves) are collected in Phase 3 together with PDF extraction.

## Tests

```powershell
# Backend
cd backend
.\.venv\Scripts\Activate.ps1
pytest

# Frontend
cd frontend
npm test
```

## Design constraints

- The frontend is a real multi-page React application, not a static mockup.
- The backend is a modular monolith: routes -> services -> repositories -> MongoDB.
- Company data is always scoped by the authenticated company identity.
- Uploaded files are never exposed through public URLs.
- Dashboard values come from stored records, never hardcoded sample metrics.
- AI output is validated with Pydantic and deterministic checks before it is trusted.
- Hard eligibility (`Pass` / `Fail` / `Unknown`) is separate from the Bid Suitability Score.
- No paid service is required for local development.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md)
- [`docs/PHASES.md`](docs/PHASES.md)
- [`docs/DEPENDENCIES.md`](docs/DEPENDENCIES.md)
