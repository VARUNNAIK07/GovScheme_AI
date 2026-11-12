"""Single settings object for the backend AND ingestion (one .env reader for the whole repo).

Owner: B (created by A for the initial DB setup). Add new keys here, never a second reader.
"""
import os
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from contracts import constants

REPO_ROOT = Path(__file__).resolve().parents[3]

# All ML models (BGE embeddings, Docling layout/table/OCR) live inside the project's .venv, not in
# the user-wide cache. Set here, at import time, because Hugging Face reads HF_HOME when it is first
# imported. Override with MODEL_DIR in the environment if needed.
MODEL_DIR = Path(os.environ.get("MODEL_DIR", REPO_ROOT / ".venv" / "models"))
os.environ.setdefault("HF_HOME", str(MODEL_DIR / "huggingface"))
DOCLING_ARTIFACTS_DIR = MODEL_DIR / "docling"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    # PostgreSQL (Supabase session pooler URL)
    database_url: SecretStr | None = None

    # Qdrant (Qdrant Cloud URL + API key)
    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_path: Path | None = None          # local embedded Qdrant, offline tests only (used if QDRANT_URL is empty)
    qdrant_collection: str = constants.QDRANT_COLLECTION
    embed_model: str = constants.EMBED_MODEL

    # LLM providers (used by knowledge/llm.py)
    llm_provider_priority: str = "groq,gemini"
    groq_api_key: SecretStr | None = None
    groq_model: str | None = None
    groq_fallback_model: str | None = None    # second Groq model with its own free quota (tried right after groq_model)
    gemini_api_key: SecretStr | None = None
    gemini_model: str | None = None
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 3

    # Backend (B)
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "govscheme-ai"
    jwt_ttl_s: int = 86_400
    use_stubs: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:3000,http://127.0.0.1:3000"     # comma-separated (Vite / web dev servers)

    # Data folder (relative paths are resolved from the repo root)
    docs_dir: Path = Path("data")

    @field_validator("database_url", mode="before")
    @classmethod
    def _use_psycopg3_driver(cls, v):
        # Supabase shows 'postgresql://...'; SQLAlchemy needs the psycopg (v3) driver name.
        if isinstance(v, str):
            for prefix in ("postgresql://", "postgres://"):
                if v.startswith(prefix):
                    return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @field_validator("docs_dir", "qdrant_path", mode="after")
    @classmethod
    def _absolute_path(cls, v: Path | None) -> Path | None:
        return v if v is None or v.is_absolute() else REPO_ROOT / v

    def require(self, name: str):
        """Return a setting or fail with a clear message naming the missing .env key."""
        value = getattr(self, name)
        if value is None or value == "":
            raise RuntimeError(f"{name.upper()} is not set in {REPO_ROOT / '.env'}")
        return value.get_secret_value() if isinstance(value, SecretStr) else value


@lru_cache
def get_settings() -> Settings:
    return Settings()
