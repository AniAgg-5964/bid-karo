from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "BidKaro API"
    api_prefix: str = "/api"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "bidkaro"
    mongodb_app_name: str = "BidKaro"
    mongodb_max_pool_size: int = 20
    mongodb_connect_timeout_ms: int = 10000
    mongodb_server_selection_timeout_ms: int = 10000
    mongodb_retry_writes: bool = True

    jwt_secret: str = "dev-only-change-me-before-any-real-deployment"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    cors_origins: str = "http://localhost:5173"
    storage_dir: Path = ROOT_DIR / "storage"
    max_upload_mb: int = 25

    tinyfish_api_key: str = ""
    tinyfish_base_url: str = ""
    tinyfish_agent_timeout_seconds: int = 120

    ai_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    groq_api_key: str = ""
    groq_model: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    ai_request_timeout_seconds: int = 60
    ai_max_output_tokens: int = 2000

    pdf_max_pages: int = 200
    ai_extraction_max_chunk_chars: int = 4000
    ai_extraction_max_pages_per_chunk: int = 3
    ai_extraction_max_chunks: int = 12
    ai_extraction_max_pages: int = 80

    discovery_max_candidates: int = 20
    discovery_fetch_limit: int = 12
    discovery_min_score: float = 0.3
    discovery_cache_hours: int = 24

    @field_validator("api_prefix")
    @classmethod
    def normalize_prefix(cls, value: str) -> str:
        value = value.strip() or "/api"
        return value if value.startswith("/") else f"/{value}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
