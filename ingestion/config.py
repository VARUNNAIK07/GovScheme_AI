"""Ingestion-only settings. Extends the repo's single Settings class (same .env, no second reader)."""
from functools import lru_cache
from pathlib import Path

import yaml

from backend.app.core.config import REPO_ROOT, Settings

INGESTION_DIR = Path(__file__).resolve().parent
SEEDS_DIR = INGESTION_DIR / "seeds"


class IngestionSettings(Settings):
    scraper_contact_email: str | None = None
    scraper_min_delay_s: float = 2.0
    scraper_max_pdf_mb: int = 50
    scraper_timeout_s: float = 30.0
    scraper_max_retries: int = 3
    chunk_max_tokens: int = 480              # BGE limit is 512 incl. special tokens
    chunk_overlap_tokens: int = 40           # added to the EMBEDDED text only, never to the cited text

    @property
    def user_agent(self) -> str:
        email = self.require("scraper_contact_email")
        return f"GovSchemeAI-Ingestion/0.1 (academic project; contact: {email})"

    # ── data folders (inside DOCS_DIR) ──
    @property
    def raw_dir(self) -> Path: return self.docs_dir / "raw"
    @property
    def inbox_dir(self) -> Path: return self.docs_dir / "inbox"
    @property
    def parsed_dir(self) -> Path: return self.docs_dir / "parsed"
    @property
    def chunks_dir(self) -> Path: return self.docs_dir / "chunks"
    @property
    def extractions_dir(self) -> Path: return self.docs_dir / "extractions"
    @property
    def logs_dir(self) -> Path: return self.docs_dir / "logs"
    @property
    def index_csv(self) -> Path: return self.docs_dir / "index.csv"


@lru_cache
def get_ingestion_settings() -> IngestionSettings:
    return IngestionSettings()


@lru_cache
def load_allowlist() -> frozenset[str]:
    data = yaml.safe_load((INGESTION_DIR / "allowlist.yaml").read_text(encoding="utf-8")) or {}
    hosts = data.get("hosts") or []
    if not hosts:
        raise RuntimeError("ingestion/allowlist.yaml has no hosts")
    return frozenset(h.lower() for h in hosts)


__all__ = ["REPO_ROOT", "SEEDS_DIR", "IngestionSettings", "get_ingestion_settings", "load_allowlist"]
