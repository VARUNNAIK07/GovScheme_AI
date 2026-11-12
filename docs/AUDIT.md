# Existing repo / corpus audit

**2026-10-12 (A):** the repository started **empty**: no prior code, schemas, PDFs or `index.csv`.
Decision for every component: **build new** (nothing to reuse, fix or replace).

| Item | Found | Decision |
|---|---|---|
| Code | none | build per team file structure |
| Contracts | only in the build plan PDF (section 4) | written to `contracts/` + reviewed (see `contracts/CHANGELOG.md`) |
| PDF corpus | none | 49 approved schemes in `ingestion/seeds/`; 32 auto-downloadable sources, 18 manual (see `docs/MANUAL_DOWNLOADS.md`) |
| Database | none | Supabase PostgreSQL, schema in `backend/migrations/versions/0001_initial_schema.py` |
| Vector store | none | Qdrant Cloud, collection `scheme_chunks` |

Deviations from the team file-structure document (all additive):

* `frontend/` not scaffolded; C creates it with `npm create vite` (which needs an empty folder).
* New in `ingestion/`: `allowlist.yaml`, `seeds/`, `common.py`, `fetcher.py`, `preflight.py`, `load_db.py`, `requirements.txt`.
* New in `data/`: `inbox/`, `extractions/`, `logs/`.
* New tests: `test_import_graph.py`, `test_contracts_db.py`.
* `backend/__init__.py` + root `pytest.ini`: all Python imports from the repo root (see `docs/ARCHITECTURE.md`).
