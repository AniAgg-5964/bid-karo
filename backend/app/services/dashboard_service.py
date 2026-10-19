from __future__ import annotations

from datetime import timedelta

from app.core.database import Database, utcnow
from app.models.dashboard import (
    ActivityItem,
    DashboardMetrics,
    DashboardSummary,
    DeadlineItem,
    PriorityAction,
    TenderCard,
)
from app.models.company import calculate_profile_completeness
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.repositories.tenders import ChangeRepository, ChecklistRepository, TenderRepository

ACTIVITY_LABELS = {
    "auth.registered": "Account created",
    "company.updated": "Company profile updated",
    "document.uploaded": "Evidence document uploaded",
    "document.deleted": "Evidence document removed",
    "tender.saved": "Tender saved",
    "checklist.updated": "Checklist task updated",
}


class DashboardService:
    def __init__(self, db: Database) -> None:
        self.tenders = TenderRepository(db)
        self.tasks = ChecklistRepository(db)
        self.changes = ChangeRepository(db)
        self.documents = DocumentRepository(db)
        self.audit = AuditRepository(db)

    def summary(self, *, user: dict, company: dict) -> DashboardSummary:
        company_id = company["id"]
        now = utcnow()
        horizon = now + timedelta(days=14)

        active_bids = self.tenders.count_active(company_id)
        open_tasks = self.tasks.count_open(company_id)
        deadlines = self.tasks.count_upcoming(company_id, now, horizon)
        document_count = self.documents.count_for_company(company_id)
        pending_changes = self.changes.count_pending(company_id)
        completeness = calculate_profile_completeness(company)

        tenders, _ = self.tenders.list_for_company(company_id, limit=5)
        due_tasks = self.tasks.upcoming_for_company(company_id, now, horizon, limit=5)
        activity = self.audit.recent_for_company(company_id, limit=6)

        actions: list[PriorityAction] = []
        if completeness < 70 or not company.get("onboarding_completed"):
            actions.append(
                PriorityAction(
                    key="complete_profile",
                    title="Complete your company profile",
                    description="A stronger profile improves tender matching and evidence checks.",
                    href="/app/company",
                    tone="warning",
                )
            )
        if document_count == 0:
            actions.append(
                PriorityAction(
                    key="upload_evidence",
                    title="Add your first evidence document",
                    description="Upload registrations, financials or completion certificates.",
                    href="/app/documents",
                    tone="info",
                )
            )
        if active_bids == 0:
            actions.append(
                PriorityAction(
                    key="discover_tender",
                    title="Discover your first tender",
                    description="Search an official source once TinyFish discovery is configured.",
                    href="/app/discover",
                    tone="info",
                )
            )
        if deadlines:
            actions.append(
                PriorityAction(
                    key="deadlines",
                    title=f"{deadlines} deadline{'s' if deadlines != 1 else ''} in the next 14 days",
                    description="Review tasks and confirm the evidence needed for submission.",
                    href="/app/checklist",
                    tone="danger",
                )
            )
        if pending_changes:
            actions.append(
                PriorityAction(
                    key="changes",
                    title=f"{pending_changes} tender change{'s' if pending_changes != 1 else ''} need review",
                    description="Compare the updated source before acting on affected tasks.",
                    href="/app/changes",
                    tone="warning",
                )
            )

        return DashboardSummary(
            company_name=company["name"],
            user_name=user["full_name"],
            profile_completeness=completeness,
            onboarding_completed=bool(company.get("onboarding_completed")),
            metrics=DashboardMetrics(
                active_bids=active_bids,
                open_tasks=open_tasks,
                upcoming_deadlines=deadlines,
                evidence_documents=document_count,
                pending_changes=pending_changes,
            ),
            priority_actions=actions[:4],
            recent_tenders=[self.to_tender_card(item) for item in tenders],
            recent_activity=[self._activity(item) for item in activity],
            upcoming_deadlines=[
                DeadlineItem(
                    id=item["id"],
                    title=item.get("title") or "Checklist task",
                    due_at=item["due_at"],
                    status=item.get("status", "missing"),
                    href=f"/app/tenders/{item.get('tender_id')}?tab=tasks"
                    if item.get("tender_id")
                    else "/app/checklist",
                )
                for item in due_tasks
            ],
        )

    def to_tender_card(self, item: dict) -> TenderCard:
        return TenderCard(
            id=item["id"],
            title=item.get("title") or "Untitled tender",
            authority=item.get("authority"),
            reference_number=item.get("reference_number"),
            deadline=item.get("deadline"),
            status=item.get("status", "saved"),
            source_url=item.get("source_url"),
            created_at=item["created_at"],
        )

    def _activity(self, item: dict) -> ActivityItem:
        action = item.get("action", "")
        label = ACTIVITY_LABELS.get(action, action.replace(".", " ").capitalize())
        return ActivityItem(
            id=item["id"],
            action=action,
            entity_type=item.get("entity_type", "record"),
            summary=label,
            created_at=item["created_at"],
        )
