# Implementation phases

Each phase is committed separately. A phase is complete only when its acceptance checks are verified.

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Repository assessment, architecture, folder structure, env template, data contracts, test strategy, ordered plan | Complete |
| 1 | React/Vite app, FastAPI, MongoDB, auth, onboarding, company profile, uploads, English/Hindi, responsive dashboard | Complete |
| 2 | Real TinyFish discovery and retrieval, tender ingestion, document collection, deduplication | Complete for discovery, retrieval, ingestion and deduplication |
| 3 | Tender PDFs, page-level text extraction, cited requirements, deterministic citation validation, document/requirement UI | Complete, including an English OCR fallback for scanned pages |
| 4 | Deterministic suitability score, eligibility, evidence matching, checklist, legal clauses | Complete |
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

Known limitation: TinyFish fetch returns page text without hyperlinks and several official portals block automated retrieval (`blocked`). Listing pages are therefore the main route to individual notices, and a run can legitimately return no open tenders. Phase 3 added upload-first document collection and PDF text extraction on top of saved tenders.

## Phase 3 exit criteria

- Tender PDFs are acquired upload-first, with an opportunistic direct download only when a public PDF URL is supplied. Downloads re-validate redirects, reject private/reserved hosts, cap size, require `%PDF` magic bytes and record a reason (`http_403`, `not_pdf`, `too_large`, `timeout`, `network_error`) instead of pretending a document was collected.
- The same PDF (SHA-256) is stored once per tender. Bytes live under `storage/companies/{company_id}/tenders/{tender_id}/`; metadata, page rows and requirements are company-scoped.
- PyMuPDF extracts text page by page and stores the viewer page index plus the printed page label. Pages without a text layer are OCR'd with local English Tesseract within configured page/time bounds. OCR text is stored with `text_source: ocr` and shown with a visual-review warning. A PDF that still has no readable text is stored as `no_text_layer` and cannot be sent to the AI.
- Document status is one of `extracted`, `no_text_layer` or `failed`, with encrypted/corrupt PDFs reported honestly.
- AI extraction is user-triggered per document, not automatic. Groq is used through a provider abstraction (`AI_PROVIDER=groq`); Gemini remains supported by the same interface.
- AI output is treated as untrusted: each item is validated with Pydantic, each requirement needs a verbatim excerpt and a cited page, and the excerpt must be found on that page after whitespace/typography normalisation. Failures are stored as `unverified` with a reason; they are never silently dropped or presented as verified.
- Requirements keep document ID, viewer page, printed page, clause/form reference, verbatim excerpt, interpretation, mandatory flag, source URL and retrieval provenance, model and prompt version.
- Re-running extraction is idempotent (duplicates are skipped); `replace=true` replaces only AI-origin requirements for that document.
- A human can mark a requirement `verified`, `needs_review` or `rejected`; changes are audited.
- The tender workspace has working **Documents** and **Requirements** tabs with page viewing, filters, verification badges, OCR badges/warnings, honest empty/blocked/scanned states and English/Hindi strings.
- A requirement whose excerpt is found only in OCR text is stored as `needs_review`, not `verified`, so a human compares it with the page image.

Phase 3 verification on 2026-10-20: backend `pytest` 68 passed; frontend `npm test` 16 passed; `npm run build` succeeded. A clearly labelled synthetic 8-page RFP (`scripts/make-sample-tender.py`) was processed end to end: PyMuPDF extracted 8/8 text pages, Groq (`openai/gpt-oss-120b`) extracted 33 requirements across 3 chunks, and all 33 excerpts were found verbatim on their cited pages. The browser review covered the sample badge, documents panel, extracted-page viewer, requirements summary/filters, verbatim excerpts and the source-page modal. Atlas migration copied the demo company's records to MongoDB Atlas and the app logged in and served the same data against Atlas.

Known limitations: OCR supports English only; Tesseract must be installed and is bounded per document (`OCR_MAX_PAGES`, 40; `OCR_TIMEOUT_SECONDS`, 45); direct downloads are best-effort and portals may block them; AI extraction runs synchronously and is capped per request (`AI_EXTRACTION_MAX_CHUNKS`, 12; `AI_EXTRACTION_MAX_PAGES`, 80).

## Authentication hardening

- New accounts must verify their email with a 6-digit code sent through Gmail SMTP before receiving a session.
- Verified accounts can require an email code after password login. Codes are 6 digits, HMAC-hashed at rest, single-use, expire after 10 minutes, and are rate-limited (`OTP_RESEND_COOLDOWN_SECONDS`, 60; `OTP_MAX_SENDS_PER_HOUR`, 5; `OTP_MAX_ATTEMPTS`, 5).
- Unknown account emails receive a generic response. Codes are never logged or returned by the API.
- Existing accounts without the new fields are treated as already verified and password-only, so the demo account keeps working. A verified user can enable or disable email sign-in in **Settings > Security** by confirming the current password.
- Live signup requires `SMTP_APP_PASSWORD` to contain a Google App Password for `bidkaroindia@gmail.com`; otherwise the API returns an honest `503`. Tests use a fake email service and never contact Gmail.

## Phase 4 exit criteria

- The suitability score is computed only in Python from fixed weights (profile fit 25%, citation verification 20%, confirmed mandatory evidence coverage 40%, tender document readiness 15%) and shows every dimension, weight, contribution and reason.
- Mandatory eligibility is separate from the soft score and uses only `Pass` / `Fail` / `Unknown`.
- `Pass` requires a verified requirement citation and human-confirmed, non-expired company evidence. Missing evidence is never a pass. `Fail` requires a confirmed contradicting decision. Everything else stays `Unknown`.
- Evidence candidates are deterministic suggestions only. The human decision is one of `confirmed`, `contradicted` or `rejected`, stored once per requirement with note, actor and audit entry. Rejected or expired documents cannot pass.
- Checklist tasks are generated from tender-specific requirements (mandatory, submission, compliance or form-referenced). Each task carries action, acceptance criteria, evidence check, issuer/signatory, deadline/trigger, consequence only when cited, and document/page/clause provenance. Regeneration is idempotent and preserves human status/owner.
- Legal and contract obligations are shown with their citations and labelled as a summary, not legal advice.
- All assessment, evidence, checklist and legal endpoints are company-scoped.

Phase 4 verification on 2026-10-20: backend `pytest` 81 passed; frontend `npm test` 19 passed; `npm run build` succeeded. Live checks against the saved synthetic tender returned a deterministic score of 35 (weak/insufficient data), 18 mandatory eligibility items all correctly `Unknown`, 11 cited legal/contract obligations, and 33 tender-specific checklist tasks. The demo account stayed password-only with email treated as verified. A live registration attempt without `SMTP_APP_PASSWORD` returned the documented `503` and did not fabricate an email.

Known limitations: Phase 4 scoring judges fit and compliance readiness, not legal eligibility. Evidence matching is token/type based and only as good as the company document metadata and the human decisions. Checklist generation does not invent owners or consequences. Phase 5 change tracking, snapshots, reminders and calendar export are not implemented.

## Later-phase guardrails

- Phase 2 is not complete with mocked TinyFish responses.
- Phase 3 must reject or flag requirements whose page/excerpt cannot be validated.
- Phase 4 must compute scores in Python and keep mandatory eligibility independent.
- Phase 5 must compare real stored versions; no fixed simulated change messages.
- Phase 6 must list unimplemented capabilities honestly.
