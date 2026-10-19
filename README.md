# BidKaro

BidKaro is an AI-assisted tender intelligence, bid-readiness, compliance and workflow platform for businesses, starting with Indian public procurement.

The defining principle is simple: every tender-specific claim must be traceable to its source, and uncertainty must stay visible.

## Current status

- **Phase 0 — architecture and repository foundation:** complete.
- **Phase 1 — functional foundation:** complete. Register/login, company onboarding, company profile, private document library, dashboard, English/Hindi and light/dark, tenant-isolated APIs.
- Later phases are tracked in [`docs/PHASES.md`](docs/PHASES.md).

### What works now

- Real email/password auth (bcrypt + JWT); every company-scoped request is filtered by the authenticated company.
- 4-step onboarding and an editable company profile (details, capabilities, tender preferences, completeness score).
- Private evidence document library: upload (PDF/PNG/JPG, local storage), list/search/filter, download and delete.
- Dashboard metrics, priority actions, deadlines and recent activity derived from stored records only.
- Honest placeholders for later phases: discovery and assessment pages state that they are not enabled yet instead of showing fake results.
- English/Hindi and light/dark switches persist per user.

The repository started empty. The product specification is `BidPilot_AI_Project_Workflow_and_Execution_Plan.docx` (kept outside the repository by the project owner). The UI direction follows the supplied BidKaro mockup screenshots.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React 18, JavaScript, Vite, Tailwind CSS, React Router, i18next |
| Backend | Python, FastAPI, Pydantic v2 |
| Database | MongoDB via PyMongo |
| Files | Local storage in development; metadata in MongoDB |
| Web automation | TinyFish (Phase 2) |
| AI | Gemini and/or Groq through a provider abstraction (Phase 3) |

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
