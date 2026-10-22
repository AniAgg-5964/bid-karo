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

    # Gmail SMTP OTP delivery. Use a Google App Password, never the account password.
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_username: str = "bidkaroindia@gmail.com"
    smtp_app_password: str = ""
    smtp_from_name: str = "BidKaro"
    smtp_timeout_seconds: int = 20
    otp_expire_minutes: int = 10
    otp_resend_cooldown_seconds: int = 60
    otp_max_sends_per_hour: int = 5
    otp_max_attempts: int = 5

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
    ocr_enabled: bool = True
    ocr_language: str = "eng"
    ocr_dpi: int = 300
    ocr_max_pages: int = 40
    ocr_timeout_seconds: int = 45
    tesseract_cmd: str = ""
    ai_extraction_max_chunk_chars: int = 4000
    ai_extraction_max_pages_per_chunk: int = 3
    ai_extraction_max_chunks: int = 12
    ai_extraction_max_pages: int = 80

    discovery_max_candidates: int = 20
    discovery_fetch_limit: int = 12
    discovery_min_score: float = 0.3
    discovery_cache_hours: int = 24

    # Tender packages (a ZIP that a tender was downloaded as). The archive is
    # read on the server and expanded into individual documents, under these
    # limits so a malicious or enormous archive cannot exhaust the server.
    package_max_upload_mb: int = 200
    package_max_members: int = 200
    package_max_member_mb: int = 25
    package_max_expanded_mb: int = 500
    package_max_ratio: int = 200
    package_max_nesting: int = 1

    # The job worker runs queued work (the analysis pipeline) in this process.
    job_worker_enabled: bool = True
    job_poll_seconds: float = 2.0

    # Vector store (Qdrant) for semantic retrieval over the company and tender
    # documents. Qdrant is an index: the documents, the requirements and the
    # decisions stay in MongoDB and on disk.
    qdrant_enabled: bool = True
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "bidkaro_knowledge"
    qdrant_timeout_seconds: int = 10
    qdrant_vector_size: int = 0  # 0 means "ask the embedding provider"

    # Embeddings. The provider decides the dimension; it is never hardcoded
    # from an assumed provider.
    embedding_provider: str = "hashing"
    embedding_model: str = ""
    embedding_dimension: int = 0  # 0 means the provider's own dimension
    embedding_batch_size: int = 32

    # Retrieval and ingestion limits.
    chunk_max_chars: int = 1200
    chunk_overlap_chars: int = 150
    chunk_max_per_document: int = 2000
    retrieval_top_k: int = 8
    retrieval_min_score: float = 0.0

    # The agent steps. Legal research is bounded because it reads the web and
    # asks a model for every clause it covers.
    legal_research_max_clauses: int = 3

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
