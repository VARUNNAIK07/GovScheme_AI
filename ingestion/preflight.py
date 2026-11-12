"""Check configuration and connectivity before running the pipeline. Never prints secrets.

    python -m ingestion.preflight
"""
import sys

from ingestion.config import get_ingestion_settings, load_allowlist


def check_database() -> str:
    from sqlalchemy import inspect, text
    from backend.app.db.session import get_engine
    with get_engine().connect() as conn:
        server = conn.execute(text("SHOW server_version")).scalar_one()
        if not inspect(conn).has_table("alembic_version"):
            raise RuntimeError(f"connected to PostgreSQL {server}, but no tables yet "
                               "(run: alembic -c backend/alembic.ini upgrade head)")
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    if version is None:
        raise RuntimeError("connected, but no migration applied (run: alembic -c backend/alembic.ini upgrade head)")
    return f"PostgreSQL {server}, migration {version}"


def check_qdrant() -> str:
    from backend.app.knowledge.qdrant_store import collection_name, get_client
    client = get_client()
    names = [c.name for c in client.get_collections().collections]
    return f"reachable; collection '{collection_name()}' {'exists' if collection_name() in names else 'will be created'}"


def run() -> bool:
    cfg = get_ingestion_settings()
    checks = {
        "SCRAPER_CONTACT_EMAIL": lambda: cfg.require("scraper_contact_email") and "set",
        "allowlist": lambda: f"{len(load_allowlist())} hosts",
        "DATABASE_URL": check_database,
        "QDRANT": check_qdrant,
    }
    ok = True
    for name, fn in checks.items():
        try:
            print(f"  OK    {name}: {fn()}")
        except Exception as e:
            ok = False
            print(f"  FAIL  {name}: {type(e).__name__}: {str(e).splitlines()[0][:200]}")
    for provider in [p.strip() for p in cfg.llm_provider_priority.split(",") if p.strip()]:
        has_key = getattr(cfg, f"{provider}_api_key", None) is not None
        has_model = bool(getattr(cfg, f"{provider}_model", None))
        status = "OK  " if has_key and has_model else "WARN"
        print(f"  {status}  LLM {provider}: key {'set' if has_key else 'missing'}, model {'set' if has_model else 'missing'}"
              " (only needed for extract_facts / summaries)")
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
