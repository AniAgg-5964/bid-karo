# Implementation phases

Each phase is committed separately. A phase is complete only when its acceptance checks are verified.

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Repository assessment, architecture, folder structure, env template, data contracts, test strategy, ordered plan | Complete |
| 1 | React/Vite app, FastAPI, MongoDB, auth, onboarding, company profile, uploads, English/Hindi, responsive dashboard | Complete |
| 2 | Real TinyFish discovery and retrieval, tender ingestion, document collection, deduplication | Complete for discovery, retrieval, ingestion and deduplication |
| 3 | Tender PDFs, page-level text extraction, cited requirements, deterministic citation validation, document/requirement UI | Complete, including an English OCR fallback for scanned pages |
| 4 | Deterministic suitability score, eligibility, evidence matching, checklist, legal clauses | Complete |
| 5 | Tasks, reminders, snapshots, change detection, calendar/export, post-award obligations | Complete |
| 6 | Integration, polish, security review, full tests, docs, demo, known limitations | Complete for a local review build; hosting is out of scope |

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

Known limitations: Phase 4 scoring judges fit and compliance readiness, not legal eligibility. Evidence matching is token/type based and only as good as the company document metadata and the human decisions. Checklist generation does not invent owners or consequences.

## Phase 5 exit criteria

- Snapshots store normalized tender fields plus requirement fingerprints and a content hash covering both. Full PDF copies are not duplicated into snapshot rows.
- Snapshot capture and source rechecks are user-triggered. A recheck fetches the recorded source URL through TinyFish, updates only fields the fetched page supports and then captures a new snapshot.
- Diffs are deterministic. Added, removed and changed tender fields are reviewable, as are requirement-set changes (a re-extraction that adds, removes or rewrites a stored requirement). Human review status is excluded so approving a requirement is not reported as a source change.
- A failed source fetch never fabricates a deletion or a change. The API returns the actual fetch error and the tender keeps its previous snapshot.
- Every detected change records old value, new value, detected time and source URL, and can be `pending`, `acknowledged` or `dismissed`. Reviews are audited.
- Reminders are generated deterministically from tender deadlines and dated checklist tasks, deduplicated by a stable key, and preserve human acknowledgement unless the underlying due date changes. A changed deadline re-opens the reminder.
- Reminders are in-app. Email delivery is a separate cron-able script (`scripts/send-reminders.py`) using the existing Gmail SMTP configuration. It defaults to a dry run, can be run with `--apply`, and exits non-zero with an honest message when `SMTP_APP_PASSWORD` is missing.
- Calendar export is ICS only, authenticated and tenant-scoped. Date-only deadlines are emitted as all-day events. There is no Google Calendar OAuth.
- Post-award obligations are generated only from cited performance/contract requirements. They keep document, page, clause, excerpt, source URL and retrieval time. Pre-award checklist tasks and post-award obligations are separate phases; tasks created before this phase are treated as `pre_award` without a destructive migration.
- The workspace exposes a Changes tab per tender, a global Changes page, a Reminders page, a post-award tab, phase badges on the checklist and ICS export controls in English and Hindi.

Phase 5 verification on 2026-10-20: backend `pytest` 92 passed; frontend `npm test` 19 passed; `npm run build` succeeded. The seeded synthetic tender returns 21 verified, source-cited requirements, 15 pre-award tasks, 5 cited post-award obligations, 6 active reminders and a baseline snapshot. Its deterministic assessment is score 74 / moderate with eligibility `unknown` (6 pass, 1 unknown, 0 fail). Both ICS endpoints returned `200` with parseable calendars. A live TinyFish recheck of a real saved tender created a new snapshot and three reviewable field changes. `scripts/send-reminders.py` listed due work in dry-run mode and, with no `SMTP_APP_PASSWORD`, exited with code 2 without claiming an email was sent. Tenant-isolation tests cover changes, snapshots, obligations, ICS and reminder review.

Known limitations: rechecks are manual; there is no background polling. A source recheck updates tender fields but does not re-run AI requirement extraction, so requirement-level changes appear only after a deliberate re-extraction. Change review does not yet auto-link a changed deadline to every affected task. Email reminders require an external scheduler and a configured Google App Password. Atlas DNS was unavailable during this phase, so live verification used local MongoDB.

## Discovery rework (Phase 5 follow-up, verified 2026-10-20)

A live run had been listing zero tenders even though the search results already contained open, profile-matching notices. The causes were in the reading rules, not in the search:

- a category page's title made the whole page a "listing", so the individual notice inside the search result was never read;
- table rows without column headings were skipped, although they carry the reference and the closing date;
- a page that stated a closing date was still treated as a listing when it also carried a small table;
- the relevance gate needed two of three profile categories, so a road-construction tender outside the declared state scored below the line and was dropped;
- a notice with no closing date was dropped silently.

The rules now are:

1. A tender is one piece of work with a closing date that is still in the future. Expired notices are never shown.
2. The closing date is read from a closing/submission word. A date labelled publish/open is never used as the closing date, and in an unlabelled row the later date is the closing date.
3. A notice inside a search result is a tender even when the page is a category page (`extracted_from: search_result`); a notice inside a table row is a tender (`extracted_from: listing_table`), and headerless tables are read positionally.
4. The work must match the company's services, sectors or keywords, matched as plain text with deterministic variants (plural form, "B of A" word order). The region only decides the order. A bare keyword needs a region match as well.
5. Notices outside India are not listed.
6. Every candidate is counted with the reason it was not listed, and the Discover page shows those counts.

Verification on 2026-10-20: backend `pytest` 106 passed (14 new discovery-rule tests); frontend `npm test` 22 passed; `npm run build` succeeded. A live run with the seeded company profile returned 12 queries, 116 search hits, 98 unique candidates, 22 tender rows read out of listing tables and **5 listed tenders with real work names, references and future closing dates** (previously 0). The same run reported 16 candidates that did not match the work types, 14 index pages, 3 pages that named no work, 1 closed tender, 1 notice without a closing date and 5 pages that could not be read. "Sources to check" keeps the aggregators and now types every entry as an official portal, a government body or a third-party aggregator.

## Phase 6 exit criteria

- Full backend and frontend suites pass and the production frontend build succeeds.
- English and Hindi cover every referenced UI key; missing-key output is not shipped.
- Security review covers tenant scoping, unauthenticated access, input validation, response headers and honest error states. No secrets are committed.
- Documentation reflects the implemented system, including the local-only demo path and remaining limitations.
- A deterministic demo seed uses only the clearly labelled synthetic tender and synthetic evidence; it never presents sample data as an official tender.
- A captioned walkthrough is recorded for local review, with narration where local text-to-speech is available and a captioned silent video otherwise.
- Hosting, custom domains, paid email infrastructure and a production scheduler remain out of scope.

Phase 6 verification on 2026-10-20: backend `pytest` 92 passed; frontend `npm test` 22 passed; `npm run build` succeeded. A key-coverage script found zero missing English or Hindi keys among referenced `t()` keys. Conservative security headers were added and tested. The manual browser pass covered login, dashboard, tender overview, Requirements, Documents, Suitability, Eligibility, Checklist, Legal, Changes, Tasks, Post-award, Reminders, Settings and both ICS downloads. Demo steps and video notes live in `demo/README.md`.

Known limitations: the review build is local only. There is no hosting, no background scheduler, no Google Calendar OAuth, no live OTP or reminder email without `SMTP_APP_PASSWORD`, and no claim of legal eligibility or autonomous bid submission.

## Phase 7 groundwork: tender packages and the agent spine (verified 2026-10-21)

Two things a tender actually arrives with were missing, and the agent work needed a spine to sit on.

**Tender packages.** A tender is usually published as a ZIP. `services/package_extraction.py` reads such an archive under fixed limits — path traversal refused, per-member size, total expanded size, compression ratio, member count, one level of nesting, executables and scripts never stored — and every refused member is reported with its reason. The archive is kept as a container document and each stored file becomes its own document with its parent and its path inside the archive, so a requirement can cite the file it came from. PDFs are read as before, an image becomes a one-page OCR document, and any other format is stored and marked "not parsed" instead of being silently dropped.

**The agent spine.** `services/agents/gate.py` is the deterministic gate, with no model in it: the quote rule set checks a quote against the page it was cited from, and the grounding rule set checks that a recommendation rests only on clauses that passed the gate and states no figure that is not already in those clauses or in the stored tender record. A failed check keeps the item and its reason. `services/job_runner.py` and the `jobs` collection run the analysis pipeline (`requirements`, `recommendations`, `verification`, `legal_research`) as steps with visible state; a step with no implementation reports "not available yet" and a step that raises fails the job with the error. The requirement extraction moved onto that pipeline, so the tender page can ask for an analysis and watch it.

Verification on 2026-10-21: backend `pytest` 132 passed (9 package tests, 11 gate tests, 6 job tests), frontend `npm test` 22 passed, `npm run build` succeeded. A live package upload of a portal-style archive (RFP, BOQ spreadsheet, scanned notice image, CAD drawing, corrigendum, nested archive, executable, path-traversal entry) stored 5 files and refused 3 with their reasons; the analysis job read 2 documents and produced 24 cited requirements, and the three later steps reported "not available yet".

## Later-phase guardrails

- Phase 2 is not complete with mocked TinyFish responses.
- Phase 3 must reject or flag requirements whose page/excerpt cannot be validated.
- Phase 4 must compute scores in Python and keep mandatory eligibility independent.
- Phase 5 must compare real stored versions; no fixed simulated change messages.
- Phase 6 must list unimplemented capabilities honestly.
