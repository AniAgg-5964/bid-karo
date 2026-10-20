# BidKaro

BidKaro is an AI-assisted tender intelligence, bid-readiness, compliance and workflow platform for businesses, starting with Indian public procurement.

The defining principle is simple: every tender-specific claim must be traceable to its source, and uncertainty must stay visible.

## Current status

- **Phase 0 — architecture and repository foundation:** complete.
- **Phase 1 — functional foundation:** complete. Register/login, company onboarding, company profile, private document library, dashboard, English/Hindi and light/dark, tenant-isolated APIs.
- **Phase 2 — live tender discovery:** complete. Profile-driven TinyFish search and page retrieval, deterministic deduplication, relevance scoring with reasons, source provenance, save/dismiss into the workspace.
- **Phase 3 — tender documents and cited requirements:** complete. Upload-first PDF collection, PyMuPDF page text with printed labels, English Tesseract OCR for scanned pages, user-triggered Groq extraction, deterministic verbatim/page citation checks, requirement review and a Documents/Requirements workspace. OCR-derived citations are labelled and visually reviewable; OCR text alone cannot silently make a requirement verified.
- **Phase 4 — deterministic assessment:** complete. A transparent soft-fit score, mandatory eligibility kept separate, human-confirmed evidence matching, tender-specific checklist tasks and cited legal/contract obligations.
- **Phase 5 — workflow:** complete. Tender snapshots, deterministic change review, in-app reminders plus a cron-able email script, authenticated ICS export and cited post-award obligations.
- **Phase 6 — local review build:** complete for local use. Hardening, full tests, documentation, a deterministic demo seed and a captioned walkthrough. Hosting is intentionally out of scope.
- **Authentication hardening:** Gmail SMTP email verification at signup and optional 6-digit email sign-in codes for verified accounts. The existing demo account remains password-only.
- Phase details and verification records are in [`docs/PHASES.md`](docs/PHASES.md).

### What works now

- Real email/password auth (bcrypt + JWT) with Gmail SMTP verification codes; every company-scoped request is filtered by the authenticated company. Signup requires email verification, and verified accounts can require a 6-digit code after the password. Passwords and codes are never returned by the API.
- 4-step onboarding and an editable company profile (details, capabilities, tender preferences, completeness score).
- Private evidence document library: upload (PDF/PNG/JPG, local storage), list/search/filter, download and delete.
- Live tender discovery: queries built from the company profile, real TinyFish search and page fetch, official sources flagged, aggregator index pages filtered out, and each result carrying source URL, retrieval time and verbatim excerpts for every extracted field.
- Tender document workspace: attach a PDF by upload (primary) or attempt a direct public PDF download; page text and printed page labels are extracted with PyMuPDF; SHA-256 dedupe per tender. Pages without a text layer are OCR'd with local English Tesseract (bounded by page count and time), stored with `text_source: ocr`, and flagged for visual review. A PDF that still has no readable text is flagged rather than pretended to be readable.
- User-triggered requirement extraction: Groq (or Gemini) proposes requirements in JSON, Pydantic validates every item, and deterministic code stores a requirement as `verified` only when its verbatim excerpt is found on the cited page. Mismatches are stored as `unverified` with a reason; nothing is silently dropped.
- Requirement review: filter by category, verification state and mandatory flag; view the cited page text; mark requirements verified, rejected or needing review. Every review is audited.
- Deterministic suitability score: profile fit, citation verification, confirmed mandatory evidence coverage and document readiness, computed in Python with visible weights and reasons. The soft score never hides a failed or unknown mandatory gate.
- Mandatory eligibility: `Pass` / `Fail` / `Unknown` for each gating requirement. `Pass` needs a verified citation plus human-confirmed, non-expired evidence; missing or unknown evidence stays `Unknown`.
- Evidence matching: deterministic candidate suggestions from the company document library, with explicit human `confirmed` / `contradicted` / `rejected` decisions. Suggestions never auto-pass a gate.
- Tender-specific checklist: generated from mandatory, submission, compliance and form-referenced requirements. Each task carries the exact action, acceptance criteria, evidence check, issuer/signatory, deadline/trigger, cited consequence and source citation. Generation is idempotent and preserves human status and owners.
- Legal and contract obligations: extracted compliance/performance clauses with document, page and clause citations, explicitly labelled as summary, not legal advice.
- Deterministic profile-fit relevance with visible reasons; saved tenders flow into the dashboard, recent activity and the 14-day deadline metric.
- Dashboard metrics, priority actions, deadlines and recent activity derived from stored records only.
- Workflow: user-triggered source rechecks through TinyFish, versioned snapshots, deterministic field and requirement-set diffs, reviewable changes, reminders with lead days, and authenticated ICS export.
- Post-award obligations: generated only from cited performance/contract requirements, kept separate from pre-award checklist tasks.
- Honest states everywhere: discovery reports a missing API key or incomplete profile instead of showing sample tenders; scanned or OCR-read pages and blocked downloads are labelled; missing evidence is shown as Unknown; a failed recheck reports the real error without inventing a change; email reminders report missing SMTP configuration instead of claiming delivery.
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
| AI | Groq `openai/gpt-oss-120b` by default, Gemini supported, behind a provider abstraction; JSON validated with Pydantic |

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
- Optional for scanned PDFs: Tesseract 5 with English language data (see [Scanned PDFs and OCR](#scanned-pdfs-and-ocr))
- Optional for live email codes: a Gmail account with 2-Step Verification and a Google App Password

## Local setup

### 1. Environment

Copy `.env.example` to `.env` in the repository root and set a real `JWT_SECRET`.
Copy `frontend/.env.example` to `frontend/.env` if the API is not on the default URL.

### 2. Gmail SMTP verification

Signup sends a verification code and verified accounts may require a code at sign-in. The sender account is `bidkaroindia@gmail.com`.

1. Enable 2-Step Verification on the Google account.
2. Create a Google **App Password** for this app.
3. Set it in the repository `.env` (never commit it):

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=bidkaroindia@gmail.com
SMTP_APP_PASSWORD=the-16-character-app-password
SMTP_FROM_NAME=BidKaro
OTP_EXPIRE_MINUTES=10
OTP_RESEND_COOLDOWN_SECONDS=60
OTP_MAX_SENDS_PER_HOUR=5
OTP_MAX_ATTEMPTS=5
```

Codes are 6 digits, HMAC-hashed at rest, single-use, expire in 10 minutes, and are rate-limited per email/purpose. Unknown accounts receive a generic response. Without `SMTP_APP_PASSWORD`, registration returns an honest `503` instead of pretending an email was sent. Automated tests use a fake email service and never contact Gmail. The existing demo account is treated as already verified and stays password-only until you deliberately enable email sign-in in **Settings > Security**.

### 3. MongoDB

With `mongod` installed:

```powershell
.\scripts\start-mongo.ps1
```

The helper stores data in `.data/mongo` (git-ignored) and listens on `localhost:27017`.

**Local vs shared MongoDB:** the app always talks to the MongoDB server in `MONGODB_URI`, so all users of a running backend share the same database. Local `mongod` is the zero-cost development/demo server. For a hosted deployment or team access, use MongoDB Atlas or another shared MongoDB and set `MONGODB_URI` in `.env`; no application code changes are required. Never commit that URI because it contains credentials.

To copy existing local data into Atlas while keeping IDs, set `ATLAS_MONGODB_URI` in `.env` (separate from the app's `MONGODB_URI`) and run:

```powershell
.\backend\.venv\Scripts\python.exe scripts\migrate-to-atlas.py          # dry run
.\backend\.venv\Scripts\python.exe scripts\migrate-to-atlas.py --apply  # copy + verify
```

The script upserts by `_id`, verifies every source ID exists on the target, and never prints credentials. Uploaded files stay on local disk; only MongoDB records move.

### 4. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### 5. Frontend

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

TinyFish's fetch response contains page text but no hyperlinks, and several official portals block automated retrieval. A run can therefore return no open tenders for a profile on a given day; the page says so instead of padding the list.

## Scanned PDFs and OCR

English OCR is available through local Tesseract. It is used only for pages with no usable text layer.

- Install Tesseract 5 with the English language data (on Windows the default path is `C:\Program Files\Tesseract-OCR\tesseract.exe`), or set `TESSERACT_CMD`.
- Configure the bounds:

```text
OCR_ENABLED=true
OCR_LANGUAGE=eng
OCR_DPI=300
OCR_MAX_PAGES=40
OCR_TIMEOUT_SECONDS=45
TESSERACT_CMD=
```

OCR scope is deliberately English-only. Hindi/other-language OCR is not implemented. OCR text is marked `text_source: ocr`; pages show an OCR warning, and the Documents panel reports how many pages were OCR'd. A requirement whose excerpt is found only in OCR text is stored as `needs_review`, not `verified`, so a human must compare it with the page image. If Tesseract is unavailable or times out, the document is still stored with an honest `ocr_status`/error, not a fabricated text layer.

## Tender documents and requirements

Open a saved tender, then use **Documents** and **Requirements**.

- **Upload first.** Portals frequently block automated downloads, so attaching the PDF you downloaded in a browser is the primary path. A direct public PDF URL can also be attempted; the downloader rejects private hosts, re-validates redirects, caps size and requires real PDF bytes. Blocked attempts return an actionable message and are audited.
- **Page-level text.** PyMuPDF stores the viewer page number, the PDF's printed page label and the page text. A PDF without a text layer is stored as `no_text_layer`. OCR is not enabled, and the UI says so.
- **Trigger extraction yourself.** Nothing is sent to the AI automatically. `POST /api/tender-documents/{id}/extract` chunks readable pages and asks the configured provider for JSON requirements.
- **Citations are checked deterministically.** The model must return a verbatim excerpt and the page it came from. After whitespace/typography normalisation, that excerpt must appear on that page. If it does not, the requirement is stored as `unverified` with a reason; it is never shown as verified.
- **Separate interpretation from evidence.** The excerpt is shown verbatim; the plain-language obligation is labelled as interpretation.
- **Human review.** Requirements can be marked verified, rejected or needing review, and the change is audited. This is a review aid, not a legal eligibility decision.

Configure AI in `.env`:

```text
AI_PROVIDER=groq
GROQ_API_KEY=...
GROQ_MODEL=openai/gpt-oss-120b
AI_REQUEST_TIMEOUT_SECONDS=60
AI_MAX_OUTPUT_TOKENS=2000
```

Groq's previously documented `llama-3.3-70b-versatile` is no longer offered; the default was updated to `openai/gpt-oss-120b` after checking the provider's live model list. `AI_PROVIDER=gemini` with `GEMINI_API_KEY` and `GEMINI_MODEL` uses the same interface.

To create a clearly labelled synthetic sample tender for testing (8 pages, fictional authority, `SYNTHETIC SAMPLE` on every page) and attach it to the demo company:

```powershell
.\backend\.venv\Scripts\python.exe scripts\make-sample-tender.py --seed --email asha.phase1@example.com
```

The sample is flagged `is_sample` and shown with a **Synthetic sample** badge. It is not an official tender and is never presented as one.

## Deterministic assessment and legal obligations

Open a saved tender and use the **Suitability**, **Eligibility**, **Checklist** and **Legal & contract** tabs.

- **Score:** 25% profile fit, 20% citation verification, 40% confirmed mandatory evidence coverage, 15% tender document readiness. The formula is deterministic Python, and every dimension shows its weight, points and reason.
- **Eligibility:** separate from the score. Every gating item is `Pass`, `Fail` or `Unknown`. `Pass` requires both a verified source citation and human-confirmed, non-expired evidence. Missing evidence or an unverified citation stays `Unknown`. A rejected or expired document cannot pass.
- **Evidence:** the API suggests possible company documents using deterministic token/type matching. You decide: confirm, mark as contradicting, or reject. One decision is stored per requirement, with your note and audit entry. Suggestions are never treated as proof.
- **Checklist:** generated from the extracted requirements, not from a generic template. Each task keeps the exact action, acceptance criteria, evidence check, issuer/signatory, deadline/trigger, consequence (only when cited) and source document/page/clause. Re-running generation skips existing tasks, so human status and ownership are preserved.
- **Legal:** shows extracted compliance and contract obligations with citations. It is a source summary, not legal advice.

The assessment persists a snapshot in `fit_assessments`, but each GET recomputes the score from current requirements, documents and decisions so the displayed value cannot drift from its inputs.

## Workflow, reminders and calendar

- **Changes:** open a saved tender and use **Changes** to capture a baseline snapshot or recheck the recorded source through TinyFish. Snapshots store normalized tender fields and requirement fingerprints, never duplicate PDFs. Diffs are deterministic and every change can be acknowledged or dismissed; reviews are audited.
- **Rechecks do not invent data:** if TinyFish cannot fetch the source, the API returns the real error and the previous snapshot stays intact. A recheck updates tender fields; it does not run AI extraction again, so requirement-set changes appear after a deliberate re-extraction.
- **Reminders:** generated from tender deadlines and dated checklist tasks. A changed deadline re-opens a reminder that was acknowledged, dismissed or emailed. Acknowledgements are preserved while the due date is stable.
- **Email:** reminders are in-app by default. Email delivery is a cron-able script, not an in-process scheduler:

  ```powershell
  # Dry run: list due reminders without sending
  .\backend\.venv\Scripts\python.exe scripts\send-reminders.py

  # Send, only for companies that enabled email reminders in Settings
  .\backend\.venv\Scripts\python.exe scripts\send-reminders.py --apply
  ```

  Without `SMTP_APP_PASSWORD` the script exits with code 2 and sends nothing.
- **Calendar:** both `/api/tenders/{id}/calendar.ics` and `/api/calendar.ics` return authenticated, tenant-scoped ICS files. Date-only deadlines become all-day events. There is no Google Calendar OAuth.
- **Post-award:** the tender's **Post-award** tab generates obligations only from cited performance/contract requirements. Pre-award tasks and post-award obligations stay separate.

## Demo data and walkthrough

`scripts/seed-demo.py` is deterministic and idempotent. It only reseeds the clearly labelled synthetic sample tender and marks the evidence library as synthetic demo evidence:

```powershell
$env:MONGODB_URI='mongodb://localhost:27017'
$env:MONGODB_DB='bidkaro'
.\backend\.venv\Scripts\python.exe scripts\seed-demo.py --email asha.phase1@example.com
```

It produces 21 verified source-cited requirements, 15 pre-award tasks, 5 cited post-award obligations, 6 active reminders, a baseline snapshot and a deterministic assessment (score 74 / moderate, eligibility `unknown`). The demo account is `asha.phase1@example.com` with the local password used by the project owner. See [`demo/README.md`](demo/README.md) for the walkthrough script and video notes.

## Tests

```powershell
# Backend
cd backend
.\.venv\Scripts\Activate.ps1
pytest

# Frontend
cd frontend
npm test
npm run build
```

Backend tests use `mongomock` and a fake email service; they need no live MongoDB, TinyFish or Gmail account. Current local result: 92 backend tests and 22 frontend tests pass, and the production build succeeds.

## Design constraints

- The frontend is a real multi-page React application, not a static mockup.
- The backend is a modular monolith: routes -> services -> repositories -> MongoDB.
- Company data is always scoped by the authenticated company identity.
- Uploaded files are never exposed through public URLs.
- Dashboard values come from stored records, never hardcoded sample metrics.
- AI output is validated with Pydantic and deterministic checks before it is trusted.
- Hard eligibility (`Pass` / `Fail` / `Unknown`) is separate from the Bid Suitability Score. A missing or unverified mandatory item is never a pass, and a high score never hides it.
- Evidence suggestions are deterministic and never auto-pass; a human must confirm, contradict or reject.
- Checklist tasks are generated from tender requirements and keep their source citation; no generic filler.
- Reminder email delivery is external and opt-in; the app never pretends a background scheduler exists.
- Calendar integration is ICS export only; there is no Google Calendar OAuth.
- No paid service is required for local development. Tesseract is free and local; Gmail SMTP uses the project account's app password.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md)
- [`docs/PHASES.md`](docs/PHASES.md)
- [`docs/DEPENDENCIES.md`](docs/DEPENDENCIES.md)
- [`demo/README.md`](demo/README.md)
