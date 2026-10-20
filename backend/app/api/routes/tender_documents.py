from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.core.dependencies import get_current_company, get_current_user, get_requirement_service
from app.core.exceptions import ValidationError
from app.models.dashboard import MessageResponse
from app.models.requirements import (
    DownloadRequest,
    MandatoryFlag,
    RequirementCategory,
    RequirementExtractionRequest,
    RequirementExtractionResponse,
    RequirementListResponse,
    RequirementOut,
    RequirementReview,
    RequirementSummary,
    RequirementVerification,
    TenderDocumentListResponse,
    TenderDocumentOut,
    TenderPageListResponse,
    TenderPageOut,
    TenderPageText,
)
from app.services.requirement_service import RequirementService

router = APIRouter(tags=["tender documents"])


@router.get("/tenders/{tender_id}/documents", response_model=TenderDocumentListResponse)
def list_tender_documents(
    tender_id: str,
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> TenderDocumentListResponse:
    items = service.list_documents(tender_id, company["id"])
    return TenderDocumentListResponse(
        items=[TenderDocumentOut.model_validate(item) for item in items], total=len(items)
    )


@router.post(
    "/tenders/{tender_id}/documents",
    response_model=TenderDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_tender_document(
    tender_id: str,
    file: UploadFile = File(...),
    kind: str = Form(default="main"),
    title: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> TenderDocumentOut:
    content = await file.read(service.storage.max_bytes + 1)
    if len(content) > service.storage.max_bytes:
        raise ValidationError(f"Files must be {service.storage.max_upload_mb} MB or smaller.")
    document = service.upload_document(
        tender_id=tender_id,
        company_id=company["id"],
        user_id=user["id"],
        filename=file.filename,
        content_type=file.content_type,
        content=content,
        kind=kind,
        title=title,
        source_url=source_url,
        source="uploaded",
    )
    return TenderDocumentOut.model_validate(document)


@router.post(
    "/tenders/{tender_id}/documents/fetch",
    response_model=TenderDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def fetch_tender_document(
    tender_id: str,
    payload: DownloadRequest,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> TenderDocumentOut:
    document = service.fetch_document(
        tender_id=tender_id,
        company_id=company["id"],
        user_id=user["id"],
        url=payload.url,
        kind=payload.kind,
        title=payload.title,
    )
    return TenderDocumentOut.model_validate(document)


@router.get("/tender-documents/{document_id}", response_model=TenderDocumentOut)
def get_tender_document(
    document_id: str,
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> TenderDocumentOut:
    document = service.get_document(document_id, company["id"])
    return TenderDocumentOut.model_validate(document)


@router.get("/tender-documents/{document_id}/pages", response_model=TenderPageListResponse)
def list_tender_pages(
    document_id: str,
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> TenderPageListResponse:
    document = service.get_document(document_id, company["id"])
    pages = service.list_pages(document_id, company["id"])
    return TenderPageListResponse(
        document_id=document_id,
        page_count=document["page_count"],
        text_page_count=document["text_page_count"],
        items=[TenderPageOut.model_validate(page) for page in pages],
    )


@router.get(
    "/tender-documents/{document_id}/pages/{page_index}",
    response_model=TenderPageText,
)
def get_tender_page_text(
    document_id: str,
    page_index: int,
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> TenderPageText:
    page = service.get_page(document_id, company["id"], page_index)
    return TenderPageText.model_validate(page)


@router.get("/tender-documents/{document_id}/download")
def download_tender_document(
    document_id: str,
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> FileResponse:
    document, path = service.document_path(document_id, company["id"])
    return FileResponse(
        path,
        media_type=document["mime_type"],
        filename=document["original_filename"],
        headers={"Cache-Control": "private, no-store"},
    )


@router.post(
    "/tender-documents/{document_id}/extract",
    response_model=RequirementExtractionResponse,
)
def extract_requirements(
    document_id: str,
    payload: RequirementExtractionRequest | None = None,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> RequirementExtractionResponse:
    return service.extract_requirements(
        document_id=document_id,
        company_id=company["id"],
        user_id=user["id"],
        replace=(payload or RequirementExtractionRequest()).replace,
    )


@router.delete("/tender-documents/{document_id}", response_model=MessageResponse)
def delete_tender_document(
    document_id: str,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> MessageResponse:
    service.delete_document(document_id, company["id"], user["id"])
    return MessageResponse(message="Tender document deleted.")


@router.get("/tenders/{tender_id}/requirements", response_model=RequirementListResponse)
def list_requirements(
    tender_id: str,
    category: RequirementCategory | None = Query(default=None),
    verification_status: RequirementVerification | None = Query(default=None),
    mandatory: MandatoryFlag | None = Query(default=None),
    document_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> RequirementListResponse:
    items, total = service.list_requirements(
        tender_id,
        company["id"],
        category=category,
        verification_status=verification_status,
        mandatory=mandatory,
        document_id=document_id,
        limit=limit,
        offset=offset,
    )
    return RequirementListResponse(
        items=[RequirementOut.model_validate(item) for item in items], total=total
    )


@router.get("/tenders/{tender_id}/requirements/summary", response_model=RequirementSummary)
def requirement_summary(
    tender_id: str,
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> RequirementSummary:
    counts = service.counts_for_tender(tender_id, company["id"])
    return RequirementSummary(**counts)


@router.get("/requirements/{requirement_id}", response_model=RequirementOut)
def get_requirement(
    requirement_id: str,
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> RequirementOut:
    return RequirementOut.model_validate(
        service.get_requirement(requirement_id, company["id"])
    )


@router.patch("/requirements/{requirement_id}", response_model=RequirementOut)
def review_requirement(
    requirement_id: str,
    payload: RequirementReview,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    service: RequirementService = Depends(get_requirement_service),
) -> RequirementOut:
    updated = service.review_requirement(
        requirement_id=requirement_id,
        company_id=company["id"],
        user_id=user["id"],
        verification_status=payload.verification_status,
        note=payload.note,
    )
    return RequirementOut.model_validate(updated)
