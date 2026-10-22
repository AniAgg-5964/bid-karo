"""Tender document storage, PDF text extraction and cited requirement extraction.

Deterministic code owns file validation, PDF parsing, chunking, schema
validation, citation checks and persistence. The AI provider only proposes
requirements; an excerpt is stored as verified only when it is found verbatim
on the cited page.
"""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError

from app.core.config import Settings, get_settings
from app.core.database import Database, utcnow
from app.core.exceptions import (
    AppError,
    NotFoundError,
    NotConfiguredError,
    ValidationError,
)
from app.integrations.ai import AIError, AIProvider
from app.models.requirements import CATEGORIES, RequirementExtractionResponse
from app.repositories.assessment import EvidenceRepository
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.repositories.tender_documents import (
    RequirementRepository,
    TenderDocumentRepository,
    TenderPageRepository,
)
from app.repositories.tenders import TenderRepository
from app.services.agents.gate import check_quote
from app.services.download import DownloadError, download_pdf
from app.services.package_extraction import (
    PackageLimits,
    inspect_archive,
    read_member,
)
from app.services.pdf_extraction import PdfExtractionError, extract_pdf_pages
from app.services.ocr import OcrUnavailable, build_ocr
from app.services.storage import StorageService, sanitize_original_filename

PROMPT_VERSION = "requirements-v1"
MIN_EXCERPT_CHARS = 20
MAX_EXCERPT_CHARS = 5000
MAX_TITLE_CHARS = 200
MAX_OBLIGATION_CHARS = 2000
MAX_REFERENCE_CHARS = 160
DOCUMENT_KINDS = {"main", "corrigendum", "boq", "form", "other", "package"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}

_QUOTE_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
)

SYSTEM_PROMPT = """You extract requirements from public tender documents for a bid-compliance tool.

Rules:
1. Return JSON only, shaped as {"requirements": [...]}.
2. Every requirement must include "title", "obligation", "excerpt", "page_index", "category" and
   "mandatory". "excerpt" must be copied character-for-character from the page text.
   Never paraphrase, summarise, correct or invent the excerpt. If you cannot quote it, omit the requirement.
3. "page_index" must be the page number from the [[PAGE n]] marker that contains the excerpt.
4. "obligation" is your plain-language interpretation of the excerpt. Keep facts (dates, amounts,
   percentages) exactly as written and do not add requirements the text does not state.
5. "category" must be one of: eligibility, technical, financial, compliance, submission, performance, other.
6. "mandatory" must be "yes", "no" or "unknown". Use "unknown" when the text does not make it explicit.
7. "clause_reference" and "form_reference" are optional. Set "clause_reference" whenever the
   text numbers the clause (for example 3.1 or 7.4); set "form_reference" only when a form is named.
8. "deadline_text" and "consequence_text" are optional and must quote or closely follow the document.
9. Do not output boilerplate advice, general legal suggestions, or requirements that are not in the text.

Example item:
{"category": "eligibility", "title": "Minimum average annual turnover",
 "obligation": "The bidder must show average annual turnover of at least INR 5 crore.",
 "excerpt": "The bidder shall have an average annual turnover of at least INR 5 crore.",
 "page_index": 3, "clause_reference": "3.1", "form_reference": null,
 "mandatory": "yes", "deadline_text": null, "consequence_text": null}

Return {"requirements": []} when the pages contain no extractable requirements."""


class AIRequirement(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str = "other"
    title: str = ""
    obligation: str = ""
    excerpt: str
    page_index: int = Field(ge=1, le=10000)
    clause_reference: str | None = None
    form_reference: str | None = None
    mandatory: str = "unknown"
    deadline_text: str | None = None
    consequence_text: str | None = None


def parse_ai_items(payload: Any) -> tuple[list[AIRequirement], int]:
    """Validate items individually so one malformed item cannot sink a chunk."""
    if not isinstance(payload, dict) or not isinstance(payload.get("requirements"), list):
        raise AIError("AI response did not contain a requirements list.")
    items: list[AIRequirement] = []
    invalid = 0
    for raw in payload["requirements"]:
        try:
            items.append(AIRequirement.model_validate(raw))
        except PydanticValidationError:
            invalid += 1
    return items, invalid


@dataclass(slots=True)
class PageChunk:
    pages: list[dict]


def normalize_for_match(text: str) -> str:
    """Whitespace/typography-insensitive form used only for verification."""
    normalized = unicodedata.normalize("NFKC", text or "").translate(_QUOTE_MAP)
    return " ".join(normalized.split()).lower()


def _trim(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned[:limit] or None


def _category(value: str) -> str:
    cleaned = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return cleaned if cleaned in CATEGORIES else "other"


def _mandatory(value: str) -> str:
    cleaned = (value or "").strip().lower()
    if cleaned in {"yes", "true", "mandatory", "required", "shall"}:
        return "yes"
    if cleaned in {"no", "false", "optional", "not_mandatory"}:
        return "no"
    return "unknown"


def chunk_pages(
    pages: Iterable[dict],
    *,
    max_chars: int = 6000,
    max_pages_per_chunk: int = 6,
) -> list[PageChunk]:
    chunks: list[PageChunk] = []
    current: list[dict] = []
    current_chars = 0

    for page in pages:
        if not page.get("has_text"):
            continue
        size = len(page.get("text") or "")
        if current and (
            current_chars + size > max_chars or len(current) >= max(max_pages_per_chunk, 1)
        ):
            chunks.append(PageChunk(pages=current))
            current = []
            current_chars = 0
        current.append(page)
        current_chars += size

    if current:
        chunks.append(PageChunk(pages=current))
    return chunks



def _mime_for(suffix: str) -> str:
    """The content type we record for a file taken out of a package."""
    mapping = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".zip": "application/zip",
    }
    return mapping.get(suffix.lower(), "application/octet-stream")


def _to_png(content: bytes) -> bytes:
    """Convert an image to PNG bytes, which is what the OCR callable takes."""
    from PIL import Image

    with Image.open(io.BytesIO(content)) as image:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
        return buffer.getvalue()


def _read_image(content: bytes, ocr) -> dict:
    """Read one image as a single page, using OCR.

    An image has no text layer, so the page is always labelled as OCR text.
    """
    if ocr is None:
        return {
            "pages": [],
            "page_count": 1,
            "text_page_count": 0,
            "status": "not_parsed",
            "error": "OCR is not available on this server, so the image was stored but not read.",
            "ocr_page_count": 0,
            "ocr_status": "unavailable",
            "parse_status": "not_parsed",
            "parse_reason": "OCR is not available on this server.",
        }
    try:
        png_bytes = _to_png(content)
    except Exception as exc:  # noqa: BLE001 - a broken image is reported, not raised
        return {
            "pages": [],
            "page_count": 1,
            "text_page_count": 0,
            "status": "failed",
            "error": f"The image could not be read: {exc}",
            "ocr_page_count": 0,
            "ocr_status": "failed",
            "parse_status": "not_parsed",
            "parse_reason": f"The image could not be read: {exc}",
        }
    try:
        text = (ocr(png_bytes) or "").strip()
    except Exception as exc:  # noqa: BLE001 - OCR failure is reported, not raised
        return {
            "pages": [],
            "page_count": 1,
            "text_page_count": 0,
            "status": "failed",
            "error": f"OCR failed on the image: {exc}",
            "ocr_page_count": 0,
            "ocr_status": "failed",
            "parse_status": "not_parsed",
            "parse_reason": "OCR failed on the image.",
        }
    has_text = bool(text)
    return {
        "pages": [
            {
                "page_index": 1,
                "printed_label": "1",
                "text": text,
                "char_count": len(text),
                "has_text": has_text,
                "text_source": "ocr" if has_text else "empty",
            }
        ],
        "page_count": 1,
        "text_page_count": 1 if has_text else 0,
        "status": "extracted" if has_text else "no_text_layer",
        "error": None if has_text else "OCR found no readable text in the image.",
        "ocr_page_count": 1 if has_text else 0,
        "ocr_status": "applied" if has_text else "failed",
        "parse_status": "parsed",
        "parse_reason": None,
    }

class RequirementService:
    def __init__(
        self,
        db: Database,
        storage: StorageService,
        *,
        ai: AIProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.storage = storage
        self.settings = settings or get_settings()
        self.ai = ai
        self.tenders = TenderRepository(db)
        self.documents = TenderDocumentRepository(db)
        self.pages = TenderPageRepository(db)
        self.requirements = RequirementRepository(db)
        self.evidence = EvidenceRepository(db)
        self.company_documents = DocumentRepository(db)
        self.audit = AuditRepository(db)

    # ------------------------------------------------------------- documents
    def _tender(self, tender_id: str, company_id: str) -> dict:
        tender = self.tenders.find_for_company(tender_id, company_id)
        if not tender:
            raise NotFoundError("Tender not found.")
        return tender

    def upload_document(
        self,
        *,
        tender_id: str,
        company_id: str,
        user_id: str,
        filename: str | None,
        content_type: str | None,
        content: bytes,
        kind: str,
        title: str | None,
        source_url: str | None = None,
        source: str = "uploaded",
    ) -> dict:
        """Store one tender document: a PDF, an image, or a ZIP package."""
        self._tender(tender_id, company_id)

        suffix = Path(sanitize_original_filename(filename)).suffix.lower()
        if suffix == ".zip":
            return self.upload_package(
                tender_id=tender_id,
                company_id=company_id,
                user_id=user_id,
                filename=filename,
                content_type=content_type,
                content=content,
                kind=kind,
                title=title,
                source_url=source_url,
                source=source,
            )

        suffix, mime_type = self.storage.validate(filename, content_type, content)
        if suffix != ".pdf" and suffix not in IMAGE_SUFFIXES:
            raise ValidationError("Tender documents must be PDF, PNG or JPG files.")

        return self._store_document(
            tender_id=tender_id,
            company_id=company_id,
            user_id=user_id,
            content=content,
            original=sanitize_original_filename(filename),
            suffix=suffix,
            mime_type=mime_type,
            kind=kind,
            title=title,
            source=source,
            source_url=source_url,
        )

    def upload_package(
        self,
        *,
        tender_id: str,
        company_id: str,
        user_id: str,
        filename: str | None,
        content_type: str | None,
        content: bytes,
        kind: str,
        title: str | None,
        source_url: str | None = None,
        source: str = "uploaded",
    ) -> dict:
        """Store a tender package (a ZIP) and expand it into documents.

        The archive itself is kept as the record of what was received. Every
        file that may be stored becomes its own document, so requirements can
        cite the file they came from. Files that are not allowed are reported
        with the reason; nothing is dropped silently.
        """
        self._tender(tender_id, company_id)
        suffix, mime_type = self.storage.validate_package(filename, content_type, content)

        sha256 = hashlib.sha256(content).hexdigest()
        existing = self.documents.find_by_hash(company_id, tender_id, sha256)
        if existing:
            return existing

        original = sanitize_original_filename(filename)
        stored_filename, path = self.storage.save_tender_document(
            company_id, tender_id, content, ".zip"
        )
        limits = PackageLimits.from_settings(self.settings)
        inspection = inspect_archive(content, limits=limits)

        try:
            package = self.documents.create(
                {
                    "company_id": company_id,
                    "tender_id": tender_id,
                    "kind": "package",
                    "title": _trim(title, MAX_TITLE_CHARS)
                    or Path(original).stem[:MAX_TITLE_CHARS],
                    "original_filename": original,
                    "stored_filename": stored_filename,
                    "mime_type": mime_type,
                    "size_bytes": len(content),
                    "sha256": sha256,
                    "source": "downloaded" if source == "downloaded" else "uploaded",
                    "source_url": _trim(source_url, 2000),
                    "retrieved_at": utcnow(),
                    "status": "extracted",
                    "page_count": 0,
                    "text_page_count": 0,
                    "ocr_page_count": 0,
                    "ocr_status": "not_needed",
                    "truncated": False,
                    "error": inspection.error,
                    "parse_status": "container",
                    "parse_reason": inspection.error,
                    "is_container": True,
                    "parent_document_id": None,
                    "archive_path": None,
                    "package_summary": {
                        "total": len(inspection.members) + len(inspection.skipped),
                        "stored": len(inspection.accepted),
                        "skipped": len(inspection.skipped),
                        "members": [],
                        "skipped_files": [
                            {"path": member.path, "reason": member.reason}
                            for member in inspection.skipped
                        ],
                    },
                }
            )
        except Exception:
            if path.exists():
                path.unlink()
            raise

        members: list[dict] = []
        for member in inspection.accepted:
            entry: dict = {
                "path": member.path,
                "title": member.title,
                "kind": member.kind,
                "category": member.category,
                "size_bytes": member.size,
                "stored": True,
                "reason": None,
                "document_id": None,
                "status": None,
                "page_count": 0,
            }
            try:
                data = read_member(content, member, limits=limits)
            except ValueError as exc:
                entry["stored"] = False
                entry["reason"] = str(exc)
                members.append(entry)
                continue
            try:
                child = self._store_document(
                    tender_id=tender_id,
                    company_id=company_id,
                    user_id=user_id,
                    content=data,
                    original=Path(member.path).name,
                    suffix=member.suffix,
                    mime_type=_mime_for(member.suffix),
                    kind=member.kind,
                    title=member.title,
                    source=source,
                    source_url=source_url,
                    parent_document_id=package["id"],
                    archive_path=member.path,
                )
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the package
                entry["stored"] = False
                entry["reason"] = f"The file could not be read: {exc}"
            else:
                entry["document_id"] = child["id"]
                entry["status"] = child.get("status")
                entry["page_count"] = child.get("page_count", 0)
            members.append(entry)

        summary = {
            "total": len(inspection.members) + len(inspection.skipped),
            "stored": sum(1 for entry in members if entry["stored"]),
            "skipped": len(inspection.skipped)
            + sum(1 for entry in members if not entry["stored"]),
            "members": members,
            "skipped_files": [
                {"path": member.path, "reason": member.reason}
                for member in inspection.skipped
            ],
        }
        self.documents.update(package["id"], company_id, {"package_summary": summary})

        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="tender_package.uploaded",
            entity_type="tender_document",
            entity_id=package["id"],
            metadata={
                "tender_id": tender_id,
                "filename": original,
                "members": summary["stored"],
                "skipped": summary["skipped"],
            },
        )
        return {**package, "package_summary": summary}

    def _store_document(
        self,
        *,
        tender_id: str,
        company_id: str,
        user_id: str,
        content: bytes,
        original: str,
        suffix: str,
        mime_type: str,
        kind: str,
        title: str | None,
        source: str = "uploaded",
        source_url: str | None = None,
        parent_document_id: str | None = None,
        archive_path: str | None = None,
    ) -> dict:
        """Store one file as a tender document and read its pages."""
        sha256 = hashlib.sha256(content).hexdigest()
        existing = self.documents.find_by_hash(company_id, tender_id, sha256)
        if existing:
            return existing

        stored_filename, path = self.storage.save_tender_document(
            company_id, tender_id, content, suffix
        )

        page_rows: list[dict] = []
        page_count = 0
        text_page_count = 0
        truncated = False
        status = "extracted"
        error: str | None = None
        ocr_page_count = 0
        ocr_status = "disabled" if not self.settings.ocr_enabled else "not_needed"
        parse_status = "parsed"
        parse_reason: str | None = None
        ocr = None
        if self.settings.ocr_enabled:
            try:
                ocr = build_ocr(
                    language=self.settings.ocr_language,
                    tesseract_cmd=self.settings.tesseract_cmd,
                    timeout_seconds=self.settings.ocr_timeout_seconds,
                )
            except OcrUnavailable:
                ocr_status = "unavailable"

        if suffix == ".pdf":
            try:
                extraction = extract_pdf_pages(
                    content,
                    max_pages=self.settings.pdf_max_pages,
                    ocr=ocr,
                    ocr_dpi=self.settings.ocr_dpi,
                    ocr_max_pages=self.settings.ocr_max_pages,
                )
                page_count = extraction.page_count
                text_page_count = extraction.text_page_count
                truncated = extraction.truncated
                status = extraction.status
                ocr_page_count = extraction.ocr_page_count
                if self.settings.ocr_enabled and ocr is not None:
                    if ocr_page_count and (
                        extraction.ocr_failed_pages or extraction.ocr_skipped_pages
                    ):
                        ocr_status = "partial"
                    elif ocr_page_count:
                        ocr_status = "applied"
                    elif text_page_count < page_count:
                        ocr_status = "failed"
                for page in extraction.pages:
                    page_rows.append(
                        {
                            "page_index": page.page_index,
                            "printed_label": page.printed_label,
                            "text": page.text,
                            "char_count": page.char_count,
                            "has_text": page.has_text,
                            "text_source": page.text_source,
                        }
                    )
            except PdfExtractionError as exc:
                status = "failed"
                error = str(exc)
                page_rows = []
        elif suffix in IMAGE_SUFFIXES:
            image = _read_image(content, ocr)
            page_rows = image["pages"]
            page_count = image["page_count"]
            text_page_count = image["text_page_count"]
            status = image["status"]
            error = image["error"]
            ocr_page_count = image["ocr_page_count"]
            ocr_status = image["ocr_status"]
            parse_status = image["parse_status"]
            parse_reason = image["parse_reason"]
        else:
            status = "not_parsed"
            parse_status = "not_parsed"
            parse_reason = f"Unsupported format: {suffix or 'unknown'}"

        try:
            document = self.documents.create(
                {
                    "company_id": company_id,
                    "tender_id": tender_id,
                    "kind": kind if kind in DOCUMENT_KINDS else "other",
                    "title": _trim(title, MAX_TITLE_CHARS)
                    or Path(original).stem[:MAX_TITLE_CHARS],
                    "original_filename": original,
                    "stored_filename": stored_filename,
                    "mime_type": mime_type,
                    "size_bytes": len(content),
                    "sha256": sha256,
                    "source": "downloaded" if source == "downloaded" else "uploaded",
                    "source_url": _trim(source_url, 2000),
                    "retrieved_at": utcnow(),
                    "status": status,
                    "page_count": page_count,
                    "text_page_count": text_page_count,
                    "ocr_page_count": ocr_page_count,
                    "ocr_status": ocr_status,
                    "truncated": truncated,
                    "error": error,
                    "parse_status": parse_status,
                    "parse_reason": parse_reason,
                    "is_container": False,
                    "parent_document_id": parent_document_id,
                    "archive_path": archive_path,
                }
            )
            self.pages.replace_for_document(
                company_id=company_id,
                tender_id=tender_id,
                document_id=document["id"],
                pages=page_rows,
            )
        except Exception:
            if path.exists():
                path.unlink()
            raise

        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="tender_document.uploaded",
            entity_type="tender_document",
            entity_id=document["id"],
            metadata={
                "tender_id": tender_id,
                "filename": original,
                "status": status,
                "source": document["source"],
            },
        )
        return document

    def fetch_document(
        self,
        *,
        tender_id: str,
        company_id: str,
        user_id: str,
        url: str,
        kind: str,
        title: str | None,
    ) -> dict:
        self._tender(tender_id, company_id)
        try:
            content, final_url, _ = download_pdf(
                url, max_bytes=self.storage.max_bytes, timeout_seconds=30
            )
        except DownloadError as exc:
            self.audit.log(
                company_id=company_id,
                actor_user_id=user_id,
                action="tender_document.download_blocked",
                entity_type="tender",
                entity_id=tender_id,
                metadata={"url": url, "reason": exc.reason},
            )
            raise AppError(
                409,
                f"Automated download failed ({exc.reason}). Upload the PDF instead.",
            ) from exc

        return self.upload_document(
            tender_id=tender_id,
            company_id=company_id,
            user_id=user_id,
            filename=Path(final_url.split("?")[0]).name or "tender-document.pdf",
            content_type="application/pdf",
            content=content,
            kind=kind,
            title=title,
            source_url=final_url,
            source="downloaded",
        )

    def list_documents(self, tender_id: str, company_id: str) -> list[dict]:
        self._tender(tender_id, company_id)
        return self.documents.list_for_tender(company_id, tender_id)

    def get_document(self, document_id: str, company_id: str) -> dict:
        document = self.documents.find_for_company(document_id, company_id)
        if not document:
            raise NotFoundError("Tender document not found.")
        return document

    def document_path(self, document_id: str, company_id: str) -> tuple[dict, Path]:
        document = self.get_document(document_id, company_id)
        path = self.storage.resolve_tender_document(
            company_id, document["tender_id"], document["stored_filename"]
        )
        if not path.exists():
            raise NotFoundError("The stored PDF is unavailable.")
        return document, path

    def list_pages(self, document_id: str, company_id: str) -> list[dict]:
        self.get_document(document_id, company_id)
        return self.pages.list_for_document(document_id, company_id)

    def get_page(self, document_id: str, company_id: str, page_index: int) -> dict:
        self.get_document(document_id, company_id)
        page = self.pages.find_page(document_id, company_id, page_index)
        if not page:
            raise NotFoundError("Page not found.")
        return page

    def delete_document(self, document_id: str, company_id: str, user_id: str) -> None:
        document = self.get_document(document_id, company_id)
        # The indexed passages go with the document, so a deleted document
        # cannot still be found by a search.
        from app.services.document_lifecycle import DocumentLifecycleService

        DocumentLifecycleService(self.db, settings=self.settings).remove_tender_document(
            company_id, document_id
        )
        self.requirements.delete_for_document(document_id, company_id)
        self.pages.delete_for_document(document_id, company_id)
        self.documents.delete(document_id, company_id)
        self.storage.delete_tender_document(
            company_id, document["tender_id"], document["stored_filename"]
        )
        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="tender_document.deleted",
            entity_type="tender_document",
            entity_id=document_id,
            metadata={"tender_id": document["tender_id"]},
        )

    # ----------------------------------------------------------- requirements
    def _chunk_prompt(self, tender: dict, document: dict, chunk: PageChunk) -> str:
        parts = [
            f"Tender title: {tender.get('title')}",
            f"Authority: {tender.get('authority') or 'not stated'}",
            f"Document: {document.get('title')}",
            "",
            "Extract requirements only from the pages below. Use the exact page number from each marker.",
            "",
        ]
        for page in chunk.pages:
            parts.append(
                f"[[PAGE {page['page_index']} | PRINTED {page.get('printed_label') or page['page_index']}]]"
            )
            parts.append(page.get("text") or "")
            parts.append("")
        return "\n".join(parts)

    def _validate_excerpt(self, requirement: AIRequirement, pages_by_index: dict[int, dict]) -> str | None:
        """Return a rejection reason, or None when the excerpt is on the cited page.

        The check itself lives in the deterministic gate, so the tender
        requirements and anything an agent proposes are judged by exactly the
        same rule.
        """
        page = pages_by_index.get(requirement.page_index)
        verdict = check_quote(
            requirement.excerpt or "",
            page_text=(page or {}).get("text"),
            text_source=(page or {}).get("text_source") or "text_layer",
            min_chars=MIN_EXCERPT_CHARS,
            max_chars=MAX_EXCERPT_CHARS,
        )
        if verdict.status == "verified":
            return None
        return verdict.reason

    def extract_requirements(
        self,
        *,
        document_id: str,
        company_id: str,
        user_id: str,
        replace: bool = False,
    ) -> RequirementExtractionResponse:
        document = self.get_document(document_id, company_id)
        tender = self._tender(document["tender_id"], company_id)
        pages = self.pages.list_for_document(document_id, company_id)
        text_pages = [page for page in pages if page.get("has_text")]

        if not text_pages:
            raise ValidationError(
                "This PDF has no extractable text. OCR did not produce usable text; "
                "upload a clearer digital copy or enable OCR in the server settings."
            )
        if self.ai is None or not self.ai.configured:
            raise NotConfiguredError(
                "AI extraction is not configured. Set AI_PROVIDER, the provider API key and model."
            )

        if replace:
            backup = self.requirements.backup_ai_for_document(document_id, company_id)
            self.requirements.delete_ai_for_document(document_id, company_id)
        else:
            backup = []

        selected = text_pages[: max(self.settings.ai_extraction_max_pages, 1)]
        all_chunks = chunk_pages(
            selected,
            max_chars=self.settings.ai_extraction_max_chunk_chars,
            max_pages_per_chunk=self.settings.ai_extraction_max_pages_per_chunk,
        )
        chunks = all_chunks[: max(self.settings.ai_extraction_max_chunks, 1)]
        skipped_chunks = len(all_chunks) - len(chunks)

        stats = {
            "created": 0,
            "duplicates": 0,
            "invalid": 0,
            "verified": 0,
            "unverified": 0,
            "needs_review": 0,
            "failed_chunks": 0,
        }
        last_error: str | None = None

        for chunk in chunks:
            try:
                payload = self.ai.complete_json(
                    system=SYSTEM_PROMPT,
                    user=self._chunk_prompt(tender, document, chunk),
                )
                items, invalid = parse_ai_items(payload)
                stats["invalid"] += invalid
            except AIError as exc:
                stats["failed_chunks"] += 1
                last_error = str(exc)
                continue

            pages_by_index = {page["page_index"]: page for page in chunk.pages}
            for item in items:
                self._store_requirement(
                    item=item,
                    document=document,
                    company_id=company_id,
                    pages_by_index=pages_by_index,
                    stats=stats,
                )

        restored = False
        if replace and backup and stats["created"] == 0:
            self.requirements.restore(backup)
            restored = True

        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="requirements.extracted",
            entity_type="tender_document",
            entity_id=document_id,
            metadata={
                "tender_id": document["tender_id"],
                "model": self.ai.model,
                "chunks": len(chunks),
                "created": stats["created"],
                "unverified": stats["unverified"],
                "restored_previous": restored,
            },
        )

        status = "completed" if stats["failed_chunks"] == 0 else "partial"
        message = (
            f"Extracted {stats['created']} requirements "
            f"({stats['verified']} verified, {stats['unverified']} unverified)."
        )
        if stats["needs_review"]:
            message += (
                f" {stats['needs_review']} matched OCR text and need visual review."
            )
        if stats["duplicates"]:
            message += f" Skipped {stats['duplicates']} duplicates."
        if stats["invalid"]:
            message += f" Ignored {stats['invalid']} malformed items."
        if skipped_chunks:
            message += f" {skipped_chunks} chunks were skipped by the per-run limit."
        if stats["failed_chunks"]:
            message += (
                f" {stats['failed_chunks']} chunks failed; last error: {last_error or 'unknown'}."
            )
        if restored:
            message += " Existing requirements were kept because none were replaced."
        if not chunks:
            status = "no_text"
            message = "No extractable pages were available for AI extraction."

        return RequirementExtractionResponse(
            document_id=document_id,
            status=status,
            chunks=len(chunks),
            skipped_chunks=skipped_chunks,
            created=stats["created"],
            duplicates=stats["duplicates"],
            invalid=stats["invalid"],
            verified=stats["verified"],
            unverified=stats["unverified"],
            needs_review=stats["needs_review"],
            failed_chunks=stats["failed_chunks"],
            model=self.ai.model,
            message=message,
        )

    def _store_requirement(
        self,
        *,
        item: AIRequirement,
        document: dict,
        company_id: str,
        pages_by_index: dict[int, dict],
        stats: dict[str, int],
    ) -> None:
        excerpt = (item.excerpt or "").strip()
        if len(excerpt) < 5:
            stats["invalid"] += 1
            return
        excerpt_key = normalize_for_match(excerpt)[:400]
        page_index = int(item.page_index)

        if self.requirements.exists(document["id"], page_index, excerpt_key):
            stats["duplicates"] += 1
            return

        reason = self._validate_excerpt(item, pages_by_index)
        page = pages_by_index.get(page_index) or {}
        text_source = page.get("text_source") or "text_layer"
        ocr_review = False
        if not reason and text_source == "ocr":
            reason = "Excerpt matched OCR text only; verify it visually against the page image."
            ocr_review = True

        title = _trim(item.title, MAX_TITLE_CHARS)
        if not title:
            clause = _trim(item.clause_reference, 40)
            title = (
                f"Clause {clause}"
                if clause
                else (_trim(item.obligation, 100) or excerpt[:100])
            )

        self.requirements.create(
            {
                "company_id": company_id,
                "tender_id": document["tender_id"],
                "document_id": document["id"],
                "category": _category(item.category),
                "title": title,
                "obligation": _trim(item.obligation, MAX_OBLIGATION_CHARS) or excerpt[:MAX_OBLIGATION_CHARS],
                "excerpt": excerpt[:MAX_EXCERPT_CHARS],
                "excerpt_key": excerpt_key,
                "page_index": page_index,
                "printed_page": page.get("printed_label"),
                "text_source": text_source,
                "clause_reference": _trim(item.clause_reference, MAX_REFERENCE_CHARS),
                "form_reference": _trim(item.form_reference, MAX_REFERENCE_CHARS),
                "mandatory": _mandatory(item.mandatory),
                "deadline_text": _trim(item.deadline_text, 500),
                "consequence_text": _trim(item.consequence_text, 1000),
                "verification_status": "needs_review" if ocr_review else ("unverified" if reason else "verified"),
                "verification_notes": reason,
                "document_title": document.get("title"),
                "document_retrieved_at": document.get("retrieved_at"),
                "source_url": document.get("source_url"),
                "origin": "ai",
                "model": self.ai.model,
                "prompt_version": PROMPT_VERSION,
            }
        )
        stats["created"] += 1
        if ocr_review:
            stats["needs_review"] += 1
        elif reason:
            stats["unverified"] += 1
        else:
            stats["verified"] += 1

    def _decorate_evidence(self, items: list[dict], company_id: str) -> list[dict]:
        if not items:
            return items
        decisions = self.evidence.find_for_requirements(
            [item["id"] for item in items], company_id
        )
        if not decisions:
            return items
        documents, _ = self.company_documents.list_for_company(company_id, limit=300)
        titles = {item["id"]: item.get("title") for item in documents}
        for item in items:
            decision = decisions.get(item["id"])
            if decision:
                item["evidence_status"] = decision.get("status") or "none"
                item["evidence_document_id"] = decision.get("document_id")
                item["evidence_document_title"] = titles.get(decision.get("document_id"))
        return items

    def list_requirements(self, tender_id: str, company_id: str, **filters) -> tuple[list[dict], int]:
        self._tender(tender_id, company_id)
        items, total = self.requirements.list_for_tender(company_id, tender_id, **filters)
        return self._decorate_evidence(items, company_id), total

    def get_requirement(self, requirement_id: str, company_id: str) -> dict:
        requirement = self.requirements.find_for_company(requirement_id, company_id)
        if not requirement:
            raise NotFoundError("Requirement not found.")
        return self._decorate_evidence([requirement], company_id)[0]

    def review_requirement(
        self,
        *,
        requirement_id: str,
        company_id: str,
        user_id: str,
        verification_status: str,
        note: str | None,
    ) -> dict:
        existing = self.get_requirement(requirement_id, company_id)
        changes: dict[str, Any] = {"verification_status": verification_status}
        if note is not None:
            changes["verification_notes"] = note.strip()[:1000] or None
        elif verification_status in {"verified", "rejected"}:
            changes["verification_notes"] = None
        updated = self.requirements.update_review(requirement_id, company_id, changes)
        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="requirement.reviewed",
            entity_type="requirement",
            entity_id=requirement_id,
            metadata={
                "tender_id": existing["tender_id"],
                "from": existing["verification_status"],
                "to": verification_status,
            },
        )
        return updated

    def counts_for_tender(self, tender_id: str, company_id: str) -> dict[str, int]:
        self._tender(tender_id, company_id)
        counts = self.requirements.summary_for_tender(company_id, tender_id)
        counts["documents"] = self.documents.count_for_tender(company_id, tender_id)
        return counts
