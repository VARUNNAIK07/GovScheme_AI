from contracts.schemas import HealthResponse


def _ok(check) -> str:
    try:
        check()
        return "ok"
    except Exception:
        return "down"


def health() -> HealthResponse:
    from ingestion.preflight import check_database, check_qdrant
    from backend.app.knowledge.llm import configured_providers
    llm = "ok" if configured_providers() else "down"     # configured; live calls are not spent on health checks
    return HealthResponse(postgres=_ok(check_database), qdrant=_ok(check_qdrant), llm=llm)
