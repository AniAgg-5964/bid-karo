from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timezone

from app.core.database import Database, utcnow
from app.core.exceptions import (
    NotConfiguredError,
    NotFoundError,
    UpstreamError,
    ValidationError,
)
from app.integrations.tinyfish import TinyFishClient, TinyFishError, TinyFishNotConfigured
from app.models.workflow import (
    ChangeOut,
    SnapshotCaptureResponse,
    TenderSnapshotOut,
)
from app.repositories.audit import AuditRepository
from app.repositories.tender_documents import RequirementRepository
from app.repositories.tenders import TenderRepository
from app.repositories.workflow import ChangeRepository, SnapshotRepository
from app.services.tender_extraction import extract_fields


SNAPSHOT_FIELDS = (
    "title",
    "authority",
    "reference_number",
    "deadline",
    "description",
    "source_url",
    "source_type",
    "value_amount",
    "value_currency",
    "location",
)

FIELD_LABELS = {
    "title": "Tender title",
    "authority": "Issuing authority",
    "reference_number": "Reference number",
    "deadline": "Submission deadline",
    "description": "Source summary",
    "source_url": "Source URL",
    "source_type": "Source type",
    "value_amount": "Contract value",
    "value_currency": "Value currency",
    "location": "Location",
}

SEVERITY = {
    "deadline": "warning",
    "reference_number": "warning",
    "title": "warning",
    "source_url": "warning",
}


def _parse_deadline(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    # Date-only source deadlines keep their calendar day in IST and elsewhere.
    return datetime.combine(parsed, time(12, 0), tzinfo=timezone.utc)


def _display(field: str, value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if field == "deadline":
            return value.date().isoformat()
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _snapshot_fields(tender: dict) -> dict[str, str | None]:
    discovered = tender.get("discovery_extracted") or {}
    values = {
        "title": tender.get("title"),
        "authority": tender.get("authority"),
        "reference_number": tender.get("reference_number"),
        "deadline": tender.get("deadline"),
        "description": tender.get("description"),
        "source_url": tender.get("source_url"),
        "source_type": tender.get("source_type"),
        "value_amount": discovered.get("value_amount"),
        "value_currency": discovered.get("value_currency"),
        "location": discovered.get("location"),
    }
    return {field: _display(field, values.get(field)) for field in SNAPSHOT_FIELDS}


def _fingerprint(fields: dict) -> str:
    payload = json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clip(value: str | None, limit: int = 180) -> str:
    text = (value or "not stated").strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _summary(field: str, old_value: str | None, new_value: str | None) -> str:
    label = FIELD_LABELS.get(field, field.replace("_", " ").title())
    if old_value is None and new_value is not None:
        return f"{label} added: {_clip(new_value)}"
    if old_value is not None and new_value is None:
        return f"{label} removed from the source"
    return f"{label} changed from {_clip(old_value)} to {_clip(new_value)}"


def _requirement_value(item: dict) -> str:
    title = (item.get("title") or "").strip() or "Untitled requirement"
    return title


def _requirement_diff(previous: dict, current: dict, *, tender: dict) -> list[dict]:
    """Compare the requirement set stored with each snapshot.

    Human review status is deliberately excluded: reviewing a requirement must
    not look like a source change. A re-extraction that adds, removes or
    rewrites a requirement does create a reviewable change.
    """
    old_items = {
        item.get("requirement_id"): item
        for item in previous.get("requirement_fingerprints") or []
        if item.get("requirement_id")
    }
    new_items = {
        item.get("requirement_id"): item
        for item in current.get("requirement_fingerprints") or []
        if item.get("requirement_id")
    }
    changes: list[dict] = []
    added = [new_items[key] for key in new_items.keys() - old_items.keys()]
    removed = [old_items[key] for key in old_items.keys() - new_items.keys()]
    updated = [
        (old_items[key], new_items[key])
        for key in old_items.keys() & new_items.keys()
        if _requirement_value(old_items[key]) != _requirement_value(new_items[key])
        or old_items[key].get("excerpt_key") != new_items[key].get("excerpt_key")
    ]

    def add(old_value: str | None, new_value: str | None, summary: str) -> None:
        changes.append(
            {
                "company_id": tender["company_id"],
                "tender_id": tender["id"],
                "tender_title": tender.get("title"),
                "field": "requirements",
                "old_value": old_value,
                "new_value": new_value,
                "summary": summary,
                "severity": "warning",
                "review_status": "pending",
                "from_snapshot_id": previous.get("id"),
                "to_snapshot_id": current.get("id"),
                "source_url": tender.get("source_url"),
                "detected_at": utcnow(),
            }
        )

    for item in added:
        label = _clip(_requirement_value(item), 120)
        add(None, label, f"Requirement added from the source: {label}")
    for item in removed:
        label = _clip(_requirement_value(item), 120)
        add(label, None, f"Requirement no longer stored for this tender: {label}")
    for old_item, new_item in updated:
        add(
            _clip(_requirement_value(old_item), 120),
            _clip(_requirement_value(new_item), 120),
            f"Stored requirement changed: {_clip(_requirement_value(new_item), 120)}",
        )
    return changes


def _diff(previous: dict | None, current: dict, *, tender: dict) -> list[dict]:
    if not previous:
        return []
    old_fields = previous.get("fields") or {}
    new_fields = current.get("fields") or {}
    changes: list[dict] = []
    for field in SNAPSHOT_FIELDS:
        old_value = old_fields.get(field)
        new_value = new_fields.get(field)
        if old_value == new_value:
            continue
        changes.append(
            {
                "company_id": tender["company_id"],
                "tender_id": tender["id"],
                "tender_title": tender.get("title"),
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "summary": _summary(field, old_value, new_value),
                "severity": SEVERITY.get(field, "info"),
                "review_status": "pending",
                "from_snapshot_id": previous.get("id"),
                "to_snapshot_id": current.get("id"),
                "source_url": tender.get("source_url"),
                "detected_at": utcnow(),
            }
        )
    changes.extend(_requirement_diff(previous, current, tender=tender))
    return changes


class WorkflowService:
    def __init__(self, db: Database, *, tinyfish: TinyFishClient | None = None) -> None:
        self.db = db
        self.tenders = TenderRepository(db)
        self.requirements = RequirementRepository(db)
        self.snapshots = SnapshotRepository(db)
        self.changes = ChangeRepository(db)
        self.audit = AuditRepository(db)
        self.tinyfish = tinyfish or TinyFishClient.from_settings()

    def _tender(self, tender_id: str, company_id: str) -> dict:
        tender = self.tenders.find_for_company(tender_id, company_id)
        if not tender:
            raise NotFoundError("Tender not found.")
        return tender

    def _build_snapshot(self, tender: dict) -> dict:
        fields = _snapshot_fields(tender)
        requirements, _ = self.requirements.list_for_tender(
            tender["company_id"], tender["id"], limit=300, offset=0
        )
        fingerprints = [
            {
                "requirement_id": item["id"],
                "title": item.get("title"),
                "excerpt_key": item.get("excerpt_key"),
                "verification_status": item.get("verification_status"),
            }
            for item in requirements
        ]
        return {
            "company_id": tender["company_id"],
            "tender_id": tender["id"],
            "source_url": tender.get("source_url"),
            # The hash covers both tender fields and the stored requirement set,
            # so a re-extraction is versioned even when tender fields are equal.
            "content_hash": _fingerprint(
                {
                    "fields": fields,
                    "requirements": sorted(
                        (
                            {
                                "requirement_id": item["requirement_id"],
                                "title": item.get("title"),
                                "excerpt_key": item.get("excerpt_key"),
                            }
                            for item in fingerprints
                        ),
                        key=lambda item: item["requirement_id"],
                    ),
                }
            ),
            "captured_at": utcnow(),
            "source_retrieved_at": tender.get("source_retrieved_at"),
            "fields": fields,
            "requirement_count": len(fingerprints),
            "requirement_fingerprints": fingerprints,
        }

    def capture_snapshot(
        self, *, tender_id: str, company_id: str, user_id: str | None = None
    ) -> SnapshotCaptureResponse:
        tender = self._tender(tender_id, company_id)
        current = self._build_snapshot(tender)
        previous = self.snapshots.latest(company_id, tender_id)
        if previous and previous.get("content_hash") == current["content_hash"]:
            return SnapshotCaptureResponse(
                snapshot=TenderSnapshotOut.model_validate(previous),
                created=False,
                changes=[],
            )

        snapshot = self.snapshots.create(current)
        change_docs = _diff(previous, snapshot, tender=tender)
        created_changes = self.changes.create_many(change_docs)
        if user_id:
            self.audit.log(
                company_id=company_id,
                actor_user_id=user_id,
                action="tender.snapshot_captured",
                entity_type="tender",
                entity_id=tender_id,
                metadata={"changes": len(created_changes)},
            )
        return SnapshotCaptureResponse(
            snapshot=TenderSnapshotOut.model_validate(snapshot),
            created=True,
            changes=[ChangeOut.model_validate(item) for item in created_changes],
        )

    def refresh_tender(
        self, *, tender_id: str, company_id: str, user_id: str
    ) -> SnapshotCaptureResponse:
        tender = self._tender(tender_id, company_id)
        if not tender.get("source_url"):
            raise ValidationError("This tender has no source URL to refresh.")
        if not self.tinyfish.configured:
            raise NotConfiguredError(
                "TinyFish is not configured, so the source cannot be rechecked. "
                "Set TINYFISH_API_KEY on the server first."
            )

        # Capture the stored baseline before any source fields change.
        baseline = self.capture_snapshot(
            tender_id=tender_id, company_id=company_id, user_id=None
        )

        try:
            batch = self.tinyfish.fetch(
                [tender["source_url"]],
                purpose="Recheck a saved tender for corrigenda and changed fields",
            )
        except TinyFishNotConfigured as exc:
            raise NotConfiguredError(str(exc)) from exc
        except TinyFishError as exc:
            raise UpstreamError(f"Could not recheck the tender source: {exc}") from exc

        if not batch.pages:
            detail = next(iter(batch.errors.values()), "no page returned")
            raise UpstreamError(f"Could not recheck the tender source: {detail}")

        page = batch.pages[0]
        extracted = extract_fields(
            page.title or tender.get("title") or "",
            page.description or tender.get("description") or "",
            page.text or "",
        )
        updates: dict = {"source_retrieved_at": utcnow()}
        if page.title:
            updates["title"] = page.title.strip()
        if page.description:
            updates["description"] = page.description.strip()
        elif page.text:
            updates["description"] = page.text.strip()[:1000]
        if extracted.authority:
            updates["authority"] = extracted.authority
        if extracted.reference_number:
            updates["reference_number"] = extracted.reference_number
        if extracted.deadline:
            parsed = _parse_deadline(extracted.deadline)
            if parsed:
                updates["deadline"] = parsed

        discovered = dict(tender.get("discovery_extracted") or {})
        if extracted.value_amount is not None:
            discovered["value_amount"] = extracted.value_amount
        if extracted.value_currency:
            discovered["value_currency"] = extracted.value_currency
        if extracted.location:
            discovered["location"] = extracted.location
        if discovered != (tender.get("discovery_extracted") or {}):
            updates["discovery_extracted"] = discovered

        self.tenders.update_for_company(tender_id, company_id, updates)

        result = self.capture_snapshot(
            tender_id=tender_id, company_id=company_id, user_id=None
        )
        # If the source was unchanged, keep the earlier "not created" result but
        # still report that the recheck completed.
        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="tender.rechecked",
            entity_type="tender",
            entity_id=tender_id,
            metadata={
                "baseline_snapshot_id": baseline.snapshot.id,
                "changes": len(result.changes),
                "source_url": tender.get("source_url"),
            },
        )
        return result

    def list_snapshots(
        self, *, tender_id: str, company_id: str, limit: int = 20, offset: int = 0
    ) -> list[TenderSnapshotOut]:
        self._tender(tender_id, company_id)
        items, _ = self.snapshots.list_for_tender(
            company_id, tender_id, limit=limit, offset=offset
        )
        return [TenderSnapshotOut.model_validate(item) for item in items]

    def list_changes(
        self,
        *,
        company_id: str,
        tender_id: str | None = None,
        review_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ChangeOut], int]:
        if tender_id:
            # Returning an empty list for another company's tender would leak
            # that the tender exists and hide a scope error.
            self._tender(tender_id, company_id)
        items, total = self.changes.list_for_company(
            company_id,
            limit=limit,
            offset=offset,
            tender_id=tender_id,
            review_status=review_status,
        )
        return [ChangeOut.model_validate(item) for item in items], total

    def review_change(
        self, *, change_id: str, company_id: str, user_id: str, review_status: str
    ) -> ChangeOut:
        existing = self.changes.find(change_id, company_id)
        if not existing:
            raise NotFoundError("Change not found.")
        updated = self.changes.update_review(change_id, company_id, review_status)
        if not updated:
            raise NotFoundError("Change not found.")
        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="change.reviewed",
            entity_type="change",
            entity_id=change_id,
            metadata={"review_status": review_status},
        )
        return ChangeOut.model_validate(updated)
