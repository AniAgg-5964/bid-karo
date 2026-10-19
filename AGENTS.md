# AGENTS.md

## Repository state
- No application code, package manifest, build/test/lint/typecheck/CI config, or OpenCode config is tracked yet. Do not assume or invent commands (`npm test`, `pytest`, etc.); add the exact commands here when tooling lands.
- The product spec currently lives outside the repo as `BidPilot_AI_Project_Workflow_and_Execution_Plan.docx` (developer Downloads). It is not tracked; ask for it or commit it under `docs/` before relying on it.

## Product context
BidPilot AI is an AI-assisted tender discovery, eligibility, and compliance workflow. The planned MVP proves one official tender source end to end: discover/fetch with TinyFish, collect documents, extract source-cited requirements, compare them against a company profile and evidence library, then produce a fit report and compliance checklist.

## Non-negotiable domain rules
- Every requirement shown to a user needs source document, page (viewer and printed page if they differ), clause/form reference when available, verbatim excerpt, and source URL plus retrieval time. If it cannot be verified, mark it Unverified / partial / conflicting; never fabricate citations, requirements, authorities, deadlines, or consequences.
- Keep mandatory eligibility (`Pass` / `Fail` / `Unknown`) separate from the soft fit score. Unknown or missing evidence is never a pass, and a high score must not hide a failed mandatory criterion.
- Checklist items must be tender-specific: exact document/action, acceptance criteria, issuer/signatory, evidence checks, deadline or trigger, and consequence only when the source states it. No generic filler such as "check legal requirements".
- Do not assume standard requirements (notarization, stamp paper, affidavit, licence, validity period); extract each from the actual tender.
- TinyFish is the required web discovery/extraction integration and should do real work on a real source. Manual PDF upload is only a fallback for blocked sources.
- Use deterministic code for scoring, date normalization, deduplication, schema validation, and citation checks. Treat model output as untrusted until validated.
- The product supports decisions; it must not claim legal eligibility or submit bids autonomously.

## Planned shape (no code yet)
Main orchestrator plus Discovery (TinyFish), Extraction, Analysis, Compliance, and Monitoring components, backed by deterministic validation and persistence. Persist tenders, documents, requirements, evidence matches, checklist tasks, and change snapshots with provenance; see the spec's data-entity and risk sections before designing schemas.

## Open decisions
Stack, model/provider access, first official tender source, calendar integration, and hosting are undecided. Confirm with the user before scaffolding; do not pick a stack from this file.
