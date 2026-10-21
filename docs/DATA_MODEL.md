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
| `reminder_email_enabled` | bool | opt-in for the cron-able reminder email job |
| `reminder_lead_days` | int[] | deadline lead days, default `[7, 3, 1]` |
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
Tender-specific actions with `company_id`, `tender_id`, `requirement_id`, `title`, `category`, `phase` (`pre_award` or `post_award`), `trigger_type`, `action`, `acceptance_criteria`, `evidence_check`, `issuer`, `signatory`, `deadline_text`, `trigger`, `consequence`, `source_document_title`, `page_index`, `printed_page`, `clause_reference`, `excerpt`, `source_url`, `source_retrieved_at`, `status`, `owner`, `due_at`, timestamps.

Tasks created before Phase 5 have no `phase`; queries treat them as `pre_award` via an `$or` condition, so no destructive migration is needed.

Indexes: `(company_id, due_at)`, `(company_id, tender_id, requirement_id)`.

## Phase 7 collections

### `jobs`

One row per queued piece of work, with its steps. Fields: `company_id`, `kind` (`package_ingest`, `tender_analysis`, `legal_research`), `status` (`queued`, `running`, `done`, `failed`), `tender_id`, `document_id`, `payload`, `steps` (each with `key`, `label`, `status` (`pending`, `running`, `done`, `failed`, `skipped`), `started_at`, `finished_at`, `error`, `summary`), `error`, `started_at`, `finished_at`, timestamps.

A step that has no implementation records `skipped` with "This step is not available yet." A step that raises records `failed` with the error and the job fails. Jobs are scoped to a company like everything else.

### Tender document packages

`tender_documents` gains `kind: package`, `is_container`, `parent_document_id`, `archive_path`, `parse_status` (`parsed`, `not_parsed`, `skipped`, `container`), `parse_reason` and `package_summary`.

A package document is the archive itself. Its `package_summary` holds what it held, what was stored and read, and what was refused with the reason:

```json
{ "total": 8, "stored": 5, "skipped": 3,
  "members": [ { "path": "NIT/BOQ Schedule.xlsx", "title": "BOQ Schedule",
                 "kind": "boq", "status": "not_parsed", "page_count": 0,
                 "document_id": "…", "stored": true, "reason": null } ],
  "skipped_files": [ { "path": "install.exe",
                       "reason": "Executables and scripts are never stored." } ] }
```

Each stored file is also a `tender_documents` row with `parent_document_id` pointing at the package, so a requirement can cite the file it came from.

## Phase 5 collections

### `tender_snapshots`

One row per captured version of a tender, not per PDF. Fields: `company_id`, `tender_id`, `source_url`, `content_hash`, `captured_at`, `source_retrieved_at`, `fields` (normalized title, authority, reference, deadline, description, source type, value, currency, location), `requirement_count` and `requirement_fingerprints` (`requirement_id`, `title`, `excerpt_key`, `verification_status`).

The hash covers the normalized fields and the requirement identity/content. Human review status is stored for explainability but is excluded from the hash and from diffs.

Index: `(company_id, tender_id, captured_at desc)`.

### `changes`

Deterministic differences between two snapshots: `company_id`, `tender_id`, `tender_title`, `field`, `old_value`, `new_value`, `summary`, `severity`, `review_status` (`pending`, `acknowledged`, `dismissed`), `from_snapshot_id`, `to_snapshot_id`, `source_url`, `detected_at`, `reviewed_at`, timestamps. The actor and action are recorded in `audit_logs`. Requirement-set changes use `field: requirements`.

Indexes: `(company_id, detected_at desc)`, `(company_id, tender_id, detected_at desc)`.

### `reminders`

Derived, deduplicated notifications: `company_id`, `reminder_key`, `type` (`deadline`, `task`, `document_expiry`), `title`, `body`, `due_at`, `href`, `tender_id`, `task_id`, `document_id`, `lead_days`, `active`, `status` (`pending`, `acknowledged`, `dismissed`, `sent`, `cancelled`), `sent_at`, `last_attempt_at`, `last_error`, `attempts`, timestamps. `lead_days` is present only for deadline reminders whose source states a deadline.

Indexes: unique `(company_id, reminder_key)`, `(company_id, status, due_at)`.

Calendar export is generated on demand as ICS; no calendar collection or OAuth token is stored.

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
tender  1---* reminders
checklist_task 1---* reminders
```

Each company-owned collection is always queried with `company_id`. Tender records may be shared candidates later, but company-specific assessments, matches, tasks and documents are isolated.

## Index strategy

- Unique index on `users.email`.
- Compound indexes beginning with `company_id` for every tenant-owned collection.
- Tender deduplication will use a stable source key plus reference number; unique indexes will be added only after deduplication rules are verified.
- Historical assessments reference the tender version/snapshot used, so past results stay explainable after a corrigendum.
- `changes` and `reminders` are queried by `company_id` first; reminders add a unique `(company_id, reminder_key)` index for idempotent generation.
