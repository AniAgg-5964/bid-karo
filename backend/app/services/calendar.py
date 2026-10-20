from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from app.core.database import Database, utcnow
from app.core.exceptions import NotFoundError
from app.repositories.tenders import ChecklistRepository, TenderRepository

CALENDAR_STATUSES = {"saved", "preparing", "submitted"}


def _escape(value: str | None) -> str:
    text = (value or "").replace("\\", "\\\\")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(";", "\\;").replace(",", "\\,")
    return text.replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545 line folding at 75 octets, preserving UTF-8 characters."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    chunks: list[bytes] = []
    current = b""
    for char in line:
        piece = char.encode("utf-8")
        if len(current) + len(piece) > 73:
            chunks.append(current)
            current = b" " + piece
        else:
            current += piece
    if current:
        chunks.append(current)
    return "\r\n".join(chunk.decode("utf-8") for chunk in chunks)


def _retrieved_text(value) -> str:
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    return "not recorded"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_date_only(value: datetime) -> bool:
    utc = _utc(value)
    return utc.time() == time(12, 0)


def _date_line(prefix: str, value: datetime) -> str:
    utc = _utc(value)
    if _is_date_only(value):
        return f"{prefix};VALUE=DATE:{utc.strftime('%Y%m%d')}"
    return f"{prefix}:{utc.strftime('%Y%m%dT%H%M%SZ')}"


def _event(
    *,
    uid: str,
    summary: str,
    due_at: datetime,
    description: str,
    url: str | None = None,
) -> list[str]:
    stamp = _utc(utcnow()).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VEVENT",
        f"UID:{_escape(uid)}",
        f"DTSTAMP:{stamp}",
        _date_line("DTSTART", due_at),
    ]
    if _is_date_only(due_at):
        lines.append(_date_line("DTEND", due_at + timedelta(days=1)))
    else:
        lines.append(_date_line("DTEND", due_at + timedelta(hours=1)))
    lines.extend(
        [
            f"SUMMARY:{_escape(summary)}",
            f"DESCRIPTION:{_escape(description)}",
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
        ]
    )
    if url:
        lines.append(f"URL:{_escape(url)}")
    lines.extend(
        [
            "BEGIN:VALARM",
            "TRIGGER:-P1D",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_escape(summary)}",
            "END:VALARM",
            "END:VEVENT",
        ]
    )
    return lines


def _wrap(name: str, events: list[list[str]]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//BidKaro//Tender calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
        "X-WR-TIMEZONE:UTC",
    ]
    for event in events:
        lines.extend(event)
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


class CalendarService:
    def __init__(self, db: Database) -> None:
        self.tenders = TenderRepository(db)
        self.tasks = ChecklistRepository(db)

    def _tender_events(self, tender: dict) -> list[list[str]]:
        events: list[list[str]] = []
        deadline = tender.get("deadline")
        if isinstance(deadline, datetime):
            description = (
                f"Tender: {tender.get('title') or 'Untitled tender'}\n"
                f"Authority: {tender.get('authority') or 'not stated'}\n"
                f"Reference: {tender.get('reference_number') or 'not stated'}\n"
                f"Source: {tender.get('source_url') or 'not recorded'}\n"
                f"Source retrieved: {_retrieved_text(tender.get('source_retrieved_at'))}\n"
                "Deadline from the recorded source. Confirm details on the official portal."
            )
            events.append(
                _event(
                    uid=f"tender-{tender['id']}-deadline@bidkaro",
                    summary=f"Tender deadline: {tender.get('title') or 'Untitled tender'}",
                    due_at=deadline,
                    description=description,
                    url=tender.get("source_url"),
                )
            )
        return events

    def _task_events(self, task: dict) -> list[list[str]]:
        due_at = task.get("due_at")
        if not isinstance(due_at, datetime):
            return []
        citation = []
        if task.get("source_document_title"):
            citation.append(f"Document: {task['source_document_title']}")
        if task.get("page_index"):
            citation.append(f"Page: {task['page_index']}")
        if task.get("clause_reference"):
            citation.append(f"Clause: {task['clause_reference']}")
        if task.get("source_url"):
            citation.append(f"Source: {task['source_url']}")
        if task.get("source_retrieved_at"):
            citation.append(
                f"Source retrieved: {_retrieved_text(task['source_retrieved_at'])}"
            )
        if task.get("excerpt"):
            citation.append(f"Source excerpt: {task['excerpt']}")
        description = (
            f"Task: {task.get('title') or 'Checklist task'}\n"
            f"Status: {task.get('status') or 'missing'}\n"
            f"Action: {task.get('action') or 'not recorded'}\n"
            f"Evidence check: {task.get('evidence_check') or 'not recorded'}\n"
            + ("\n".join(citation) or "Citation: not recorded")
        )
        return [
            _event(
                uid=f"task-{task['id']}@bidkaro",
                summary=f"Bid task: {task.get('title') or 'Checklist task'}",
                due_at=due_at,
                description=description,
                url=task.get("source_url"),
            )
        ]

    def tender_calendar(self, *, company_id: str, tender_id: str) -> str:
        tender = self.tenders.find_for_company(tender_id, company_id)
        if not tender:
            raise NotFoundError("Tender not found.")
        tasks, _ = self.tasks.list_for_tender(
            company_id, tender_id, limit=500, offset=0
        )
        events = self._tender_events(tender)
        for task in tasks:
            events.extend(self._task_events(task))
        return _wrap(
            f"BidKaro - {tender.get('title') or 'Tender'}",
            events,
        )

    def company_calendar(self, *, company_id: str) -> str:
        tenders, _ = self.tenders.list_for_company(company_id, limit=100, offset=0)
        tasks, _ = self.tasks.list_for_company(company_id, limit=500, offset=0)
        events: list[list[str]] = []
        for tender in tenders:
            if tender.get("status") in CALENDAR_STATUSES:
                events.extend(self._tender_events(tender))
        for task in tasks:
            if task.get("status") in {"complete", "not_applicable"}:
                continue
            events.extend(self._task_events(task))
        return _wrap("BidKaro deadlines and tasks", events)
