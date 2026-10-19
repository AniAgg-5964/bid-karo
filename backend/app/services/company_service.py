from __future__ import annotations

from app.core.database import Database
from app.models.company import CompanyOut, CompanyUpdate, calculate_profile_completeness
from app.repositories.companies import CompanyRepository
from app.repositories.audit import AuditRepository


def company_to_out(company: dict) -> CompanyOut:
    payload = dict(company)
    payload["profile_completeness"] = calculate_profile_completeness(payload)
    return CompanyOut.model_validate(payload)


class CompanyService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.companies = CompanyRepository(db)
        self.audit = AuditRepository(db)

    def get(self, company_id: str) -> dict | None:
        return self.companies.find_by_id(company_id)

    def update(self, *, company_id: str, user_id: str, payload: CompanyUpdate) -> dict:
        changes = payload.model_dump(exclude_unset=True)
        if "preferences" in changes and changes["preferences"] is not None:
            changes["preferences"] = payload.preferences.model_dump()

        if "name" in changes and not changes["name"]:
            changes.pop("name")

        updated = self.companies.update(company_id, changes)
        if updated is None:
            raise ValueError("Company not found.")

        self.audit.log(
            company_id=company_id,
            actor_user_id=user_id,
            action="company.updated",
            entity_type="company",
            entity_id=company_id,
            metadata={"fields": sorted(changes.keys())},
        )
        return updated
