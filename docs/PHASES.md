# Implementation phases

Each phase is committed separately. A phase is complete only when its acceptance checks are verified.

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Repository assessment, architecture, folder structure, env template, data contracts, test strategy, ordered plan | Complete |
| 1 | React/Vite app, FastAPI, MongoDB, auth, onboarding, company profile, uploads, English/Hindi, responsive dashboard | In progress |
| 2 | Real TinyFish discovery and retrieval, tender ingestion, document collection, deduplication | Not started |
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

## Later-phase guardrails

- Phase 2 is not complete with mocked TinyFish responses.
- Phase 3 must reject or flag requirements whose page/excerpt cannot be validated.
- Phase 4 must compute scores in Python and keep mandatory eligibility independent.
- Phase 5 must compare real stored versions; no fixed simulated change messages.
- Phase 6 must list unimplemented capabilities honestly.
