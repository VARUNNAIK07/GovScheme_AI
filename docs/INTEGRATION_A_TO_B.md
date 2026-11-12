# Integrating Person A's knowledge layer into Person B's backend

> **Status 2026-10-13: DONE.** Person B's code is integrated into `backend/app/` (see `docs/BACKEND.md`). `person_B/` is no longer referenced and can be deleted.

B's `backend/app/agents/registry.py` is the single switch. With `USE_STUBS=false` it should call
these functions instead of `agents/stubs.py`. All return contract models from `contracts/schemas.py`.
Everything here is read-only for B and needs only `.env` (DATABASE_URL, QDRANT_URL/KEY, LLM keys).

| B registry method (today: stub) | Person A function | Notes |
|---|---|---|
| `schemes()` | `knowledge.scheme_store.load_schemes(scheme_ids=None) -> dict[str, Scheme]` | Includes `fact_citations`, `limitations`, `secondary_sectors`, `benefit_types`, `states`, current `doc_ids`. Rejected facts never returned. |
| `rules()` | `knowledge.scheme_store.load_rules(scheme_ids=None) -> dict[str, list[EligibilityRule]]` | A scheme with no rules is absent → B's `evaluate()` gives NEEDS_VERIFICATION. `_unmapped` rules always have operator `manual`. |
| `candidates()` | `knowledge.retrieval.retrieve_candidates(profile: Profile, top_k=30) -> list[Candidate]` | **Needs the profile** (signature change in B's registry). Pool = schemes open in `profile.attributes.state` + `ALL`. Sector-of-interest schemes always included (score 0 if no hit). `need_similarity` set when `needs` and a summary exist. Deterministic. |
| `evidence()` | `knowledge.retrieval.get_evidence(scheme_id, query, k=6) -> list[Evidence]` | Current versions only. For W3 use the scheme name or the user's question as `query`. |
| `compare(scheme_ids)` | `knowledge.comparison.compare(schemes, eligibility) -> ComparisonMatrix` and `comparison.evidence_for_matrix(matrix) -> list[Evidence]` | Deterministic from cited facts; `value=None` = "Not stated in source". Insights: `summary.explain_comparison(matrix, evidence)`. |
| `summarize_scheme(...)` | `knowledge.summary.summarize_scheme(scheme, eligibility, evidence, attrs)` | Owned by the contracts session; uses `knowledge.llm.complete_json`. |
| `api/citations.resolve` | `knowledge.citations.resolve(citation_id) -> CitationTarget` | Unknown id → `KeyError` (map to 404). |
| `GET /api/documents/{doc_id}/file` | read `documents.local_path` (via `document_meta_v`) under `DOCS_DIR` | Serve with `application/pdf`. Local disk only for now. |
| `api/admin.refresh` | `ingestion.refresh.run(doc_id=None) -> RefreshResult` | Fills `changed_docs`, `affected_schemes`; B adds `invalidated_runs` (`workflow_runs.scheme_ids && affected_schemes`). Slow (re-downloads sources): run as a background job. |
| `api/health` | `ingestion.preflight.check_database()`, `check_qdrant()`; LLM: `knowledge.llm.configured_providers()` | Each raises on failure → map to `"down"`. |

## Changes needed on B's side (from reviewing `person_B/`)
1. Use the shared `backend/app/core/config.py`, `db/models.py`, `db/session.py` (do not overwrite them); replace `InMemoryRepository` with SQL on `users`, `profiles`, `workflow_runs`, `comparison_sessions`.
2. `candidates()` must take the profile.
3. Question bank: add a free-text `needs` question (else score N is always 0) and offer all 36 states/UTs (`constants.STATES`).
4. Consider creating a new profile version only on completion and on W5, not per onboarding answer.
