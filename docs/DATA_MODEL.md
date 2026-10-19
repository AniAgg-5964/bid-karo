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
| `created_at`, `updated_at` | datetime | |

Indexes: unique `email`, `company_id`.

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

## Planned Phase 2-5 collections

The product specification defines these entities. They will be implemented with explicit validation and indexes as each phase lands.

| Collection | Purpose |
| --- | --- |
| `tenders` | tender metadata, source URL, retrieval time, status, current version |
| `tender_documents` | collected files, document type, URL, version, collection status |
| `requirements` | cited tender requirements, applicability, verification state |
| `evidence_matches` | requirement-to-company-document matches and gaps |
| `fit_assessments` | deterministic score, dimension breakdown, coverage, eligibility results |
| `checklist_tasks` | tender-specific actions, owners, statuses, deadlines, citations |
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
requirement 1---* evidence_matches *---1 company_document
tender  1---* fit_assessments
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
