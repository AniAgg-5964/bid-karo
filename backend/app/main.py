from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.is_production and settings.jwt_secret.startswith("dev-only"):
        raise RuntimeError("JWT_SECRET must be configured before running in production.")
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    yield


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


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": settings.app_name, "docs": "/docs", "health": f"{settings.api_prefix}/health"}


app.include_router(api_router, prefix=settings.api_prefix)
