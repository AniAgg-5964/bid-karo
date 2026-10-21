"""Agent 2: what does this mean for us, and what do we do about it?

The verdict is **not** the model's. It comes from the deterministic
assessment: a clause passes only when its citation is verified and a human has
confirmed a valid, unexpired piece of our evidence. The model is only allowed
to explain that verdict in plain language and to say what we should do next.

So the model may write the gap, the action and how we will know it is done. It
may not change a pass into a fail, or a fail into a pass. The stored record
always carries the deterministic status.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError

from app.core.exceptions import NotConfiguredError
from app.integrations.ai import AIError, AIProvider
from app.services.agents.gate import check_grounding

PROMPT_VERSION = "verification-v1"

SYSTEM_PROMPT = """You explain a bid-readiness check to the company that owns it.

You are given, for each clause of a tender, the *verified* result of the check
(cleared, not cleared, or unknown) together with the reason, the wording of
the clause, and the evidence the company holds.

Rules:
1. Never change the result. It is given to you and it is correct. If you
   disagree, say so in the action as a question, do not restate the result.
2. Do not state a number, amount, percentage, date or threshold that is not
   already in the clause, the result or the evidence. If you do, the answer is
   rejected.
3. Write what the company must do: which document, from whom, in what form,
   signed by whom, by when. Name the document it already holds where it
   applies.
4. Do not give legal advice and do not comment on fairness or enforceability.
5. Return JSON only: {"items": [...]}. One item per clause you have advice
   for. Return {"items": []} when there is nothing to advise."""

USER_TEMPLATE = """Tender: {title}
Authority: {authority}
Submission deadline: {deadline}

Company profile:
- Services: {services}
- Regions: {regions}
- Certifications: {certifications}
- Annual turnover: {turnover}
- Employees: {employees}

Clauses and their verified results:
{clauses}

Evidence the company holds:
{evidence}

Return at most 12 items, the most urgent first."""

ITEM_EXAMPLE = {
    "requirement_refs": ["3.2"],
    "gap": "We have no completion certificate for a similar work in the last five years.",
    "action": "Ask the client of the State Highway 9 widening project for the completion certificate, showing the contract value of INR 6.2 crore.",
    "acceptance_criteria": "The certificate is on letterhead, shows the contract value and the completion date, and is signed by the client.",
    "owner_hint": "commercial",
    "due_hint_days_before_bid": 10,
}

GATE_LABELS = {
    "pass": "You clear this",
    "fail": "You do not clear this",
    "unknown": "We cannot tell yet",
}


class ProposedVerification(BaseModel):
    """One explanation as the model wrote it.

    The clause may be named under any of these keys; the model is not told to
    use one exact word.
    """

    model_config = ConfigDict(extra="ignore")

    requirement_refs: list[str] = Field(default_factory=list)
    clause: str | None = None
    clause_ref: str | None = None
    gap: str = ""
    action: str | None = None
    acceptance_criteria: str | None = None
    owner_hint: str | None = None
    due_hint_days_before_bid: int | None = None

    def references(self) -> list[str]:
        """The clauses this item refers to, however the model named them."""
        refs = list(self.requirement_refs)
        for value in (self.clause, self.clause_ref):
            if value:
                refs.append(str(value))
        return [str(item).strip() for item in refs if str(item).strip()]


def parse_verifications(payload: Any) -> tuple[list[ProposedVerification], int]:
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return [], 0
    parsed: list[ProposedVerification] = []
    invalid = 0
    for item in items:
        if not isinstance(item, dict):
            invalid += 1
            continue
        try:
            proposal = ProposedVerification.model_validate(item)
        except PydanticValidationError:
            invalid += 1
            continue
        if not proposal.references():
            invalid += 1
            continue
        proposal.requirement_refs = proposal.references()
        parsed.append(proposal)
    return parsed, invalid


MAX_CLAUSES_IN_PROMPT = 12
MAX_EXCERPT_CHARS = 240


def _clause_lines(items: list[dict]) -> str:
    lines: list[str] = []
    for item in items[:MAX_CLAUSES_IN_PROMPT]:
        reference = item.get("clause_reference") or item.get("requirement_id")
        excerpt = (item.get("excerpt") or "").strip()
        if len(excerpt) > MAX_EXCERPT_CHARS:
            excerpt = excerpt[:MAX_EXCERPT_CHARS] + "..."
        lines.append(
            f"Clause {reference} [{item.get('gate', 'unknown').upper()}] {excerpt} "
            f"- Reason: {item.get('reason') or 'not stated'} "
            f"- Evidence: {item.get('evidence_document_title') or item.get('evidence_status') or 'none'}"
        )
    return "\n".join(lines) or "(no clauses were checked)"


MAX_EVIDENCE_IN_PROMPT = 10


def _evidence_lines(documents: list[dict]) -> str:
    lines = []
    for document in documents[:MAX_EVIDENCE_IN_PROMPT]:
        title = document.get("title") or document.get("original_filename") or "document"
        bits = [f"- {title}"]
        if document.get("document_type"):
            bits.append(f"({document['document_type']})")
        if document.get("expiry_date"):
            bits.append(f"valid to {document['expiry_date']}")
        if document.get("verification_status"):
            bits.append(f"[{document['verification_status']}]")
        lines.append(" ".join(bits))
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
    if deadline is None:
        return None
    days = hint if isinstance(hint, int) and 0 <= hint <= 120 else 7
    return deadline - timedelta(days=days)


class Verifier:
    """Explains the deterministic verdict and proposes the next step."""

    def __init__(self, ai: AIProvider) -> None:
        self.ai = ai

    def verify(
        self,
        *,
        tender: dict,
        company: dict,
        eligibility_items: list[dict],
        company_documents: list[dict],
        deadline: datetime | None = None,
    ) -> list[dict]:
        """Return one explanation per clause, with the verdict taken from us."""
        if not self.ai.configured:
            raise NotConfiguredError(
                "The AI provider is not configured, so no verification was written. "
                "Set AI_PROVIDER, the provider API key and model."
            )

        by_reference = {
            (item.get("clause_reference") or item.get("requirement_id")): item
            for item in eligibility_items
        }
        payload = self.ai.complete_json(
            system=SYSTEM_PROMPT,
            user=USER_TEMPLATE.format(
                title=tender.get("title") or "tender",
                authority=tender.get("authority") or "not stated",
                deadline=(deadline.date().isoformat() if deadline else "not stated"),
                services=", ".join(company.get("products_services") or []) or "not stated",
                regions=", ".join(company.get("regions") or []) or "not stated",
                certifications=", ".join(company.get("certifications") or []) or "not stated",
                turnover=company.get("annual_turnover") or "not stated",
                employees=company.get("employee_count") or "not stated",
                clauses=_clause_lines(eligibility_items),
                evidence=_evidence_lines(company_documents),
            ),
        )
        proposals, _invalid = parse_verifications(payload)

        results: list[dict] = []
        for proposal in proposals:
            referenced = []
            for reference in proposal.requirement_refs:
                item = by_reference.get(str(reference).strip())
                if item:
                    referenced.append(item)
            if not referenced:
                continue
            check = check_grounding(
                f"{proposal.gap} {proposal.action or ''} {proposal.acceptance_criteria or ''}",
                requirement_ids=[item["requirement_id"] for item in referenced],
                known_requirements={item["requirement_id"]: item for item in referenced},
                stored_fields={
                    "deadline": deadline.isoformat() if deadline else None,
                    "reference_number": tender.get("reference_number"),
                    "our_evidence": company_documents,
                },
            )
            for item in referenced:
                verdict = (item.get("gate") or "unknown").lower()
                label = GATE_LABELS.get(verdict, "We cannot tell yet")
                claim = f"{label}: {item.get('reason') or 'the reason is not stated'}."
                if proposal.gap:
                    claim = f"{claim} {proposal.gap.strip()}"
                if check.cleaned_claim:
                    claim = f"{claim} {check.cleaned_claim.strip()}"
                results.append(
                    {
                        "kind": "verification",
                        "title": item.get("title") or "Clause",
                        "claim": claim.strip()[:2000],
                        "action": (proposal.action or "").strip()[:2000] or None,
                        "acceptance_criteria": (proposal.acceptance_criteria or "").strip()[:2000] or None,
                        "suggested_owner": _owner_label(proposal.owner_hint),
                        "suggested_due_at": _due_date(deadline, proposal.due_hint_days_before_bid),
                        "requirement_refs": [item["requirement_id"] for item in referenced],
                        "grounded_requirements": check.grounded_requirements,
                        "dropped_claims": check.dropped_claims,
                        "grounding_status": "grounded" if check.grounded else "unverified",
                        "grounding_note": check.reason,
                        "verdict": verdict,
                        "proposed_task": {
                            "title": item.get("title") or "Clause",
                            "action": (proposal.action or "").strip()[:2000] or None,
                            "acceptance_criteria": (proposal.acceptance_criteria or "").strip()[:2000] or None,
                            "owner": _owner_label(proposal.owner_hint),
                            "due_at": _due_date(deadline, proposal.due_hint_days_before_bid),
                            "status": "missing",
                            "requirement_id": item["requirement_id"],
                        }
                        if check.grounded
                        else None,
                    }
                )
        return results
