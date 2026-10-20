from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from app.core.database import Database, utcnow
from app.core.exceptions import NotFoundError
from app.models.workflow import ReminderListResponse, ReminderOut
from app.repositories.companies import CompanyRepository
from app.repositories.documents import DocumentRepository
from app.repositories.tenders import ChecklistRepository, TenderRepository
from app.repositories.users import UserRepository
from app.repositories.workflow import ReminderRepository
from app.services.email import EmailService

ACTIVE_TENDER_STATUSES = {"saved", "preparing", "submitted"}
CLOSED_TASK_STATUSES = {"complete", "not_applicable"}
DOCUMENT_LEAD_DAYS = (30, 7, 1)


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    return None


def _date_text(value: date | datetime) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%d %b %Y")
    return value.strftime("%d %b %Y")


def _lead_days(company: dict) -> list[int]:
    raw = company.get("reminder_lead_days") or [7, 3, 1]
    days = sorted({int(day) for day in raw if 1 <= int(day) <= 90}, reverse=True)
    return days or [7, 3, 1]


class ReminderService:
    def __init__(self, db: Database, *, email: EmailService | None = None) -> None:
        self.db = db
        self.companies = CompanyRepository(db)
        self.tenders = TenderRepository(db)
        self.tasks = ChecklistRepository(db)
        self.documents = DocumentRepository(db)
        self.users = UserRepository(db)
        self.reminders = ReminderRepository(db)
        self.email = email or EmailService()

    def sync(self, company: dict) -> int:
        company_id = company["id"]
        lead_days = _lead_days(company)
        keys: set[str] = set()

        tenders, _ = self.tenders.list_for_company(company_id, limit=100)
        for tender in tenders:
            if tender.get("status") not in ACTIVE_TENDER_STATUSES:
                continue
            deadline = tender.get("deadline")
            if not isinstance(deadline, datetime):
                continue
            for lead in lead_days:
                key = f"tender:{tender['id']}:deadline:{lead}"
                keys.add(key)
                self.reminders.upsert_generated(
                    {
                        "company_id": company_id,
                        "reminder_key": key,
                        "type": "deadline",
                        "title": f"Tender deadline in {lead} day{'s' if lead != 1 else ''}: {tender.get('title') or 'Untitled tender'}",
                        "body": (
                            f"{tender.get('title') or 'Untitled tender'} closes on "
                            f"{_date_text(deadline)}. Source: {tender.get('source_url') or 'not recorded'}."
                        ),
                        "due_at": deadline - timedelta(days=lead),
                        "href": f"/app/tenders/{tender['id']}",
                        "tender_id": tender["id"],
                        "task_id": None,
                        "document_id": None,
                        "lead_days": lead,
                    }
                )

        tasks, _ = self.tasks.list_for_company(company_id, limit=500)
        for task in tasks:
            if task.get("status") in CLOSED_TASK_STATUSES:
                continue
            due_at = task.get("due_at")
            if not isinstance(due_at, datetime):
                continue
            for lead in lead_days:
                key = f"task:{task['id']}:due:{lead}"
                keys.add(key)
                href = (
                    f"/app/tenders/{task.get('tender_id')}?tab=tasks"
                    if task.get("tender_id")
                    else "/app/checklist"
                )
                self.reminders.upsert_generated(
                    {
                        "company_id": company_id,
                        "reminder_key": key,
                        "type": "task",
                        "title": f"Task due in {lead} day{'s' if lead != 1 else ''}: {task.get('title') or 'Checklist task'}",
                        "body": (
                            f"Complete '{task.get('title') or 'Checklist task'}' by "
                            f"{_date_text(due_at)}. Evidence check: "
                            f"{task.get('evidence_check') or 'not recorded'}."
                        ),
                        "due_at": due_at - timedelta(days=lead),
                        "href": href,
                        "tender_id": task.get("tender_id"),
                        "task_id": task["id"],
                        "document_id": None,
                        "lead_days": lead,
                    }
                )

        documents, _ = self.documents.list_for_company(company_id, limit=200)
        today = utcnow().date()
        for document in documents:
            expiry = _as_date(document.get("expiry_date"))
            if not expiry or expiry < today:
                continue
            if document.get("verification_status") in {"rejected", "expired"}:
                continue
            expiry_at = datetime.combine(expiry, time(9, 0), tzinfo=timezone.utc)
            for lead in sorted(set(DOCUMENT_LEAD_DAYS) | set(lead_days), reverse=True):
                key = f"document:{document['id']}:expiry:{lead}"
                keys.add(key)
                self.reminders.upsert_generated(
                    {
                        "company_id": company_id,
                        "reminder_key": key,
                        "type": "document_expiry",
                        "title": f"Evidence expires in {lead} day{'s' if lead != 1 else ''}: {document.get('title') or 'Company document'}",
                        "body": (
                            f"{document.get('title') or 'Company document'} expires on "
                            f"{_date_text(expiry)}. Replace or renew it before relying on it "
                            "as eligibility evidence."
                        ),
                        "due_at": expiry_at - timedelta(days=lead),
                        "href": "/app/documents",
                        "tender_id": None,
                        "task_id": None,
                        "document_id": document["id"],
                        "lead_days": lead,
                    }
                )

        self.reminders.mark_inactive_except(company_id, keys)
        return len(keys)

    def list(
        self, company: dict, *, status: str | None = None, limit: int = 100, offset: int = 0
    ) -> ReminderListResponse:
        self.sync(company)
        items, total = self.reminders.list_for_company(
            company["id"], limit=limit, offset=offset, status=status
        )
        return ReminderListResponse(
            items=[ReminderOut.model_validate(item) for item in items],
            total=total,
            email_enabled=bool(company.get("reminder_email_enabled")),
            email_configured=self.email.configured,
        )

    def update(self, *, reminder_id: str, company_id: str, status: str) -> ReminderOut:
        existing = self.reminders.find(reminder_id, company_id)
        if not existing:
            raise NotFoundError("Reminder not found.")
        updated = self.reminders.update_status(reminder_id, company_id, status)
        if not updated:
            raise NotFoundError("Reminder not found.")
        return ReminderOut.model_validate(updated)

    def send_due(
        self,
        *,
        dry_run: bool = True,
        now: datetime | None = None,
        limit: int = 100,
        email: EmailService | None = None,
    ) -> dict:
        current = now or utcnow()
        sender = email or self.email
        sent = 0
        failed = 0
        skipped = 0
        due_preview: list[dict] = []

        for company in self.companies.list_all():
            self.sync(company)
            if not company.get("reminder_email_enabled"):
                skipped += 1
                continue
            users = self.users.list_for_company(company["id"])
            if not users:
                skipped += 1
                continue
            recipient = users[0].get("email")
            if not recipient:
                skipped += 1
                continue

            if dry_run:
                for reminder in self.reminders.list_due_for_company(
                    company["id"], current, limit=limit
                ):
                    due_preview.append(
                        {
                            "company_id": company["id"],
                            "recipient": recipient,
                            "title": reminder["title"],
                            "due_at": reminder["due_at"],
                            "href": reminder["href"],
                        }
                    )
                continue

            for _ in range(max(limit, 1)):
                reminder = self.reminders.claim_due_for_company(company["id"], current)
                if not reminder:
                    break
                try:
                    sender.send_reminder(
                        to=recipient,
                        title=reminder["title"],
                        body=(
                            reminder["body"]
                            + f"\nOpen in BidKaro: {reminder['href']}"
                            + "\n\nThis is an automated reminder from your BidKaro workspace."
                        ),
                    )
                except Exception as exc:  # noqa: BLE001 - persisted for the operator
                    self.reminders.mark_failed(
                        reminder["id"], company["id"], str(exc), current
                    )
                    failed += 1
                else:
                    self.reminders.mark_sent(reminder["id"], company["id"], current)
                    sent += 1

        return {
            "dry_run": dry_run,
            "sent": sent,
            "failed": failed,
            "companies_skipped": skipped,
            "due": due_preview,
        }
