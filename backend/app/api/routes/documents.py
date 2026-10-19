from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError as PydanticValidationError

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company, get_current_user, get_storage
from app.core.exceptions import NotFoundError, ValidationError
from app.models.dashboard import MessageResponse
from app.models.document import (
    DocumentListResponse,
    DocumentMetadata,
    DocumentOut,
    DocumentUpdate,
)
from app.repositories.documents import DocumentRepository
from app.services.document_service import DocumentService
from app.services.storage import StorageService

router = APIRouter(prefix="/documents", tags=["company documents"])


def _parse_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} must use YYYY-MM-DD format.") from exc


def _metadata(
    *,
    title: str,
    document_type: str,
    issuer: str | None,
    signatory: str | None,
    financial_year: str | None,
    issue_date: str | None,
    expiry_date: str | None,
    project_value: float | None,
    notes: str | None,
) -> DocumentMetadata:
    try:
        return DocumentMetadata(
            title=title.strip(),
            document_type=document_type.strip(),
            issuer=issuer,
            signatory=signatory,
            financial_year=financial_year,
            issue_date=_parse_date(issue_date, "issue_date"),
            expiry_date=_parse_date(expiry_date, "expiry_date"),
            project_value=project_value,
            notes=notes,
        )
    except PydanticValidationError as exc:
        first = exc.errors()[0]
        message = first.get("msg", "Invalid document metadata.")
        raise ValidationError(message) from exc


@router.get("", response_model=DocumentListResponse)
def list_documents(
    document_type: str | None = None,
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
    storage: StorageService = Depends(get_storage),
) -> DocumentListResponse:
    service = DocumentService(db, storage)
    items, total = service.list(
        company["id"], document_type=document_type, search=search, limit=limit, offset=offset
    )
    return DocumentListResponse(
        items=[DocumentOut.model_validate(item) for item in items], total=total
    )


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    document_type: str = Form(...),
    issuer: str | None = Form(default=None),
    signatory: str | None = Form(default=None),
    financial_year: str | None = Form(default=None),
    issue_date: str | None = Form(default=None),
    expiry_date: str | None = Form(default=None),
    project_value: float | None = Form(default=None),
    notes: str | None = Form(default=None),
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
    storage: StorageService = Depends(get_storage),
) -> DocumentOut:
    metadata = _metadata(
        title=title,
        document_type=document_type,
        issuer=issuer,
        signatory=signatory,
        financial_year=financial_year,
        issue_date=issue_date,
        expiry_date=expiry_date,
        project_value=project_value,
        notes=notes,
    )
    content = await file.read(storage.max_bytes + 1)
    if len(content) > storage.max_bytes:
        raise ValidationError(f"Files must be {storage.max_upload_mb} MB or smaller.")

    document = DocumentService(db, storage).create(
        company_id=company["id"],
        user_id=user["id"],
        filename=file.filename,
        content_type=file.content_type,
        content=content,
        metadata=metadata,
    )
    return DocumentOut.model_validate(document)


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
    storage: StorageService = Depends(get_storage),
) -> FileResponse:
    service = DocumentService(db, storage)
    document, path = service.path_for(document_id, company["id"])
    return FileResponse(
        path,
        media_type=document["mime_type"],
        filename=document["original_filename"],
        headers={"Cache-Control": "private, no-store"},
    )


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: str,
    payload: DocumentUpdate,
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
    storage: StorageService = Depends(get_storage),
) -> DocumentOut:
    service = DocumentService(db, storage)
    service.get(document_id, company["id"])
    updated = DocumentRepository(db).update_for_company(
        document_id, company["id"], payload.model_dump(exclude_unset=True)
    )
    if not updated:
        raise NotFoundError("Document not found.")
    return DocumentOut.model_validate(updated)


@router.delete("/{document_id}", response_model=MessageResponse)
def delete_document(
    document_id: str,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
    storage: StorageService = Depends(get_storage),
) -> MessageResponse:
    DocumentService(db, storage).delete(document_id, company["id"], user["id"])
    return MessageResponse(message="Document deleted.")
