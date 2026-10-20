# Architecture

## Shape

BidKaro is a modular monolith.

```text
React SPA (Vite)
   |
   | JSON over /api, JWT bearer token
   v
FastAPI routes
   -> services (business rules)
      -> repositories (MongoDB access)
      -> integrations (TinyFish, AI providers, storage)
         -> MongoDB + local file storage
```

Routes validate input and enforce authentication. Services own business rules. Repositories own queries and indexes. Integrations are replaceable and never leak provider-specific shapes into the API contract.

## Backend modules

| Module | Responsibility |
| --- | --- |
| `core` | Settings, MongoDB lifecycle, security primitives, dependencies |
| `models` | Pydantic request/response contracts and shared enums |
| `repositories` | Collection access, indexes, tenant-scoped queries |
| `services` | Auth, company, documents, tender documents/PDF extraction, requirements, dashboard, audit, storage |
| `api/routes` | HTTP endpoints grouped by domain |
| `integrations` | TinyFish, Groq and Gemini adapters |
| `services/pdf_extraction.py` | Deterministic PyMuPDF page text and printed-label extraction |

Planned domain modules mirror the product workflow: tenders, requirements, evidence matching, scoring, eligibility, checklists, legal clauses, changes, tasks, calendar, and post-award obligations.

## Tenant isolation

Every authenticated user belongs to exactly one company for the initial release.

- A JWT contains only the user ID.
- The current user is loaded on each request; the company ID comes from the user record.
- Every company-owned query includes `company_id`.
- Every company-owned resource is fetched with both its ID and the caller's `company_id`.
- File downloads are authenticated endpoints; storage paths are never served statically.

This is enforced in repositories and endpoints, not just in the UI.

## Source traceability

The central invariant is that tender-specific requirements retain provenance. The `requirements` collection stores:

- stable requirement ID, tender ID and source document ID;
- source document name/type, URL when one exists, and retrieval timestamp on the document;
- viewer page index and printed page label;
- clause and form reference when the source states one;
- verbatim excerpt plus a separately labelled interpretation;
- mandatory flag (`yes` / `no` / `unknown`);
- verification status (`verified`, `unverified`, `needs_review`, `rejected`) and a reason for failures;
- AI origin, model and prompt version;
- human-review changes, which are also audited.

A requirement is stored as `verified` only when deterministic code finds its normalized excerpt on the cited page. A requirement without a valid source is never presented as verified. The AI only proposes extraction candidates.

Tender document bytes are validated (PDF signature, size), deduplicated by SHA-256 per tender, and stored outside the database.

## Deterministic versus AI

Deterministic Python code owns:

- scoring arithmetic, weights, evidence coverage and threshold checks;
- mandatory eligibility evaluation (`Pass` / `Fail` / `Unknown`);
- date normalization and timezone handling;
- deduplication, status transitions and schema validation;
- citation/page-reference validation.

AI may propose extracted fields, requirements, clause interpretations and concise explanations. AI output is parsed and validated against Pydantic schemas and is never treated as factual without source validation.

## Storage

- MongoDB stores structured records, workflow state and file metadata.
- Local disk stores uploaded bytes in development under `STORAGE_DIR/companies/{company_id}/{uuid}{ext}` for the evidence library and `STORAGE_DIR/companies/{company_id}/tenders/{tender_id}/{uuid}.pdf` for tender PDFs.
- Filenames are generated UUIDs; the original name is metadata only.
- File type and size are validated before writing.
- Direct downloads reject private/reserved hosts, re-validate redirects, enforce a size cap and require `%PDF` magic bytes.
- The storage layer is isolated so object storage can replace it later.

## API conventions

- Base path: `/api`.
- JSON errors use FastAPI's `{"detail": ...}` shape.
- Auth: `Authorization: Bearer <JWT>`.
- IDs are stable UUID hex strings.
- Timestamps are timezone-aware UTC datetimes.
- Pagination uses `limit` and `offset` where collections can grow.
- The frontend consumes the same Pydantic contracts exposed in OpenAPI.

## Frontend

- React Router owns real routes; there is no static-page fallback.
- `AuthContext` restores the session from a stored token and redirects unauthenticated users.
- `i18next` loads external translation dictionaries for English and Hindi.
- Layout components provide the persistent sidebar, top bar and mobile drawer.
- UI primitives (`Button`, `Input`, `Card`, `Dialog`, etc.) keep spacing, focus states and status colors consistent.
- Business rules such as eligibility and scoring are rendered from API values, never recomputed differently in the browser.

## Security baseline

- Passwords are hashed with bcrypt.
- JWTs are signed with a server-side secret and expire.
- CORS is restricted to configured origins.
- Uploads are type/size validated and downloaded only through authorized routes.
- Secrets live in environment variables and never in frontend bundles.
- Retrieved tender content is untrusted input; prompt construction must delimit it and must never let it change system rules.
