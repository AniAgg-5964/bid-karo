from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    assessment,
    auth,
    companies,
    dashboard,
    discovery,
    documents,
    health,
    tender_documents,
    tenders,
    workflow,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(documents.router)
api_router.include_router(dashboard.router)
api_router.include_router(tenders.router)
api_router.include_router(tender_documents.router)
api_router.include_router(assessment.router)
api_router.include_router(discovery.router)
api_router.include_router(workflow.router)
