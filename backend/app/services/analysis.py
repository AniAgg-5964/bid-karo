"""The tender analysis pipeline: a job with visible steps.

The pipeline is registered as steps so the shape of the work is visible before
every agent exists. A step with no handler reports "not available yet" instead
of pretending to have run.

The steps are:

``requirements``    read the tender document and propose cited requirements
                    (implemented: the existing extraction, gated by the
                    deterministic quote check)
``recommendations`` propose what the company should do, grounded in the
                    requirements that passed the gate
``verification``    check the proposals against the company's own records
``legal_research``  read official legal sources for the clauses that matter
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.database import Database
from app.core.exceptions import NotFoundError
from app.models.jobs import JobOut
from app.repositories.jobs import JobRepository
from app.services.job_runner import JobContext, JobRunner
from app.services.storage import StorageService

ANALYSIS_STEPS = (
    {"key": "requirements", "label": "Read the tender document"},
    {"key": "recommendations", "label": "Recommend what to do"},
    {"key": "verification", "label": "Check against our records"},
    {"key": "legal_research", "label": "Research official legal sources"},
)


def requirements_step(context: JobContext) -> dict:
    """Extract cited requirements from the tender's documents."""
    from app.integrations.ai import build_ai_provider
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


class AnalysisService:
    """Starts and reports the analysis job for a tender."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.jobs = JobRepository(db)
        self.runner = JobRunner(db, handlers={"requirements": requirements_step})

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
