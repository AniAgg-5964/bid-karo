from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.core.database import Database, utcnow
from app.repositories.base import with_id


class CompanyRepository:
    def __init__(self, db: Database) -> None:
        self.collection = db.companies

    def create(self, *, name: str) -> dict:
        now = utcnow()
        document = {
            "_id": uuid4().hex,
            "name": name.strip(),
            "legal_name": None,
            "business_type": None,
            "description": None,
            "products_services": [],
            "sectors": [],
            "regions": [],
            "certifications": [],
            "annual_turnover": None,
            "turnover_currency": "INR",
            "employee_count": None,
            "established_year": None,
            "preferences": {
                "sectors": [],
                "regions": [],
                "keywords": [],
                "min_value": None,
                "max_value": None,
            },
            "onboarding_completed": False,
            "created_at": now,
            "updated_at": now,
        }
        self.collection.insert_one(document)
        return with_id(document)

    def find_by_id(self, company_id: str) -> dict | None:
        return with_id(self.collection.find_one({"_id": company_id}))

    def update(self, company_id: str, changes: dict) -> dict | None:
        changes = {key: value for key, value in changes.items() if value is not None}
        if not changes:
            return self.find_by_id(company_id)
        changes["updated_at"] = utcnow()
        self.collection.update_one({"_id": company_id}, {"$set": changes})
        return self.find_by_id(company_id)
