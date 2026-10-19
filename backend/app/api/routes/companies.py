from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.database import Database, get_database
from app.core.dependencies import get_current_company, get_current_user
from app.models.company import CompanyOut, CompanyUpdate
from app.services.company_service import CompanyService, company_to_out

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/me", response_model=CompanyOut)
def get_company(company: dict = Depends(get_current_company)) -> CompanyOut:
    return company_to_out(company)


@router.patch("/me", response_model=CompanyOut)
def update_company(
    payload: CompanyUpdate,
    user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
    db: Database = Depends(get_database),
) -> CompanyOut:
    updated = CompanyService(db).update(
        company_id=company["id"], user_id=user["id"], payload=payload
    )
    return company_to_out(updated)
