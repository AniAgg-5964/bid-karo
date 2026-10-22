"""The Action Inbox.

One prioritised list of the things that actually need a person, computed from
the records the company owns:

* a mandatory criterion that failed, or that is still unresolved;
* a change to a tender that nobody has reviewed;
* a deadline that is close;
* a reminder that is due;
* a source that has never been checked, or that has gone stale;
* evidence that is about to expire.

The order is by consequence and by date, not by a made-up urgency score. An
item that does not exist in the data is not in the list, and an item that is
resolved is not in the list either.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from app.core.database import Database
from app.repositories.assessment import EvidenceRepository
from app.repositories.documents import DocumentRepository
from app.repositories.tenders import ChecklistRepository, TenderRepository
from app.repositories.workflow import ChangeRepository
from app.services.assessment import AssessmentService

InboxKind = Literal[
    "eligibility",
    "evidence",
    "change",
    "deadline",
    "reminder",
    "source",
]
InboxSeverity = Literal["info", "warning", "danger", "success"]

# A source that has not been checked for this long is treated as stale.
STALE_SOURCE_DAYS = 7
# Evidence inside this window is worth a look before it expires.
EVIDENCE_EXPIRY_DAYS = 30
MAX_ITEMS = 12


def _href(tender_id: str | None, tab: str = "") -> str:
    if not tender_id:
        return "/app/tenders"
    return f"/app/tenders/{tender_id}{f'?tab={tab}' if tab else ''}"


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


class InboxService:
    """Builds the Action Inbox from the company's own records."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.tenders = TenderRepository(db)
        self.documents = DocumentRepository(db)
        self.changes = ChangeRepository(db)
        self.tasks = ChecklistRepository(db)
        self.evidence = EvidenceRepository(db)
        self.assessment = AssessmentService(db)

    def build(self, company_id: str) -> dict[str, Any]:
        today = date.today()
        items: list[dict[str, Any]] = []

        items.extend(self._eligibility_items(company_id))
        items.extend(self._change_items(company_id))
        items.extend(self._deadline_items(company_id, today))
        items.extend(self._reminder_items(company_id, today))
        items.extend(self._source_items(company_id, today))
        items.extend(self._evidence_items(company_id, today))

        severity_rank = {"danger": 0, "warning": 1, "info": 2, "success": 3}
        items.sort(
            key=lambda item: (
                severity_rank.get(item["severity"], 4),
                item.get("due_at") or datetime.max.replace(tzinfo=timezone.utc),
            )
        )
        return {
            "items": items[:MAX_ITEMS],
            "total": len(items),
            "truncated": len(items) > MAX_ITEMS,
        }

    # ------------------------------------------------------------------ parts

    def _eligibility_items(self, company_id: str) -> list[dict[str, Any]]:
        """The mandatory criteria that failed, or that nobody has decided yet.

        One item per tender, not one per criterion: a reader wants to know
        which tender is blocked and by how much, and the criteria themselves
        are one click away.
        """
        items: list[dict[str, Any]] = []
        tenders, _total = self.tenders.list_for_company(company_id, limit=50)
        for tender in tenders:
            tender_id = tender.get("id")
            if not tender_id:
                continue
            try:
                result = self.assessment.assess(tender_id=tender_id, company={"id": company_id})
            except Exception:  # noqa: BLE001 - one tender must not break the list
                continue
            failed = [entry for entry in result.eligibility.items if entry.gate == "fail"]
            unknown = [entry for entry in result.eligibility.items if entry.gate == "unknown"]
            if not failed and not unknown:
                continue
            if failed:
                title = (
                    f"{len(failed)} mandatory "
                    f"{'criterion fails' if len(failed) == 1 else 'criteria fail'}"
                )
                description = failed[0].title or ""
                severity = "danger"
                action = "Review the evidence for this criterion"
            else:
                title = (
                    f"{len(unknown)} mandatory "
                    f"{'criterion needs' if len(unknown) == 1 else 'criteria need'} a decision"
                )
                description = unknown[0].title or ""
                severity = "warning"
                action = "Confirm or reject the evidence"
            items.append(
                {
                    "id": f"eligibility-{tender_id}",
                    "kind": "eligibility",
                    "title": title,
                    "description": f"{tender.get('title') or 'Tender'}. {description}".strip(". "),
                    "href": _href(tender_id, "eligibility"),
                    "severity": severity,
                    "due_at": None,
                    "tender_id": tender_id,
                    "tender_title": tender.get("title"),
                    "action_label": action,
                }
            )
        return items

    def _change_items(self, company_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        changes, _total = self.changes.list_for_company(company_id, limit=50)
        for change in changes:
            if change.get("review_status") != "pending":
                continue
            items.append(
                {
                    "id": f"change-{change.get('id')}",
                    "kind": "change",
                    "title": change.get("summary") or "A tender changed",
                    "description": "The source of this tender was rechecked and something moved.",
                    "href": _href(change.get("tender_id"), "changes"),
                    "severity": change.get("severity") if change.get("severity") in {"warning", "danger"} else "info",
                    "due_at": change.get("detected_at"),
                    "tender_id": change.get("tender_id"),
                    "tender_title": change.get("tender_title"),
                    "action_label": "Review what changed",
                }
            )
        return items

    def _deadline_items(self, company_id: str, today: date) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        tasks, _total = self.tasks.list_for_company(company_id, limit=200)
        for task in tasks:
            if task.get("status") in {"done", "not_applicable"}:
                continue
            due_at = task.get("due_at")
            due_date = _as_date(due_at)
            if not due_date:
                continue
            days = (due_date - today).days
            if days > 30:
                continue
            items.append(
                {
                    "id": f"deadline-{task.get('id')}",
                    "kind": "deadline",
                    "title": task.get("title") or "Checklist task",
                    "description": (
                        "Due today." if days == 0 else f"Due in {days} day(s)."
                    ),
                    "href": _href(task.get("tender_id"), "tasks"),
                    "severity": "warning" if days <= 7 else "info",
                    "due_at": due_at if isinstance(due_at, datetime) else None,
                    "tender_id": task.get("tender_id"),
                    "tender_title": task.get("tender_title"),
                    "action_label": "Open the task",
                }
            )
        return items

    def _reminder_items(self, company_id: str, today: date) -> list[dict[str, Any]]:
        collection = self.db.db["reminders"]
        items: list[dict[str, Any]] = []
        for reminder in collection.find({"company_id": company_id}):
            if reminder.get("status") in {"done", "dismissed"}:
                continue
            due_at = reminder.get("due_at")
            due_date = _as_date(due_at)
            if not due_date or due_date > today + timedelta(days=14):
                continue
            items.append(
                {
                    "id": f"reminder-{reminder.get('_id')}",
                    "kind": "reminder",
                    "title": reminder.get("title") or "Reminder",
                    "description": reminder.get("reason") or "A deadline you set a reminder for.",
                    "href": "/app/reminders",
                    "severity": "info",
                    "due_at": due_at if isinstance(due_at, datetime) else None,
                    "tender_id": reminder.get("tender_id"),
                    "tender_title": reminder.get("tender_title"),
                    "action_label": "Open the reminder",
                }
            )
        return items

    def _source_items(self, company_id: str, today: date) -> list[dict[str, Any]]:
        """A source that was never checked, or that has gone stale."""
        items: list[dict[str, Any]] = []
        tenders, _total = self.tenders.list_for_company(company_id, limit=50)
        for tender in tenders:
            if not tender.get("source_url"):
                continue
            checked = tender.get("source_retrieved_at")
            checked_date = _as_date(checked)
            if checked_date is None:
                items.append(
                    {
                        "id": f"source-{tender.get('id')}",
                        "kind": "source",
                        "title": tender.get("title") or "Tender",
                        "description": "This tender's source has never been checked for changes.",
                        "href": _href(tender.get("id"), "changes"),
                        "severity": "info",
                        "due_at": None,
                        "tender_id": tender.get("id"),
                        "tender_title": tender.get("title"),
                        "action_label": "Check the source",
                    }
                )
                continue
            age = (today - checked_date).days
            if age <= STALE_SOURCE_DAYS:
                continue
            items.append(
                {
                    "id": f"source-{tender.get('id')}",
                    "kind": "source",
                    "title": tender.get("title") or "Tender",
                    "description": f"The source was last checked {age} days ago.",
                    "href": _href(tender.get("id"), "changes"),
                    "severity": "info",
                    "due_at": None,
                    "tender_id": tender.get("id"),
                    "tender_title": tender.get("title"),
                    "action_label": "Check the source again",
                }
            )
        return items

    def _evidence_items(self, company_id: str, today: date) -> list[dict[str, Any]]:
        limit_date = today + timedelta(days=EVIDENCE_EXPIRY_DAYS)
        items: list[dict[str, Any]] = []
        for document in self.documents.expiring_for_company(company_id, limit_date):
            expiry = _as_date(document.get("expiry_date"))
            if not expiry:
                continue
            days = (expiry - today).days
            items.append(
                {
                    "id": f"evidence-{document.get('id')}",
                    "kind": "evidence",
                    "title": document.get("title") or "Evidence document",
                    "description": (
                        f"This document expires in {days} day(s)."
                        if days >= 0
                        else "This document has expired."
                    ),
                    "href": "/app/documents",
                    "severity": "warning" if days <= 14 else "info",
                    "due_at": None,
                    "tender_id": None,
                    "tender_title": None,
                    "action_label": "Renew or replace it",
                }
            )
        return items
