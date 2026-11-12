# Architecture notes

## Import convention (all Python)

All code is imported **from the repo root**: `contracts...`, `ingestion...`, `backend.app...`.
Run commands from the repo root (`python -m ingestion.run_all`, `uvicorn backend.app.main:app`,
`pytest`, `alembic -c backend/alembic.ini ...`). Never write `from app...`.

Allowed directions (checked by `backend/tests/test_import_graph.py`):

```
ingestion  ──►  backend.app.knowledge  ──►  backend.app.db, backend.app.core  ──►  contracts
backend.app.agents / controller / api  ──►  knowledge (only via agents/registry.py), db, core, contracts
```

* `contracts` imports nothing from the repo.
* `backend.app.knowledge` never imports `ingestion`, `agents`, `controller` or `api`.
* No import cycles.

## Single instances

| Thing | The one place |
|---|---|
| `.env` reader | `backend/app/core/config.py` (`get_settings`); ingestion extends it in `ingestion/config.py` |
| Database engine/session | `backend/app/db/session.py` |
| Table definitions | `backend/app/db/models.py` (+ Alembic migrations) |
| Embedding model | `backend/app/knowledge/embedder.py` (loaded once, its tokenizer is reused for chunking) |
| Qdrant client | `backend/app/knowledge/qdrant_store.py` |
| HTTP client for official sites | `ingestion/fetcher.py` |
| Vocabularies (sectors, tags, states, IDs) | `contracts/constants.py` (seeded into reference tables) |
