from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import get_database
from app.core.exceptions import AppError

logger = logging.getLogger("bidkaro")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.is_production and settings.jwt_secret.startswith("dev-only"):
        raise RuntimeError("JWT_SECRET must be configured before running in production.")
    settings.storage_dir.mkdir(parents=True, exist_ok=True)

    # Fail fast with a message that never contains connection credentials.
    database_provider = app.dependency_overrides.get(get_database, get_database)
    try:
        database = database_provider()
        database.ping()
    except Exception as exc:  # pragma: no cover - exercised by deployment failure
        raise RuntimeError(
            "MongoDB is unreachable for database "
            f"'{settings.mongodb_db}'. Check MONGODB_URI, the Atlas IP allowlist, "
            f"and the database user's password/permissions ({type(exc).__name__})."
        ) from exc
    logger.info("MongoDB connected: %s", database.describe_target())

    runner = None
    if settings.job_worker_enabled:
        from app.services.analysis import requirements_step
        from app.services.job_runner import JobRunner

        runner = JobRunner(database, handlers={"requirements": requirements_step})
        runner.start_worker(interval_seconds=settings.job_poll_seconds)
        logger.info("Job worker started.")

    yield

    if runner is not None:
        runner.stop_worker()


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="BidKaro tender intelligence and bid-readiness API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Conservative headers for a JSON API reviewed locally over HTTP."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
    )
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": settings.app_name, "docs": "/docs", "health": f"{settings.api_prefix}/health"}


app.include_router(api_router, prefix=settings.api_prefix)
