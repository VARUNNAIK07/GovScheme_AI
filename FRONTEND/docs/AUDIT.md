# Repository & Corpus Audit

Audit completed at Hour 0 (09:00 - 09:15) per build plan.

## Component Decisions

| Component / Path | Current State | Decision | Rationale |
|---|---|---|---|
| `contracts/` | Frozen schemas (`schemas.py`, `types.ts`, `constants.py`) | **Keep / Enforce** | Forms the immutable contract between Knowledge (A), Brain (B), and Experience (C). |
| `contracts/fixtures/` | Structured JSON with `_fixture: true` + `sample.pdf` | **Reuse for Dev / Test** | Enables Member C to build UI and e2e tests independently before API integration. |
| `contracts/personas.json` | 3 verified personas (Farmer, SC Student, Senior BPL) | **Reuse** | Standard benchmark dataset for deterministic eligibility and scoring validation. |
| `frontend/` | React 19, TypeScript, Vite, Tailwind CSS, pdfjs-dist, MSW | **Build Clean** | Built to production civic standards without AI template artifacts. |
| `backend/` | FastAPI, SQLAlchemy, Alembic, PostgreSQL, Qdrant | **Integrate via REST** | Contract-bound REST endpoints under `/api`. |
