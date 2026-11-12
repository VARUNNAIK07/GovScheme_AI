# Database gap report (2026-10-13)

Checked the 18 tables in Supabase (migration `0001`) against: contracts v1.2, all API endpoints in
section 5, workflows W1–W6, Person B's draft (`person_B/`), and what the retrieval agent will query.

## Verdict
**No missing tables.** One required change (migration 0002), plus two decisions that don't block anything.

## Coverage
| Need | Table(s) | OK? |
|---|---|---|
| register / login / `GET /me` (B: `UserRecord`) | `users` (unique lower(email)) | ✅ |
| profile + version (B: `Profile`, `apply_answer` bumps version) | `profiles` (PK user_id+version, one `is_current`) | ✅ |
| W2 library cache by (workflow, user, profile_version) (B: `WorkflowCache`) | `workflow_runs` + `ix_runs_cache_lookup` | ✅ |
| W5 invalidate a user's runs | `workflow_runs.status / invalidated_at` | ✅ |
| W6 invalidate runs touching changed schemes | `workflow_runs.scheme_ids` + GIN index | ✅ |
| W4 comparison sessions (2–5 ids) | `comparison_sessions` (CHECK 2..5) | ✅ |
| `Scheme` (incl. v1.2 `fact_citations`, `secondary_sectors`, `benefit_types`, `states`) | `schemes` + link tables + `scheme_facts` | ✅ except `limitations` / `max_benefit` facts → **0002** |
| `EligibilityRule` (B: `evaluate()`) | `eligibility_rules` | ✅ |
| `Evidence`, `CitationTarget`, `GET /citations/{id}` | `chunks` + `documents` + `sources` | ✅ |
| `DocumentMeta` (v1.2 `is_current`) | view `document_meta_v` | ✅ |
| retrieval: filter schemes by state / sector before vector search | `scheme_states`, `schemes.primary_sector`, `scheme_secondary_sectors` (indexed) | ✅ |
| `need_similarity` (needs vs scheme summary) | `schemes.summary` | ✅ (filled by extraction) |
| audit of LLM extraction | `extraction_runs` | ✅ |
| processing history / refresh | `ingestion_events`, `sources.last_status` | ✅ |

## Required change: migration 0002
Allow `scheme_facts.kind` values `max_benefit` and `limitation` (contract v1.2 `FACT_KIND_BY_FIELD`).
Draft is correct and safe (widens one CHECK; no data touched): `docs/proposals/migration_0002_scheme_fact_kinds.py`.
Apply = copy to `backend/migrations/versions/`, update the CHECK in `models.py`, `alembic upgrade head`, `alembic check`, drop the xfail.

## Decisions (not blocking)
1. **Where the PDFs live in production.** `GET /api/documents/{doc_id}/file` reads `data/raw/` on the machine running the API. Fine for the local demo; for a deployed backend, upload to a private Supabase Storage bucket and add `documents.storage_path` (a later migration).
2. **Onboarding versions.** B's `apply_answer` creates a new profile version per answer (~12 rows/user, 12 cache invalidations). Works with the schema as is; suggestion for B: version only on completion and on W5.
