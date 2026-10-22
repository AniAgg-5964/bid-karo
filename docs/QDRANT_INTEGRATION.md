# Qdrant integration — Phase 0 repository assessment

This is the repository-specific map that the integration plan requires before
any substantial code change. Everything below was read from this repository, not
assumed.

## 1. What already exists and must be reused

| Existing piece | Where | How Qdrant uses it |
| --- | --- | --- |
| File storage and validation | `backend/app/services/storage.py` | Originals stay on disk under `storage/companies/{company}/...`. Qdrant never replaces them |
| Archive safety | `backend/app/services/package_extraction.py` | The ingestion of a tender ZIP must use these exact rules, not a second archive reader |
| PDF text, page boundaries, OCR fallback | `backend/app/services/pdf_extraction.py`, `services/ocr.py` | The passage source. `extract_pdf_pages` already returns page text with `text_source` (`text_layer` / `ocr`) |
| Page-level chunking for AI extraction | `chunk_pages` in `services/requirement_service.py` | Left alone. Retrieval needs passages *within* a page, which is a new chunker, not a rewrite of this one |
| The quote gate | `services/agents/gate.py` (`check_quote`) | A retrieved passage must still be proved against the page it came from |
| The grounding gate | `services/agents/gate.py` (`check_grounding`) | Retrieval feeds the agents; the gate still decides what is stored |
| The official-source allow-list | `services/agents/sources.py` | The legal knowledge base may only hold sources from these domains |
| Web retrieval | `integrations/tinyfish.py` | Missing or outdated legal references are still fetched from the live web |
| AI provider abstraction | `integrations/ai.py` (`AIProvider`, `build_ai_provider`) | The pattern the embedding provider must follow: a protocol, a factory, an unconfigured fallback |
| Job runner | `services/job_runner.py`, `jobs` collection | Indexing and research run as steps with visible state. No new queue |
| Audit log | `repositories/audit.py` | Indexing and retrieval actions are audited like everything else |
| Tenant scoping | `core/dependencies.py` (`get_current_user`, `get_current_company`), every repository | Retrieval filters are built from the authenticated company, never from a client-supplied id |
| Document metadata | `repositories/tender_documents.py` (`tender_documents`, `tender_pages`), `repositories/documents.py` (`company_documents`) | The payload metadata of every passage comes from these records |
| Requirements and eligibility | `repositories/tender_documents.py` (`requirements`), `services/assessment.py` | The Business Fit agent reads the stored requirements and the **existing** deterministic verdict. It never recomputes a score |
| Agents already built | `services/agents/{recommender,verifier,legal_researcher}.py` | They become retrieval-aware instead of being replaced |

## 2. What does not exist yet

| Missing | Note |
| --- | --- |
| Any embedding provider | None. `integrations/ai.py` is chat-completion only |
| Any vector store client | None. Qdrant is not a dependency |
| Passage-level chunking | `chunk_pages` groups whole pages for the AI call; retrieval needs clause-aware passages with a page and a clause reference |
| A retrieval service | The agents read the Mongo requirements directly today |
| A document index lifecycle | `tender_documents` has no index status, no content hash per version, no model stamp |
| A local Qdrant deployment | No compose file, no data directory, no start/stop script |
| A knowledge-base corpus for legal and procurement references | The legal agent reads the web per clause and stores nothing reusable |

## 3. How the data is represented today

- **Tenant boundary**: `users.company_id` is the only source of the company. Every company-owned collection is queried with `company_id` in the filter, and `get_current_company` resolves it from the authenticated user.
- **Company documents**: `company_documents` — title, type, issuer, signatory, financial year, issue/expiry dates, project value, `mime_type`, `size_bytes`, `sha256`, `verification_status` (`self_declared` / `verified` / `rejected` / `expired`). Files live in `storage/companies/{company_id}/{uuid}{ext}`.
- **Tender documents**: `tender_documents` — `kind` (`main`, `corrigendum`, `boq`, `form`, `other`, `package`), title, original filename, stored filename, mime, size, sha256, `source` (`uploaded` / `downloaded`), `source_url`, `retrieved_at`, `status` (`extracted`, `no_text_layer`, `failed`, `not_parsed`), `parse_status`, `parse_reason`, page counts, OCR counts, `is_container`, `parent_document_id`, `archive_path`, `package_summary`. Pages live in `tender_pages` with `page_index`, `printed_label`, `text`, `char_count`, `has_text`, `text_source`.
- **Requirements**: `requirements` — the cited clause: `excerpt` (verbatim), `page_index`, `printed_page`, `clause_reference`, `verification_status`, `deadline_text`, `consequence_text`, `document_id`, `source_url`, `origin`, `model`, `prompt_version`.
- **Evidence decisions**: `evidence_matches` — one human decision per requirement (`confirmed` / `contradicted` / `rejected`).

## 4. Implementation map

**Reuse unchanged**: storage, package extraction, PDF/OCR extraction, the gate, the sources allow-list, TinyFish, the AI provider pattern, the job runner, the audit log, the repositories, `assessment.py`.

**Extend**

| File | Change |
| --- | --- |
| `backend/app/core/config.py` | `QDRANT_*`, `EMBEDDING_*`, ingestion and retrieval limits |
| `backend/app/core/database.py` | New collection properties (`knowledge_documents`, `knowledge_findings`) and indexes |
| `backend/app/core/dependencies.py` | `get_embedding_provider()`, `get_vector_store()` |
| `backend/app/models/requirements.py`, `models/document.py` | Index status fields on a document |
| `backend/app/repositories/tender_documents.py` | Index-state helpers (status, chunk count, model stamp, last error) |
| `backend/app/services/analysis.py` | New pipeline steps: `index_documents`, `legal_intelligence`, `business_fit` |
| `backend/app/api/routes/analysis.py` | Routes for indexing status, retrieval and knowledge health |
| `frontend/src/**` | Indexing status, findings, requirement statuses, in English and Hindi |

**Add**

| File | Purpose |
| --- | --- |
| `backend/app/services/embeddings.py` | `EmbeddingProvider` protocol, `build_embedding_provider`, a deterministic always-available provider and an optional semantic one. The dimension comes from the provider |
| `backend/app/services/vector_store.py` | Qdrant wrapper: collection setup, upsert, filtered search, delete by document, health. Never raises into the app |
| `backend/app/services/chunking.py` | Clause-aware passage chunking with page and clause attribution, overlap and configurable size |
| `backend/app/services/document_ingestion.py` | Extract → chunk → embed → index → record status, reusing the existing extraction and the job runner |
| `backend/app/services/document_lifecycle.py` | Re-index on a new version, on a corrigendum, on a model change, and on deletion |
| `backend/app/services/retrieval.py` | The scoped, tenant-filtered retrieval service the agents call |
| `backend/app/services/citations.py` | Passage → source reference (document, page, clause, URL, retrieved at) |
| `backend/app/services/legal_intelligence.py` | The legal agent over the knowledge base, with TinyFish verification and structured findings |
| `backend/app/services/business_fit.py` | Requirement → evidence, with the deterministic comparison and the existing eligibility verdict |
| `backend/app/repositories/knowledge.py` | Mongo records for the knowledge base and the findings |
| `backend/app/api/routes/knowledge.py` | Indexing, retrieval, findings and health routes |
| `docker-compose.yml` | Qdrant for local development, with a persistent volume |
| `scripts/qdrant-dev.ps1` | Start, stop and status for Qdrant (Docker Compose, with a standalone-binary fallback) |
| `backend/tests/test_*.py` | Tests for the chunker, the embeddings, the vector store, the retrieval scoping, the ingestion and the business fit, all runnable without a server |

## 5. Environment findings and risks

1. **Python 3.14.2** in the backend virtualenv. `qdrant-client` (1.19.1), `model2vec` (0.10.0) and `numpy` (2.5.4) all resolve for this interpreter. `fastembed` resolves, but its ONNX runtime has no 3.14 wheel, so it is **not** the default embedding path here.
2. **Docker is installed (29.2.1, Compose v5.1.0) but the daemon is not running.** The Compose file is the documented path; a standalone Qdrant binary helper is provided so the stack can also run without Docker.
3. **Embedding models cost nothing but need a first download.** A semantic model is fetched once from Hugging Face (~30 MB, free). Until it is available, a deterministic provider that needs no download keeps the pipeline runnable. Which one is used must be visible in the health output and in the indexed metadata, because the dimension comes from the model, not from a constant.
4. **The scoring and eligibility rules must not move.** The Business Fit agent reads the stored requirements and the verdict that `assessment.py` already produced. It explains and cites; it does not recompute a score or decide a `Pass`.
5. **Qdrant is an index, not a source of truth.** Documents, requirements, evidence decisions, findings and eligibility stay in Mongo. A collection wipe must be recoverable by re-indexing from Mongo and the stored files.
6. **The retrieval path is the tenant-isolation risk.** The filter is built from the authenticated company, and the tests must prove that a company cannot retrieve another company's passages.
7. **Legal text is time-sensitive.** A passage in the knowledge base does not prove a rule is current. The legal agent still verifies against the live official source when currency matters.

## 6. What the plan will not do

- No rewrite of the requirement extraction, the scoring formula, the eligibility rules or the existing UI.
- No second archive reader, no second PDF extractor, no second job queue.
- No global vector search that relies on the model to filter results afterwards.
- No paid embedding API and no paid vector database.
- No claim that a passage in the index is a current legal position.
