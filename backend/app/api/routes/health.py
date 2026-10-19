from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.database import Database, get_database

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Database = Depends(get_database)) -> dict:
    try:
        db.ping()
        database = "ok"
    except Exception:
        database = "unavailable"
    return {
        "status": "ok" if database == "ok" else "degraded",
        "service": get_settings().app_name,
        "database": database,
    }
