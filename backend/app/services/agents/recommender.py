"""Agent 1: what should this company do about this tender?

The model proposes. The deterministic gate disposes. A human confirms.

The model is given the tender's verified clauses, the company's own profile
and the evidence it already holds, and it may only answer from those. It is
also given the passages our index found for those clauses: the tender's own
words around the clause, and what our own certificates actually say. The
grounding gate then checks that every proposal rests on a clause we actually
hold and introduces no figure that is not already in that clause or in the
tender record. A proposal that fails keeps its reason; it is never quietly
kept as if it were a fact.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError

from app.core.exceptions import NotConfiguredError
from app.integrations.ai import AIError, AIProvider
from app.models.agents import GroundingStatus, RecommendationKind
from app.services.agents.gate import _referenced_ids, check_grounding

PROMPT_VERSION = "recommendations-v1"

KIND_VALUES = (
    "document_to_prepare",
    "clarification_to_raise",
    "red_flag",
    "format_requirement",
    "timeline_note",
)

SYSTEM_PROMPT = """You advise a company on what to do about one public tender.

You are given the tender's clauses (each with its clause number and the exact
wording the tender uses) and the company's own profile and evidence.

Rules:
1. Every proposal must rest on at least one clause number from the list. Refer
   to clauses exactly as given, for example "3.1".
2. Do not state a number, amount, percentage, date or threshold that is not
   already in the clause you refer to or in the tender details. If you do, the
   proposal is rejected.
3. Do not invent registrations, certificates, laws or deadlines. If something
   is not in the clauses or the profile, say that it is not stated.
4. Write the action in plain language for the bidder: what to obtain, from
   whom, in what form, signed by whom, by when.
5. Where the company already holds a document, name it.
6. Do not give legal advice and do not comment on whether a clause is fair,
   enforceable or likely to be challenged.
7. Return JSON only: {"recommendations": [...]}. Every item in the list must be
   an object with these keys: "kind", "title", "claim", "action",
   "acceptance_criteria", "requirement_refs" (a list of clause numbers),
   "owner_hint" and "due_hint_days_before_bid". For example:
   {"kind": "document_to_prepare", "title": "Attach the audited statements",
   "claim": "Clause 3.1 requires a three-year average turnover of at least INR 5 crore.",
   "action": "Attach the CA-audited statements showing the average turnover.",
   "acceptance_criteria": "The statements are signed by the chartered accountant.",
   "requirement_refs": ["3.1"], "owner_hint": "finance",
   "due_hint_days_before_bid": 7}
   Return {"recommendations": []} when the clauses give nothing to act on."""

USER_TEMPLATE = """Tender: {title}
Authority: {authority}
Reference: {reference}
Submission deadline: {deadline}
Tender value: {value}

Company profile:
- Services: {services}
- Sectors: {sectors}
- Regions: {regions}
- Certifications: {certifications}
- Annual turnover: {turnover}
- Employees: {employees}

Evidence the company already holds:
{evidence}

Clauses of this tender (clause number, wording, deadline, consequence):
{clauses}

The tender's own words around these clauses, read from the indexed documents:
{clause_context}

What our own documents say about these clauses, read from the indexed
documents:
{evidence_context}

Return at most 12 recommendations, most important first."""

ITEM_EXAMPLE = {
    "kind": "document_to_prepare",
    "title": "Attach the audited financial statements",
    "claim": "Clause 3.1 requires a three-year average turnover of at least INR 5 crore, so the audited statements must show that average.",
    "action": "Attach the CA-audited financial statements for the last three years, showing the average turnover.",
    "acceptance_criteria": "The uploaded statements are signed by the chartered accountant and show the three-year average turnover.",
    "requirement_refs": ["3.1"],
    "owner_hint": "finance",
    "due_hint_days_before_bid": 7,
}


class ProposedRecommendation(BaseModel):
    """One proposal as the model wrote it."""

    model_config = ConfigDict(extra="ignore")

    kind: str = "document_to_prepare"
    title: str = ""
    claim: str = ""
    action: str | None = None
    acceptance_criteria: str | None = None
    requirement_refs: list[str] = Field(default_factory=list)
    owner_hint: str | None = None
    due_hint_days_before_bid: int | None = None


def parse_proposals(payload: Any) -> tuple[list[ProposedRecommendation], int]:
    """Read the model's proposals, dropping the ones that are not usable."""
    items = payload.get("recommendations") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return [], 0
    proposals: list[ProposedRecommendation] = []
    invalid = 0
    for item in items:
        if isinstance(item, str):
            # The model answered in prose. Keep the sentence, and let the gate
            # decide whether it rests on a clause we hold.
            text = item.strip()
            if not text:
                invalid += 1
                continue
            items_dict = {
                "kind": "document_to_prepare",
                "title": text[:90],
                "claim": text,
                "requirement_refs": list(_referenced_ids(text)),
            }
        elif isinstance(item, dict):
            items_dict = item
        else:
            invalid += 1
            continue
        try:
            proposal = ProposedRecommendation.model_validate(items_dict)
        except PydanticValidationError:
            invalid += 1
            continue
        if not proposal.title.strip() or not proposal.claim.strip():
            invalid += 1
            continue
        kind = (proposal.kind or "").strip().lower()
        if kind not in KIND_VALUES:
            kind = "document_to_prepare"
        proposal.kind = kind
        proposals.append(proposal)
    return proposals, invalid


MAX_CLAUSES_IN_PROMPT = 12
MAX_EXCERPT_CHARS = 240


def _clause_lines(requirements: list[dict]) -> str:
    lines: list[str] = []
    for item in requirements[:MAX_CLAUSES_IN_PROMPT]:
        reference = item.get("clause_reference") or item.get("id")
        excerpt = (item.get("excerpt") or "").strip()
        if len(excerpt) > MAX_EXCERPT_CHARS:
            excerpt = excerpt[:MAX_EXCERPT_CHARS] + "..."
        parts = [f"Clause {reference}: {excerpt}"]
        if item.get("deadline_text"):
            parts.append(f"Deadline: {item['deadline_text']}")
        if item.get("consequence_text"):
            parts.append(f"Consequence: {item['consequence_text']}")
        lines.append(" - ".join(parts))
    return "\n".join(lines) or "(no clauses were extracted from this tender)"


MAX_EVIDENCE_IN_PROMPT = 10


def _evidence_lines(company_documents: list[dict], decisions: dict[str, dict]) -> str:
    lines: list[str] = []
    for document in company_documents[:MAX_EVIDENCE_IN_PROMPT]:
        title = document.get("title") or document.get("original_filename") or "document"
        bits = [f"- {title}"]
        if document.get("document_type"):
            bits.append(f"({document['document_type']})")
        if document.get("expiry_date"):
            bits.append(f"valid to {document['expiry_date']}")
        if document.get("verification_status"):
            bits.append(f"[{document['verification_status']}]")
        lines.append(" ".join(bits))
    if decisions:
        held = [item.get("requirement_id") for item in decisions.values() if item.get("status") == "confirmed"]
        if held:
            lines.append(f"Evidence already confirmed against {len(held)} clause(s).")
    return "\n".join(lines) or "(the company has no evidence on file yet)"


def _owner_label(hint: str | None) -> str | None:
    labels = {
        "finance": "Finance",
        "technical": "Technical",
        "legal": "Legal",
        "compliance": "Compliance",
        "commercial": "Commercial",
        "hr": "HR",
        "operations": "Operations",
    }
    if not hint:
        return None
    return labels.get(hint.strip().lower())


def _due_date(deadline: datetime | None, hint: int | None) -> datetime | None:
    """The due date is computed, never taken from the model."""
    if deadline is None:
        return None
    days = hint if isinstance(hint, int) and 0 <= hint <= 120 else 7
    return deadline - timedelta(days=days)


class Recommender:
    """Proposes what to do, then has its proposals judged by the gate."""

    def __init__(self, ai: AIProvider) -> None:
        self.ai = ai

    def propose(
        self,
        *,
        tender: dict,
        company: dict,
        requirements: list[dict],
        company_documents: list[dict],
        evidence_decisions: dict[str, dict],
        deadline: datetime | None = None,
        clause_context: str = "",
        evidence_context: str = "",
    ) -> list[dict]:
        """Return the proposals that passed the gate, with their verdicts."""
        if not self.ai.configured:
            raise NotConfiguredError(
                "The AI provider is not configured, so no recommendation was made. "
                "Set AI_PROVIDER, the provider API key and model."
            )

        known = {item["id"]: item for item in requirements}
        clause_refs = {
            (item.get("clause_reference") or item["id"]): item for item in requirements
        }
        payload = self.ai.complete_json(
            system=SYSTEM_PROMPT,
            user=USER_TEMPLATE.format(
                title=tender.get("title") or "tender",
                authority=tender.get("authority") or "not stated",
                reference=tender.get("reference_number") or "not stated",
                deadline=(deadline.date().isoformat() if deadline else "not stated"),
                value=(tender.get("discovery_extracted") or {}).get("value_amount") or "not stated",
                services=", ".join(company.get("products_services") or []) or "not stated",
                sectors=", ".join(company.get("sectors") or []) or "not stated",
                regions=", ".join(company.get("regions") or []) or "not stated",
                certifications=", ".join(company.get("certifications") or []) or "not stated",
                turnover=company.get("annual_turnover") or "not stated",
                employees=company.get("employee_count") or "not stated",
                evidence=_evidence_lines(company_documents, evidence_decisions),
                clauses=_clause_lines(requirements),
                clause_context=clause_context or "(nothing indexed for these clauses)",
                evidence_context=evidence_context or "(nothing indexed for our documents)",
            ),
        )
        proposals, _invalid = parse_proposals(payload)

        results: list[dict] = []
        for proposal in proposals:
            referenced = []
            for reference in proposal.requirement_refs:
                item = clause_refs.get(str(reference).strip())
                if item:
                    referenced.append(item)
            check = check_grounding(
                f"{proposal.claim} {proposal.action or ''} {proposal.acceptance_criteria or ''}",
                requirement_ids=[item["id"] for item in referenced],
                known_requirements={item["id"]: item for item in referenced},
                stored_fields={
                    "deadline": deadline.isoformat() if deadline else None,
                    "reference_number": tender.get("reference_number"),
                    "authority": tender.get("authority"),
                    "value_amount": (tender.get("discovery_extracted") or {}).get("value_amount"),
                    "our_evidence": company_documents,
                },
                allowed_kinds=KIND_VALUES,
            )
            status: GroundingStatus = "grounded" if check.grounded else "unverified"
            cleaned = check.cleaned_claim or proposal.claim.strip()
            results.append(
                {
                    "kind": proposal.kind,
                    "title": proposal.title.strip()[:200],
                    "claim": cleaned[:2000],
                    "action": (proposal.action or "").strip()[:2000] or None,
                    "acceptance_criteria": (proposal.acceptance_criteria or "").strip()[:2000] or None,
                    "suggested_owner": _owner_label(proposal.owner_hint),
                    "suggested_due_at": _due_date(deadline, proposal.due_hint_days_before_bid),
                    "requirement_refs": [str(item) for item in proposal.requirement_refs],
                    "grounded_requirements": check.grounded_requirements,
                    "dropped_claims": check.dropped_claims,
                    "grounding_status": status,
                    "grounding_note": check.reason,
                    "proposed_task": {
                        "title": proposal.title.strip()[:200],
                        "action": (proposal.action or "").strip()[:2000] or None,
                        "acceptance_criteria": (proposal.acceptance_criteria or "").strip()[:2000] or None,
                        "owner": _owner_label(proposal.owner_hint),
                        "due_at": _due_date(deadline, proposal.due_hint_days_before_bid),
                        "status": "missing",
                    }
                    if check.grounded
                    else None,
                }
            )
        return results
