"""The tender analysis pipeline: a job with visible steps.

The pipeline is registered as steps so the shape of the work is visible before
every agent exists. A step with no handler reports "not available yet" instead
of pretending to have run.

The steps are:

``requirements``    read the tender document and propose cited requirements
                    (the model proposes, the quote gate decides)
``recommendations`` propose what the company should do, grounded in the
                    requirements that passed the gate
``verification``    check the proposals against the company's own records; the
                    verdict stays with the deterministic assessment
``legal_research``  read official legal sources for the clauses that matter
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.database import Database
from app.core.exceptions import NotFoundError, ValidationError
from app.integrations.ai import build_ai_provider
from app.integrations.tinyfish import TinyFishClient
from app.models.jobs import JobOut
from app.repositories.agents import LegalSourceRepository, RecommendationRepository
from app.repositories.assessment import EvidenceRepository
from app.repositories.companies import CompanyRepository
from app.repositories.documents import DocumentRepository
from app.repositories.jobs import JobRepository
from app.repositories.tender_documents import RequirementRepository, TenderDocumentRepository
from app.repositories.tenders import ChecklistRepository, TenderRepository
from app.services.agents.legal_researcher import LegalResearcher
from app.services.agents.recommender import Recommender
from app.services.agents.verifier import Verifier
from app.services.job_runner import JobContext, JobRunner
from app.services.storage import StorageService

ANALYSIS_STEPS = (
    {"key": "requirements", "label": "Read the tender document"},
    {"key": "recommendations", "label": "Recommend what to do"},
    {"key": "verification", "label": "Check against our records"},
    {"key": "legal_research", "label": "Research official legal sources"},
)

# Only these clauses are worth legal research: the ones that impose an
# obligation on the contractor.
LEGAL_RELEVANT_CATEGORIES = {"compliance", "performance", "financial", "eligibility"}


def _verified_requirements(db: Database, company_id: str, tender_id: str) -> list[dict]:
    requirements, _total = RequirementRepository(db).list_for_tender(
        company_id, tender_id, limit=300
    )
    return [
        item
        for item in requirements
        if (item.get("verification_status") or "") in {"verified", "needs_review"}
    ]


def _tender_context(db: Database, tender_id: str, company_id: str) -> dict:
    tender = TenderRepository(db).find_for_company(tender_id, company_id)
    if not tender:
        raise NotFoundError("Tender not found.")
    company = CompanyRepository(db).find_by_id(company_id) or {"id": company_id}
    requirements = _verified_requirements(db, company_id, tender_id)
    documents, _document_total = DocumentRepository(db).list_for_company(
        company_id, limit=200
    )
    decisions = EvidenceRepository(db).find_for_requirements(
        [item["id"] for item in requirements], company_id
    )
    deadline = tender.get("deadline")
    if isinstance(deadline, str):
        deadline = datetime.fromisoformat(deadline)
    return {
        "tender": tender,
        "company": company,
        "requirements": requirements,
        "documents": documents,
        "decisions": decisions,
        "deadline": deadline,
    }


def requirements_step(context: JobContext) -> dict:
    """Extract cited requirements from the tender's documents."""
    from app.services.requirement_service import RequirementService

    settings = get_settings()
    service = RequirementService(
        context.db,
        StorageService(settings.storage_dir, settings.max_upload_mb),
        ai=build_ai_provider(settings),
        settings=settings,
    )
    tender_id = context.tender_id
    company_id = context.company_id
    if not tender_id or not company_id:
        raise ValueError("The job has no tender to analyse.")

    documents = service.list_documents(tender_id, company_id)
    user_id = (context.payload or {}).get("user_id")
    total = 0
    read = 0
    for document in documents:
        if document.get("status") != "extracted" or not document.get("text_page_count"):
            continue
        response = service.extract_requirements(
            document_id=document["id"],
            company_id=company_id,
            user_id=user_id or "system",
            replace=False,
        )
        read += 1
        total += getattr(response, "created", 0) or 0
    return {"documents": read, "requirements": total}


def recommendations_step(context: JobContext) -> dict:
    """Agent 1: propose what the company should do, then let the gate judge it."""
    settings = get_settings()
    tender_id = context.tender_id
    company_id = context.company_id
    if not tender_id or not company_id:
        raise ValueError("The job has no tender to analyse.")

    state = _tender_context(context.db, tender_id, company_id)
    recommender = Recommender(build_ai_provider(settings))
    proposals = recommender.propose(
        tender=state["tender"],
        company=state["company"],
        requirements=state["requirements"],
        company_documents=state["documents"],
        evidence_decisions=state["decisions"],
        deadline=state["deadline"],
    )
    repository = RecommendationRepository(context.db)
    stored = repository.replace_for_tender(
        company_id,
        tender_id,
        [
            {
                "company_id": company_id,
                "tender_id": tender_id,
                "model": build_ai_provider(settings).model,
                "prompt_version": "recommendations-v1",
                **proposal,
            }
            for proposal in proposals
        ],
        origin="recommendations",
    )
    grounded = sum(1 for item in stored if item.get("grounding_status") == "grounded")
    return {
        "proposed": len(stored),
        "grounded": grounded,
        "rejected": len(stored) - grounded,
    }


def verification_step(context: JobContext) -> dict:
    """Agent 2: explain the deterministic verdict and propose the next step."""
    from app.services.assessment import AssessmentService

    settings = get_settings()
    tender_id = context.tender_id
    company_id = context.company_id
    if not tender_id or not company_id:
        raise ValueError("The job has no tender to analyse.")

    state = _tender_context(context.db, tender_id, company_id)
    assessment = AssessmentService(context.db).assess(
        tender_id=tender_id, company=state["company"]
    )
    items = [item.model_dump() for item in assessment.eligibility.items]
    verifier = Verifier(build_ai_provider(settings))
    proposals = verifier.verify(
        tender=state["tender"],
        company=state["company"],
        eligibility_items=items,
        company_documents=state["documents"],
        deadline=state["deadline"],
    )
    repository = RecommendationRepository(context.db)
    stored = repository.replace_for_tender(
        company_id,
        tender_id,
        [
            {
                "company_id": company_id,
                "tender_id": tender_id,
                "model": build_ai_provider(settings).model,
                "prompt_version": "verification-v1",
                **proposal,
            }
            for proposal in proposals
            if proposal.get("kind") == "verification"
        ],
        origin="verification",
    )
    grounded = sum(1 for item in stored if item.get("grounding_status") == "grounded")
    return {
        "clauses": len(items),
        "explained": len(stored),
        "grounded": grounded,
        "verdicts": {
            "pass": assessment.eligibility.pass_count,
            "fail": assessment.eligibility.fail_count,
            "unknown": assessment.eligibility.unknown_count,
        },
    }


def legal_research_step(context: JobContext) -> dict:
    """Agent 3: read official legal sources for the clauses that matter."""
    settings = get_settings()
    tender_id = context.tender_id
    company_id = context.company_id
    if not tender_id or not company_id:
        raise ValueError("The job has no tender to analyse.")

    state = _tender_context(context.db, tender_id, company_id)
    candidates = [
        item
        for item in state["requirements"]
        if (item.get("category") or "") in LEGAL_RELEVANT_CATEGORIES
    ][: settings.legal_research_max_clauses]

    researcher = LegalResearcher(
        ai=build_ai_provider(settings),
        client=TinyFishClient.from_settings(settings),
    )
    repository = LegalSourceRepository(context.db)
    found = 0
    refused = 0
    for requirement in candidates:
        try:
            provisions = researcher.research(
                company=state["company"],
                tender=state["tender"],
                requirement=requirement,
                company_documents=state["documents"],
                retrieved_at=datetime.now(tz=timezone.utc),
            )
        except Exception as exc:  # noqa: BLE001 - one clause must not stop the step
            refused += 1
            continue
        repository.replace_for_requirement(
            company_id,
            tender_id,
            requirement["id"],
            [
                {
                    "company_id": company_id,
                    "tender_id": tender_id,
                    "requirement_id": requirement["id"],
                    "model": build_ai_provider(settings).model,
                    "prompt_version": "legal-research-v1",
                    **provision,
                }
                for provision in provisions
            ],
        )
        found += len(provisions)
    return {
        "clauses": len(candidates),
        "provisions": found,
        "clauses_not_read": refused,
    }


def build_handlers() -> dict:
    """The step handlers the job worker runs."""
    return {
        "requirements": requirements_step,
        "recommendations": recommendations_step,
        "verification": verification_step,
        "legal_research": legal_research_step,
    }


class AnalysisService:
    """Starts and reports the analysis job for a tender."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.jobs = JobRepository(db)
        self.runner = JobRunner(db, handlers=build_handlers())

    def start(
        self,
        *,
        tender_id: str,
        company_id: str,
        user_id: str,
        document_id: str | None = None,
    ) -> JobOut:
        job = self.runner.enqueue(
            "tender_analysis",
            company_id,
            tender_id=tender_id,
            document_id=document_id,
            payload={"user_id": user_id},
            steps=list(ANALYSIS_STEPS),
        )
        return JobOut.model_validate(job)

    def latest(self, *, tender_id: str, company_id: str) -> JobOut | None:
        items, _ = self.jobs.list_for_company(company_id, limit=50)
        for item in items:
            if item.get("kind") == "tender_analysis" and item.get("tender_id") == tender_id:
                return JobOut.model_validate(item)
        return None

    def get(self, job_id: str, company_id: str) -> JobOut:
        job = self.jobs.find_for_company(job_id, company_id)
        if not job:
            raise NotFoundError("Job not found.")
        return JobOut.model_validate(job)

    # ------------------------------------------------------------- proposals
    def recommendations(
        self, company_id: str, tender_id: str, *, kind: str | None = None
    ) -> list[dict]:
        return RecommendationRepository(self.db).list_for_tender(
            company_id, tender_id, kind=kind
        )

    def legal_sources(self, company_id: str, tender_id: str) -> list[dict]:
        return LegalSourceRepository(self.db).list_for_tender(company_id, tender_id)

    def apply_recommendation(
        self,
        *,
        company_id: str,
        tender_id: str,
        recommendation_id: str,
        owner: str | None = None,
        due_at: datetime | None = None,
        title: str | None = None,
    ) -> dict:
        """Turn a proposal into a real checklist task. A human confirms it."""
        repository = RecommendationRepository(self.db)
        recommendation = repository.find_for_company(recommendation_id, company_id)
        if not recommendation or recommendation.get("tender_id") != tender_id:
            raise NotFoundError("Recommendation not found.")
        if recommendation.get("grounding_status") != "grounded":
            raise ValidationError(
                "This proposal was not grounded in a verified clause, so it cannot "
                "become a task."
            )
        proposed = recommendation.get("proposed_task") or {}
        grounded = recommendation.get("grounded_requirements") or []
        requirement_id = proposed.get("requirement_id") or (grounded[0] if grounded else None)
        if not requirement_id:
            raise ValidationError("This proposal does not point at a clause.")

        requirement = RequirementRepository(self.db).find_for_company(
            requirement_id, company_id
        )
        if not requirement:
            raise NotFoundError("The clause behind this proposal was not found.")
        tender = TenderRepository(self.db).find_for_company(tender_id, company_id)
        if not tender:
            raise NotFoundError("Tender not found.")

        task, _created = ChecklistRepository(self.db).create_generated(
            {
                "company_id": company_id,
                "tender_id": tender_id,
                "requirement_id": requirement_id,
                "kind": "other",
                "title": (title or proposed.get("title") or recommendation.get("title") or "Task")[:200],
                "category": requirement.get("category") or "other",
                "phase": "pre_award",
                "action": proposed.get("action") or recommendation.get("action"),
                "acceptance_criteria": proposed.get("acceptance_criteria")
                or recommendation.get("acceptance_criteria"),
                "evidence_check": recommendation.get("claim"),
                "issuer": tender.get("authority"),
                "signatory": None,
                "deadline_text": requirement.get("deadline_text"),
                "trigger": requirement.get("deadline_text"),
                "consequence": requirement.get("consequence_text"),
                "source_document_title": requirement.get("document_title"),
                "page_index": int(requirement.get("page_index") or 1),
                "printed_page": requirement.get("printed_page"),
                "clause_reference": requirement.get("clause_reference"),
                "excerpt": requirement.get("excerpt"),
                "source_url": requirement.get("source_url"),
                "source_retrieved_at": requirement.get("document_retrieved_at"),
                "status": "missing",
                "owner": owner or proposed.get("owner"),
                "due_at": due_at or proposed.get("due_at"),
                "origin": "agent_recommendation",
                "recommendation_id": recommendation_id,
            }
        )
        repository.update(
            recommendation_id,
            company_id,
            {"applied_task_id": task["id"], "applied_at": datetime.now(tz=timezone.utc)},
        )
        return task
