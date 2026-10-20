"""Deterministic Phase 4 assessment: evidence matching, eligibility and score.

Every mandatory gate result needs a human-confirmed evidence document. The
soft score is computed separately and never turns an Unknown or Fail into a
pass. Matching is token-based and explainable; no model call is involved.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone

from app.core.database import Database, utcnow
from app.core.exceptions import AppError, NotFoundError
from app.models.assessment import (
    AssessmentCounts,
    AssessmentOut,
    EligibilityItem,
    EligibilitySummary,
    EvidenceCandidate,
    EvidenceDecision,
    FitScore,
    RequirementEvidenceOut,
    ScoreDimension,
)
from app.models.workflow import ChecklistTaskOut, LegalObligationOut
from app.repositories.assessment import AssessmentRepository, EvidenceRepository
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.repositories.tender_documents import RequirementRepository, TenderDocumentRepository
from app.repositories.tenders import ChecklistRepository, TenderRepository
from app.services.relevance import score_tender

GATING_CATEGORIES = {"eligibility", "technical", "financial"}
CHECKLIST_CATEGORIES = {"submission", "compliance"}
OPEN_TASK_STATUSES = {"missing", "incomplete", "needs_verification", "in_progress"}
POST_AWARD_MARKERS = (
    "during the contract",
    "during the contract period",
    "after award",
    "after the award",
    "commencement of work",
    "commencement of the contract",
    "completion of work",
    "completion of the contract",
    "defect liability",
    "warranty",
    "maintenance period",
    "post-award",
    "post award",
    "after the contract",
)

TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "the", "and", "for", "with", "shall", "must", "bidder", "bidders", "tender",
    "tenders", "document", "documents", "required", "require", "requirement",
    "provide", "provided", "submit", "submitted", "submission", "minimum",
    "during", "last", "three", "years", "year", "from", "that", "this", "have",
    "has", "are", "was", "were", "will", "not", "any", "all", "its", "their",
    "which", "such", "under", "than", "least", "also", "been", "other", "into",
    "per", "copy", "copies", "duly", "self", "attested", "signed", "issued",
    "issue", "valid", "validity", "period", "complete", "completed", "shall",
}

SYNONYMS = {
    "certifications": "certificate",
    "certification": "certificate",
    "certified": "certificate",
    "certificates": "certificate",
    "licences": "license",
    "licence": "license",
    "licenses": "license",
    "statements": "statement",
    "returns": "return",
    "documents": "document",
    "registrations": "registration",
    "declarations": "declaration",
    "affidavits": "affidavit",
    "completions": "completion",
    "contracts": "contract",
    "projects": "project",
    "works": "work",
    "orders": "order",
}

STRONG_TERMS = {
    "iso", "9001", "14001", "45001", "pan", "gst", "msme", "udyam", "turnover",
    "financial", "audited", "experience", "completion", "solvency", "epf", "esic",
    "labour", "labor", "license", "registration", "affidavit", "declaration",
    "insurance", "noc", "quality", "safety", "environment", "bank", "emd",
    "contractor", "gstin", "pf", "itr",
}

CATEGORY_TERMS = {
    "financial": {"financial", "bank", "turnover", "audited", "solvency", "itr", "gst", "statement"},
    "technical": {"experience", "completion", "work", "project", "quality", "contract", "order"},
    "eligibility": {"registration", "license", "certificate", "pan", "gst", "msme", "udyam", "iso", "pf", "esic"},
    "compliance": {"declaration", "affidavit", "insurance", "labour", "safety", "environment", "noc"},
    "submission": {"declaration", "affidavit", "bank", "emd", "form"},
}


def _normalize(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def _stem(word: str) -> str:
    for suffix in ("ations", "ation", "ments", "ment", "ings", "ing", "ies"):
        if len(word) > len(suffix) + 4 and word.endswith(suffix):
            if suffix == "ies":
                return word[: -len(suffix)] + "y"
            return word[: -len(suffix)]
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _tokens(value: str | None) -> set[str]:
    words = TOKEN_RE.findall(_normalize(value))
    result: set[str] = set()
    for word in words:
        if len(word) < 3 or word in STOPWORDS:
            continue
        result.add(SYNONYMS.get(word, _stem(word)))
    return result


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    return None


def _format_inr(value: float) -> str:
    if value >= 10_000_000:
        return f"INR {value / 10_000_000:.2f} crore"
    if value >= 100_000:
        return f"INR {value / 100_000:.2f} lakh"
    return f"INR {value:,.0f}"


def _parse_amount_inr(text: str) -> float | None:
    match = re.search(
        r"(?:INR|Rs\.?|₹)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(crore|lakh|lakhs|million|mn|billion|bn)?",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = (match.group(2) or "").lower()
    multipliers = {
        "crore": 10_000_000,
        "lakh": 100_000,
        "lakhs": 100_000,
        "million": 1_000_000,
        "mn": 1_000_000,
        "billion": 1_000_000_000,
        "bn": 1_000_000_000,
    }
    return amount * multipliers.get(unit, 1)


def _requirement_text(requirement: dict) -> str:
    return " ".join(
        str(requirement.get(field) or "")
        for field in ("title", "obligation", "excerpt")
    )


def _is_post_award(requirement: dict) -> bool:
    if requirement.get("category") == "performance":
        return True
    text = _normalize(
        " ".join(
            str(requirement.get(field) or "")
            for field in ("title", "obligation", "excerpt", "deadline_text", "consequence_text")
        )
    )
    return any(marker in text for marker in POST_AWARD_MARKERS)


def _post_award_trigger_type(requirement: dict) -> str:
    text = _normalize(
        " ".join(
            str(requirement.get(field) or "")
            for field in ("title", "obligation", "excerpt", "deadline_text")
        )
    )
    if any(marker in text for marker in ("after award", "after the award", "post-award", "post award")):
        return "after_award"
    if any(marker in text for marker in ("commencement", "during the contract", "during the contract period")):
        return "during_contract"
    if any(marker in text for marker in ("completion", "defect liability", "warranty", "maintenance")):
        return "after_completion"
    return "during_contract"


def _document_tokens(document: dict) -> set[str]:
    return _tokens(
        " ".join(
            str(document.get(field) or "")
            for field in (
                "title",
                "document_type",
                "issuer",
                "notes",
                "financial_year",
                "signatory",
            )
        )
    )


def _document_validity(document: dict) -> tuple[bool, str | None]:
    if document.get("verification_status") in {"rejected", "expired"}:
        return False, f"Document is marked {document['verification_status']}."
    expiry = _as_date(document.get("expiry_date"))
    if expiry and expiry < utcnow().date():
        return False, f"Document expired on {expiry.isoformat()}."
    if document.get("verification_status") == "self_declared":
        return True, "Self-declared document; confirm the issuer and signatory."
    return True, None


def profile_hints(company: dict, requirement: dict) -> list[str]:
    text = _requirement_text(requirement)
    normalized = _normalize(text)
    hints: list[str] = []

    if "turnover" in normalized and company.get("annual_turnover") is not None:
        stated = _parse_amount_inr(text)
        if stated:
            actual = float(company["annual_turnover"])
            relation = "at or above" if actual >= stated else "below"
            hints.append(
                f"Company profile turnover {_format_inr(actual)} is {relation} the "
                f"stated {_format_inr(stated)}. Confirm with audited evidence."
            )

    requirement_tokens = _tokens(text)
    for certification in company.get("certifications") or []:
        cert_tokens = _tokens(certification)
        if cert_tokens & requirement_tokens:
            hints.append(f"Company profile lists certification: {certification}.")

    return hints


def evidence_candidates(
    company: dict, requirement: dict, documents: list[dict], *, limit: int = 3
) -> list[EvidenceCandidate]:
    req_tokens = _tokens(_requirement_text(requirement))
    category_terms = CATEGORY_TERMS.get(requirement.get("category", ""), set())
    results: list[EvidenceCandidate] = []

    for document in documents:
        doc_tokens = _document_tokens(document)
        overlap = req_tokens & doc_tokens
        affinity = bool(category_terms & (doc_tokens | _tokens(document.get("document_type"))))
        if not overlap and not affinity:
            continue

        score = min(0.55, 0.18 * len(overlap))
        reasons: list[str] = []
        if overlap:
            reasons.append("Matches: " + ", ".join(sorted(overlap)[:6]))
        if overlap & STRONG_TERMS:
            score += 0.25
            reasons.append("Matches a distinctive term from the requirement.")
        if affinity:
            score += 0.15
            reasons.append("Document type fits the requirement category.")

        score = round(min(score, 1.0), 2)
        if score < 0.25:
            continue

        valid, validity_note = _document_validity(document)
        results.append(
            EvidenceCandidate(
                document_id=document["id"],
                title=document.get("title") or "Untitled evidence",
                document_type=document.get("document_type") or "other",
                issuer=document.get("issuer"),
                expiry_date=_as_date(document.get("expiry_date")),
                score=score,
                matched_terms=sorted(overlap)[:10],
                reasons=reasons,
                valid=valid,
                validity_note=validity_note,
            )
        )

    results.sort(key=lambda item: (-item.score, item.title.lower()))
    return results[:limit]


class AssessmentService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.tenders = TenderRepository(db)
        self.requirements = RequirementRepository(db)
        self.tender_documents = TenderDocumentRepository(db)
        self.documents = DocumentRepository(db)
        self.evidence = EvidenceRepository(db)
        self.checklist = ChecklistRepository(db)
        self.assessments = AssessmentRepository(db)
        self.audit = AuditRepository(db)

    def _tender(self, tender_id: str, company_id: str) -> dict:
        tender = self.tenders.find_for_company(tender_id, company_id)
        if not tender:
            raise NotFoundError("Tender not found.")
        return tender

    def _requirements(self, company_id: str, tender_id: str) -> list[dict]:
        items, _ = self.requirements.list_for_tender(
            company_id, tender_id, limit=300, offset=0
        )
        return [item for item in items if item.get("verification_status") != "rejected"]

    def _company_documents(self, company_id: str) -> list[dict]:
        items, _ = self.documents.list_for_company(company_id, limit=300, offset=0)
        return items

    def _eligibility(
        self,
        *,
        company: dict,
        requirements: list[dict],
        evidence_map: dict[str, dict],
        documents: list[dict],
    ) -> EligibilitySummary:
        documents_by_id = {item["id"]: item for item in documents}
        items: list[EligibilityItem] = []

        for requirement in requirements:
            if requirement.get("mandatory") != "yes":
                continue
            if requirement.get("category") not in GATING_CATEGORIES:
                continue

            decision = evidence_map.get(requirement["id"])
            hints = profile_hints(company, requirement)
            gate = "unknown"
            evidence_status = "none"
            evidence_document_id = None
            evidence_document_title = None
            reason = "No evidence has been confirmed. Unknown is not a pass."

            if requirement.get("verification_status") != "verified":
                reason = (
                    "The requirement citation is not verified, so eligibility cannot be confirmed."
                )
            elif decision:
                document = documents_by_id.get(decision.get("document_id"))
                evidence_document_id = decision.get("document_id")
                evidence_document_title = (document or {}).get("title")
                evidence_status = decision.get("status", "none")
                if decision.get("status") == "contradicted":
                    gate = "fail"
                    reason = "A human reviewer marked the selected evidence as contradicting this requirement."
                elif decision.get("status") == "confirmed":
                    if not document:
                        reason = "The confirmed evidence document is no longer available."
                    else:
                        valid, validity_note = _document_validity(document)
                        if valid:
                            gate = "pass"
                            reason = f"Human-confirmed evidence: {document.get('title')}."
                            if validity_note:
                                reason += f" {validity_note}"
                        else:
                            reason = validity_note or "The confirmed evidence is not valid."
                else:
                    reason = "The selected document was rejected as evidence. Unknown is not a pass."
            else:
                candidates = evidence_candidates(company, requirement, documents, limit=1)
                if candidates:
                    evidence_status = "suggested"
                    reason = (
                        f"Possible evidence found: {candidates[0].title}. "
                        "A human must confirm or reject it."
                    )

            items.append(
                EligibilityItem(
                    requirement_id=requirement["id"],
                    title=requirement.get("title") or "Untitled requirement",
                    category=requirement.get("category") or "other",
                    mandatory=requirement.get("mandatory") or "unknown",
                    excerpt=requirement.get("excerpt") or "",
                    page_index=int(requirement.get("page_index") or 1),
                    printed_page=requirement.get("printed_page"),
                    clause_reference=requirement.get("clause_reference"),
                    document_id=requirement["document_id"],
                    document_title=requirement.get("document_title"),
                    gate=gate,
                    evidence_status=evidence_status,
                    evidence_document_id=evidence_document_id,
                    evidence_document_title=evidence_document_title,
                    profile_hints=hints,
                    reason=reason,
                )
            )

        pass_count = sum(1 for item in items if item.gate == "pass")
        fail_count = sum(1 for item in items if item.gate == "fail")
        unknown_count = sum(1 for item in items if item.gate == "unknown")

        if not items:
            status = "unknown"
            message = "No mandatory eligibility requirements have been extracted yet."
        elif fail_count:
            status = "fail"
            message = "At least one mandatory eligibility criterion is marked as failed."
        elif pass_count == len(items):
            status = "pass"
            message = "Every mandatory eligibility criterion has human-confirmed evidence."
        else:
            status = "unknown"
            message = (
                f"{unknown_count} mandatory criteria remain Unknown. Unknown is not a pass."
            )

        return EligibilitySummary(
            status=status,
            pass_count=pass_count,
            fail_count=fail_count,
            unknown_count=unknown_count,
            items=items,
            message=message,
        )

    def _score(
        self,
        *,
        company: dict,
        tender: dict,
        requirements: list[dict],
        tender_documents: list[dict],
        eligibility: EligibilitySummary,
    ) -> FitScore:
        now = utcnow()
        texts = " ".join(_requirement_text(item) for item in requirements)[:40_000]
        relevance = score_tender(
            company,
            title=tender.get("title") or "",
            snippet=tender.get("description") or "",
            text=texts,
        )
        profile_score = round(relevance.score * 100)

        verified = sum(1 for item in requirements if item.get("verification_status") == "verified")
        needs_review = sum(
            1 for item in requirements if item.get("verification_status") == "needs_review"
        )
        verification_score = (
            round(((verified + 0.5 * needs_review) / len(requirements)) * 100)
            if requirements
            else 0
        )

        gating_total = len(eligibility.items)
        evidence_score = (
            round((eligibility.pass_count / gating_total) * 100) if gating_total else 0
        )

        extracted = sum(
            1 for item in tender_documents if item.get("status") == "extracted"
        )
        document_ratio = extracted / len(tender_documents) if tender_documents else 0
        readiness_score = round((0.7 * document_ratio + (0.3 if requirements else 0)) * 100)

        dimensions = [
            ScoreDimension(
                key="profile_fit",
                label="Profile fit",
                weight=25,
                score=profile_score,
                contribution=round(profile_score * 0.25, 1),
                reason=(
                    "; ".join(relevance.reasons)
                    if relevance.reasons
                    else "No declared sector, product or keyword matched this tender."
                ),
            ),
            ScoreDimension(
                key="requirements_verified",
                label="Citation verification",
                weight=20,
                score=verification_score,
                contribution=round(verification_score * 0.20, 1),
                reason=(
                    f"{verified} verified, {needs_review} need visual review, "
                    f"{len(requirements)} total requirements."
                    if requirements
                    else "No requirements have been extracted."
                ),
            ),
            ScoreDimension(
                key="evidence_coverage",
                label="Mandatory evidence coverage",
                weight=40,
                score=evidence_score,
                contribution=round(evidence_score * 0.40, 1),
                reason=(
                    f"{eligibility.pass_count} of {gating_total} mandatory eligibility "
                    "criteria have human-confirmed valid evidence."
                    if gating_total
                    else "No mandatory eligibility criteria have been extracted."
                ),
            ),
            ScoreDimension(
                key="document_readiness",
                label="Document readiness",
                weight=15,
                score=readiness_score,
                contribution=round(readiness_score * 0.15, 1),
                reason=(
                    f"{extracted} of {len(tender_documents)} tender documents have extractable text."
                    if tender_documents
                    else "No tender documents have been uploaded."
                ),
            ),
        ]

        value = int(round(sum(item.contribution for item in dimensions)))
        if eligibility.status == "fail":
            explanation = (
                "Mandatory eligibility has a confirmed failure. The soft score cannot "
                "override a failed mandatory criterion."
            )
        elif eligibility.status == "unknown":
            explanation = (
                "Mandatory eligibility is not fully confirmed. Treat this score as "
                "provisional until every Unknown criterion is reviewed."
            )
        elif not requirements:
            explanation = "Not enough extracted requirements to assess this tender."
        else:
            explanation = (
                "Soft fit based on profile match, citation verification, confirmed "
                "evidence coverage and document readiness. It is not an eligibility decision."
            )

        if value >= 75:
            band = "strong"
        elif value >= 50:
            band = "moderate"
        elif value >= 25:
            band = "weak"
        else:
            band = "insufficient"

        return FitScore(
            value=value,
            band=band,
            dimensions=dimensions,
            explanation=explanation,
            gating_status=eligibility.status,
            generated_at=now,
        )

    def assess(self, *, tender_id: str, company: dict) -> AssessmentOut:
        tender = self._tender(tender_id, company["id"])
        requirements = self._requirements(company["id"], tender_id)
        documents = self._company_documents(company["id"])
        tender_documents = self.tender_documents.list_for_tender(
            company["id"], tender_id
        )
        evidence_map = self.evidence.find_for_requirements(
            [item["id"] for item in requirements], company["id"]
        )
        eligibility = self._eligibility(
            company=company,
            requirements=requirements,
            evidence_map=evidence_map,
            documents=documents,
        )
        score = self._score(
            company=company,
            tender=tender,
            requirements=requirements,
            tender_documents=tender_documents,
            eligibility=eligibility,
        )
        _, checklist_total = self.checklist.list_for_tender(
            company["id"], tender_id, limit=1
        )
        counts = AssessmentCounts(
            total=len(requirements),
            verified=sum(
                1
                for item in requirements
                if item.get("verification_status") == "verified"
            ),
            mandatory_gating=len(eligibility.items),
            checklist_total=checklist_total,
            checklist_open=self.checklist.count_open_for_tender(company["id"], tender_id),
        )
        result = AssessmentOut(
            tender_id=tender_id,
            score=score,
            eligibility=eligibility,
            counts=counts,
            generated_at=score.generated_at,
        )
        self.assessments.save(
            company_id=company["id"],
            tender_id=tender_id,
            payload=result.model_dump(mode="json"),
        )
        return result

    def evidence_for_requirement(
        self, *, tender_id: str, requirement_id: str, company: dict
    ) -> RequirementEvidenceOut:
        requirement = self.requirements.find_for_company(requirement_id, company["id"])
        if not requirement or requirement.get("tender_id") != tender_id:
            raise NotFoundError("Requirement not found.")
        documents = self._company_documents(company["id"])
        candidates = evidence_candidates(company, requirement, documents)
        decision = self.evidence.find_for_requirement(requirement_id, company["id"])
        selected = None
        if decision:
            selected = next(
                (item for item in documents if item["id"] == decision.get("document_id")),
                None,
            )
        status = decision.get("status") if decision else ("suggested" if candidates else "none")
        return RequirementEvidenceOut(
            requirement_id=requirement_id,
            status=status or "none",
            document_id=decision.get("document_id") if decision else None,
            document_title=(selected or {}).get("title"),
            note=decision.get("note") if decision else None,
            candidates=candidates,
        )

    def decide_evidence(
        self,
        *,
        tender_id: str,
        requirement_id: str,
        company: dict,
        user_id: str,
        payload: EvidenceDecision,
    ) -> RequirementEvidenceOut:
        requirement = self.requirements.find_for_company(requirement_id, company["id"])
        if not requirement or requirement.get("tender_id") != tender_id:
            raise NotFoundError("Requirement not found.")
        document = self.documents.find_for_company(payload.document_id, company["id"])
        if not document:
            raise NotFoundError("Evidence document not found.")

        self.evidence.upsert_decision(
            company_id=company["id"],
            tender_id=requirement["tender_id"],
            requirement_id=requirement_id,
            document_id=document["id"],
            status=payload.status,
            note=payload.note,
            user_id=user_id,
        )
        self.audit.log(
            company_id=company["id"],
            actor_user_id=user_id,
            action="evidence.decision",
            entity_type="requirement",
            entity_id=requirement_id,
            metadata={"document_id": document["id"], "status": payload.status},
        )
        return self.evidence_for_requirement(
            tender_id=tender_id, requirement_id=requirement_id, company=company
        )

    def list_legal_obligations(
        self, *, tender_id: str, company_id: str
    ) -> list[LegalObligationOut]:
        self._tender(tender_id, company_id)
        requirements = self._requirements(company_id, tender_id)
        items: list[LegalObligationOut] = []
        for requirement in requirements:
            if (
                requirement.get("category") not in {"compliance", "performance"}
                and not requirement.get("consequence_text")
            ):
                continue
            items.append(
                LegalObligationOut(
                    requirement_id=requirement["id"],
                    title=requirement.get("title") or "Untitled obligation",
                    category=requirement.get("category") or "other",
                    obligation=requirement.get("obligation") or "",
                    excerpt=requirement.get("excerpt") or "",
                    page_index=int(requirement.get("page_index") or 1),
                    printed_page=requirement.get("printed_page"),
                    clause_reference=requirement.get("clause_reference"),
                    document_title=requirement.get("document_title"),
                    deadline_text=requirement.get("deadline_text"),
                    consequence_text=requirement.get("consequence_text"),
                    verification_status=requirement.get("verification_status") or "unverified",
                    source_url=requirement.get("source_url"),
                )
            )
        return items

    def generate_checklist(
        self, *, tender_id: str, company: dict, user_id: str
    ) -> tuple[list[dict], int, int]:
        tender = self._tender(tender_id, company["id"])
        requirements = self._requirements(company["id"], tender_id)
        documents = self._company_documents(company["id"])
        evidence_map = self.evidence.find_for_requirements(
            [item["id"] for item in requirements], company["id"]
        )
        documents_by_id = {item["id"]: item for item in documents}
        created: list[dict] = []
        skipped = 0

        for requirement in requirements:
            if _is_post_award(requirement):
                continue
            if not (
                requirement.get("mandatory") == "yes"
                or requirement.get("category") in CHECKLIST_CATEGORIES
                or requirement.get("form_reference")
            ):
                continue

            decision = evidence_map.get(requirement["id"])
            confirmed = None
            if decision and decision.get("status") == "confirmed":
                confirmed = documents_by_id.get(decision.get("document_id"))
            evidence_check = "No company evidence confirmed for this requirement."
            if confirmed:
                evidence_check = f"Confirmed evidence: {confirmed.get('title')}"
                if confirmed.get("expiry_date"):
                    evidence_check += f" (expires {_as_date(confirmed['expiry_date'])})"
            elif decision and decision.get("status") == "contradicted":
                evidence_check = "A reviewer marked the selected evidence as contradicting this requirement."

            if requirement.get("category") in {
                "submission",
                "eligibility",
                "technical",
                "financial",
            }:
                due_at = tender.get("deadline")
                trigger = requirement.get("deadline_text") or (
                    "Before the tender submission deadline" if due_at else None
                )
            else:
                # Performance/compliance obligations can fall after award. Keep
                # the cited trigger and do not invent a submission deadline.
                due_at = None
                trigger = requirement.get("deadline_text")
            values = {
                "company_id": company["id"],
                "tender_id": tender_id,
                "requirement_id": requirement["id"],
                "title": requirement.get("title") or "Untitled requirement",
                "category": requirement.get("category") or "other",
                "phase": "pre_award",
                "trigger_type": "before_submission",
                "action": requirement.get("obligation") or "",
                "acceptance_criteria": requirement.get("excerpt") or "",
                "evidence_check": evidence_check,
                "issuer": tender.get("authority"),
                "signatory": None,
                "deadline_text": requirement.get("deadline_text"),
                "trigger": trigger,
                "consequence": requirement.get("consequence_text"),
                "source_document_title": requirement.get("document_title"),
                "page_index": int(requirement.get("page_index") or 1),
                "printed_page": requirement.get("printed_page"),
                "clause_reference": requirement.get("clause_reference"),
                "excerpt": requirement.get("excerpt") or "",
                "source_url": requirement.get("source_url"),
                "source_retrieved_at": requirement.get("document_retrieved_at"),
                "status": "in_progress" if confirmed else "missing",
                "owner": None,
                "due_at": due_at,
            }
            task, was_created = self.checklist.create_generated(values)
            if was_created:
                created.append(task)
            else:
                skipped += 1

        self.audit.log(
            company_id=company["id"],
            actor_user_id=user_id,
            action="checklist.generated",
            entity_type="tender",
            entity_id=tender_id,
            metadata={"created": len(created), "skipped": skipped},
        )
        return created, skipped, len(created) + skipped

    def generate_obligations(
        self, *, tender_id: str, company: dict, user_id: str
    ) -> tuple[list[dict], int, int]:
        tender = self._tender(tender_id, company["id"])
        requirements = self._requirements(company["id"], tender_id)
        documents = self._company_documents(company["id"])
        evidence_map = self.evidence.find_for_requirements(
            [item["id"] for item in requirements], company["id"]
        )
        documents_by_id = {item["id"]: item for item in documents}
        created: list[dict] = []
        skipped = 0

        for requirement in requirements:
            if not _is_post_award(requirement):
                continue
            decision = evidence_map.get(requirement["id"])
            confirmed = None
            if decision and decision.get("status") == "confirmed":
                confirmed = documents_by_id.get(decision.get("document_id"))
            evidence_check = "No company evidence confirmed for this obligation."
            if confirmed:
                evidence_check = f"Confirmed evidence: {confirmed.get('title')}"
                if confirmed.get("expiry_date"):
                    evidence_check += f" (expires {_as_date(confirmed['expiry_date'])})"
            values = {
                "company_id": company["id"],
                "tender_id": tender_id,
                "requirement_id": requirement["id"],
                "title": requirement.get("title") or "Untitled obligation",
                "category": requirement.get("category") or "other",
                "phase": "post_award",
                "trigger_type": _post_award_trigger_type(requirement),
                "action": requirement.get("obligation") or "",
                "acceptance_criteria": requirement.get("excerpt") or "",
                "evidence_check": evidence_check,
                "issuer": tender.get("authority"),
                "signatory": None,
                "deadline_text": requirement.get("deadline_text"),
                "trigger": requirement.get("deadline_text"),
                "consequence": requirement.get("consequence_text"),
                "source_document_title": requirement.get("document_title"),
                "page_index": int(requirement.get("page_index") or 1),
                "printed_page": requirement.get("printed_page"),
                "clause_reference": requirement.get("clause_reference"),
                "excerpt": requirement.get("excerpt") or "",
                "source_url": requirement.get("source_url"),
                "source_retrieved_at": requirement.get("document_retrieved_at"),
                "status": "in_progress" if confirmed else "missing",
                "owner": None,
                "due_at": None,
            }
            task, was_created = self.checklist.create_generated(values)
            if was_created:
                created.append(task)
            else:
                skipped += 1

        self.audit.log(
            company_id=company["id"],
            actor_user_id=user_id,
            action="obligations.generated",
            entity_type="tender",
            entity_id=tender_id,
            metadata={"created": len(created), "skipped": skipped},
        )
        return created, skipped, len(created) + skipped

    def list_tasks(
        self, *, tender_id: str, company_id: str, phase: str | None = None
    ) -> tuple[list[dict], int]:
        self._tender(tender_id, company_id)
        return self.checklist.list_for_tender(
            company_id, tender_id, limit=300, offset=0, phase=phase
        )

    def update_task(
        self, *, task_id: str, company_id: str, user_id: str, changes: dict
    ) -> dict:
        existing = self.checklist.collection.find_one(
            {"_id": task_id, "company_id": company_id}
        )
        if not existing:
            raise NotFoundError("Checklist task not found.")
        updated = self.checklist.update_for_company(task_id, company_id, changes)
        if not updated:
            raise NotFoundError("Checklist task not found.")
        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="checklist.updated",
            entity_type="checklist_task",
            entity_id=task_id,
            metadata={"fields": sorted(changes)},
        )
        return ChecklistTaskOut.model_validate(updated).model_dump()
