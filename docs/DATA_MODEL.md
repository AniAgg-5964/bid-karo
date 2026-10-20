# Data model

MongoDB database: `bidkaro` (configurable with `MONGODB_DB`).

IDs are UUID hex strings stored in `_id`. All timestamps are UTC. Company-owned records include `company_id`.

## Phase 1 collections

### `users`

| Field | Type | Notes |
| --- | --- | --- |
| `_id` | string | UUID |
| `email` | string | unique, lowercase |
| `password_hash` | string | bcrypt |
| `full_name` | string | |
| `company_id` | string | tenant boundary |
| `role` | string | `owner` initially |
| `is_active` | bool | |
| `email_verified` | bool | new accounts; legacy accounts default to true |
| `otp_login_enabled` | bool | new accounts; legacy accounts default to false |
| `created_at`, `updated_at` | datetime | |

Indexes: unique `email`, `company_id`.

### `otp_codes`

| Field | Type | Notes |
| --- | --- | --- |
| `_id` | string | UUID |
| `email`, `purpose` | string | `verify_email` or `login` |
| `user_id` | string? | account being verified when known |
| `code_hash` | string | HMAC-SHA256 of the 6-digit code; raw code is never stored |
| `attempts` | int | failed verification count |
| `consumed_at` | datetime? | set when used or invalidated |
| `expires_at` | datetime | TTL index removes expired rows |
| `created_at` | datetime | |

Indexes: `(email, purpose, created_at)` and TTL on `expires_at`.

### `companies`

| Field | Type | Notes |
| --- | --- | --- |
| `_id` | string | UUID |
| `name` | string | display name |
| `legal_name`, `business_type`, `description` | string | profile |
| `products_services`, `sectors`, `regions`, `certifications` | string[] | profile |
| `annual_turnover`, `employee_count`, `established_year` | number | optional |
| `turnover_currency` | string | default `INR` |
| `preferences` | object | sectors, regions, keywords, value range |
| `onboarding_completed` | bool | |
| `created_at`, `updated_at` | datetime | |

Indexes: `name`; later a text index for search.

### `company_documents`

| Field | Type | Notes |
| --- | --- | --- |
| `_id` | string | UUID, also the storage filename stem |
| `company_id` | string | owner |
| `original_filename`, `stored_filename` | string | stored name is UUID-based |
| `document_type` | string | user-selected category |
| `title` | string | display title |
| `issuer`, `signatory`, `financial_year` | string | optional metadata |
| `issue_date`, `expiry_date` | date | optional |
| `project_value` | number | optional |
| `notes` | string | optional |
| `mime_type`, `size_bytes`, `sha256` | | integrity |
| `verification_status` | string | `self_declared` initially |
| `created_at`, `updated_at` | datetime | |

Indexes: `(company_id, created_at)`, `(company_id, document_type)`, `(company_id, expiry_date)`.

### `audit_logs`

| Field | Type | Notes |
| --- | --- | --- |
| `_id` | string | UUID |
| `company_id`, `actor_user_id` | string | |
| `action` | string | e.g. `document.uploaded` |
| `entity_type`, `entity_id` | string | |
| `metadata` | object | no secrets or file contents |
| `created_at` | datetime | |

Indexes: `(company_id, created_at)`, `entity_type + entity_id`.

## Phase 2 collections

### `discovered_tenders`

Company-scoped candidates from TinyFish discovery. Key fields: `dedupe_key`, `title`, `url`, `source_type` (`official`/`aggregator`), `extracted` (title, authority, reference, deadline, excerpts), `relevance` (score and reasons), `listing` (portal/index flags), `status` (`new`/`saved`/`dismissed`), `first_seen_at`, `last_seen_at`. Deduplicated per company by `dedupe_key`.

Indexes: `(company_id, dedupe_key)` unique, `(company_id, status)`, `(company_id, relevance.score)`.

### `discovery_runs`

One record per run: company, profile snapshot, queries, counts/funnel, timestamps. Indexed by `(company_id, started_at)`.

### `tenders`

Saved workspace tenders: `company_id`, `title`, `authority`, `reference_number`, `deadline` (UTC; date-only values anchored at 12:00 UTC), `status` (`saved`/`preparing`/`submitted`/`won`/`lost`/`archived`), `source_url`, `source_type`, `source_retrieved_at`, `description`, `discovered_tender_id`, optional `is_sample` for clearly labelled synthetic fixtures, `created_at`, `updated_at`.

Indexes: `(company_id, created_at)`, `(company_id, deadline)`.

## Phase 3 collections

### `tender_documents`

| Field | Type | Notes |
| --- | --- | --- |
| `_id` | string | UUID |
| `company_id`, `tender_id` | string | tenant + tender scope |
| `kind` | string | `main`, `corrigendum`, `boq`, `form`, `other` |
| `title`, `original_filename`, `stored_filename` | string | bytes stored outside MongoDB |
| `mime_type`, `size_bytes`, `sha256` | | integrity; SHA-256 dedupes per tender |
| `source` | string | `uploaded` or `downloaded` |
| `source_url` | string? | final URL for downloads |
| `retrieved_at` | datetime | upload or download time |
| `status` | string | `extracted`, `no_text_layer`, `failed` |
| `page_count`, `text_page_count`, `truncated` | | extraction outcome |
| `ocr_status` | string | `disabled`, `not_needed`, `applied`, `partial`, `failed`, `unavailable` |
| `ocr_page_count` | int | pages successfully transcribed with OCR |
| `error` | string? | e.g. password-protected or corrupt PDF |
| `created_at`, `updated_at` | datetime | |

Indexes: `(company_id, tender_id, created_at)`, unique `(company_id, tender_id, sha256)`.

### `tender_pages`

| Field | Type | Notes |
| --- | --- | --- |
| `_id` | string | UUID |
| `company_id`, `tender_id`, `document_id` | string | scope |
| `page_index` | int | 1-based viewer page |
| `printed_label` | string | PDF label from PyMuPDF |
| `text` | string | extracted text |
| `char_count` | int | |
| `has_text` | bool | false when neither text layer nor OCR produced text |
| `text_source` | string | `text_layer`, `ocr` or `empty` |

Indexes: unique `(document_id, page_index)`, `(company_id, tender_id)`.

### `requirements`

| Field | Type | Notes |
| --- | --- | --- |
| `_id` | string | UUID |
| `company_id`, `tender_id`, `document_id` | string | scope |
| `category` | string | eligibility, technical, financial, compliance, submission, performance, other |
| `title`, `obligation` | string | obligation is labelled interpretation |
| `excerpt` | string | verbatim model quote |
| `excerpt_key` | string | normalized quote for dedupe |
| `page_index`, `printed_page` | | citation |
| `text_source` | string | `text_layer`, `ocr` or `empty`; OCR-only citations start as `needs_review` |
| `clause_reference`, `form_reference` | string? | only when sourced |
| `mandatory` | string | `yes`, `no`, `unknown` |
| `deadline_text`, `consequence_text` | string? | only when sourced |
| `verification_status` | string | `verified`, `unverified`, `needs_review`, `rejected` |
| `verification_notes` | string? | rejection reason or reviewer note |
| `source_url` | string? | copied from the document when present |
| `origin`, `model`, `prompt_version` | string | provenance |
| `created_at`, `updated_at` | datetime | |

Indexes: `(company_id, tender_id, page_index)`, `(company_id, document_id)`, `(company_id, verification_status)`.

## Phase 4 collections

### `evidence_matches`

One human decision per requirement and company. Fields: `company_id`, `tender_id`, `requirement_id`, `document_id`, `status` (`confirmed`, `contradicted`, `rejected`), `note`, `decided_by`, `created_at`, `updated_at`.

Indexes: unique `(company_id, requirement_id)`, `(company_id, tender_id)`.

### `fit_assessments`

Latest deterministic snapshot per tender: `company_id`, `tender_id`, serialized score, eligibility summary and counts, `generated_at`, `created_at`. A GET recomputes from current inputs before saving, so this is an explainability snapshot, not the source of truth.

Indexes: unique `(company_id, tender_id)`.

### `checklist_tasks`

Tender-specific actions with `company_id`, `tender_id`, `requirement_id`, `title`, `category`, `action`, `acceptance_criteria`, `evidence_check`, `issuer`, `signatory`, `deadline_text`, `trigger`, `consequence`, `source_document_title`, `page_index`, `printed_page`, `clause_reference`, `excerpt`, `source_url`, `status`, `owner`, `due_at`, timestamps.

Indexes: `(company_id, due_at)`, `(company_id, tender_id, requirement_id)`.

## Planned Phase 5 collections

| Collection | Purpose |
| --- | --- |
| `tender_snapshots` | source snapshots per retrieval/version |
| `changes` | detected differences, affected requirements/tasks, review state |
| `calendar_events` | user-approved external events or exports |
| `reminders` | deduplicated deadline/expiry notifications |

## Relationships

```text
company 1---* users
company 1---* company_documents
company 1---* tenders
tender  1---* tender_documents
tender_document 1---* requirements
requirement 1---0..1 evidence_matches *---1 company_document
tender  1---1 fit_assessments
requirement 1---* checklist_tasks
tender  1---* tender_snapshots 1---* changes
checklist_task 1---* reminders / calendar_events
```

Each company-owned collection is always queried with `company_id`. Tender records may be shared candidates later, but company-specific assessments, matches, tasks and documents are isolated.

## Index strategy

- Unique index on `users.email`.
- Compound indexes beginning with `company_id` for every tenant-owned collection.
- Tender deduplication will use a stable source key plus reference number; unique indexes will be added only after deduplication rules are verified.
- Historical assessments reference the tender version/snapshot used, so past results stay explainable after a corrigendum.
