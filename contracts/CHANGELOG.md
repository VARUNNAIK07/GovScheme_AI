# Contract changelog

One line per change. Append-only after the freeze: add optional fields, never rename or remove.

- 2026-10-12 (A) v1.0: `schemas.py` written from build plan section 4. Fields with `X | None` given default `None` (and lists `[]`) so partial onboarding profiles validate.
- 2026-10-12 (A) v1.0: `status`/`eligibility_status` typed as `EligibilityStatus` literal (was `str`); values unchanged.
- 2026-10-12 (A) v1.0: `TraceStep` defined (referenced in `WorkflowState` but missing from the plan). **B to confirm.**
- 2026-10-12 (A) v1.1: `Scheme` + optional `secondary_sectors`, `benefit_types`, `max_benefit_period`.
- 2026-10-12 (A) v1.1: `DocumentMeta` + optional `language`, `text_layer`, `fetch_method`, `error`.
- 2026-10-12 (A) v1.1: Clarified `Evidence.bbox` origin = bottom-left (PDF points); `chunk_id` page = start page, `n` 0-based per page. **C: flip y for canvas.**
- 2026-10-12 (A) v1.1: Vocabularies fixed in `constants.py`: 10 sectors (approved taxonomy), beneficiary tags, benefit types, ISO 3166-2:IN state codes, `_unmapped` rule field. **B, C: `sectors_of_interest` and `state` must use these values.**

### v1.2 (A, 2026-10-12): details and tasks in `docs/proposals/CONTRACT_V1_2.md`
Status key: **impl** = in the files · **tested** = covered by a passing test · **reviewed** = B/C agreed (none yet) · **proposed** = not in the files yet.

- (impl, tested) `Scheme.fact_citations: dict[str, list[str]] = {}` (keys = `constants.FACT_KIND_BY_FIELD`) and `Scheme.limitations: list[str] = []`. Every id must be a real stored chunk.
- (impl, tested) `Candidate.need_similarity: float | None = None`: computed by Retrieval with the shared embedder; Scoring uses it as N and loads no model.
- (impl, tested) `DocumentMeta.is_current: bool = True` (DB column already existed). A new version becomes current only after it is indexed; old chunks stay resolvable, retrieval filters them out.
- (impl, tested) New `RefreshResult {changed_docs, affected_schemes, invalidated_runs}` = W6 result = `POST /api/admin/refresh` body.
- (impl) `WorkflowState.schemes: dict[str, Scheme]`, `rules: dict[str, list[EligibilityRule]]`, `refresh: RefreshResult | None`: written only by the controller (B), read by agents.
- (impl, tested) `Question.option_labels: dict[str, str] = {}`: `options` stay machine codes; UI falls back to the code.
- (impl, tested) API bodies for section 5: `ErrorBody`, `ErrorResponse`, `PublicUser`, `RegisterRequest`, `LoginRequest`, `AuthResponse`, `Me`, `OnboardingNext`, `AnswerRequest`, `AnswerResponse`, `ProfileUpdateRequest`, `ProfileUpdateResponse`, `SchemeDetail`, `ComparisonRequest`, `ComparisonResponse`, `RefreshRequest`, `HealthResponse` (+ TS alias `ComparisonOptions = LibraryCard[]`).
- (impl, tested) `RuleCheck.result` meaning fixed (user's point of view; exclusion applies = `fail`; missing field = `unknown`; `manual` = `ambiguous`). Status order unchanged. Code: `contracts/semantics.py`.
- (impl, tested) Scoring definitions in `contracts/semantics.py` + `constants.SCORE_WEIGHTS/ELIGIBILITY_FIT`. Formula and weights unchanged. P denominator = only the tags this profile can evaluate; B counts primary or secondary sectors (binary). **B to review.**
- (impl, tested) Signature: `summarize_scheme(scheme, eligibility, evidence, attrs)`. Relevance is built from eligibility checks (no LLM, no profile sent to the LLM). **B: update stub.**
- (impl, tested) TS: v1.2 fields are optional (`?`) for rollout; `backend/tests/test_contracts_ts_sync.py` fails on any Python/TS drift.
- (impl, tested) Fixtures: `contracts/fixtures/*.json` (+ `sample.pdf`, the official PMSBY Rules PDF), built by `python -m contracts.fixtures.build_fixtures` from real chunks; `contracts/personas.json` (3 synthetic personas).
- (impl, tested) Migration 0002: `scheme_facts.kind` += `max_benefit`, `limitation`. Applied to Supabase 2026-10-13 by A's pipeline session (`alembic current` = 0002 head; file identical to the proposal). **B to review** (B owns migrations).
- (impl, tested) 2026-10-13: `summary._default_llm` adapted to `llm.complete_json(system, user, schema) -> LLMResult` (schema `SummaryDraft`); `citations._db_lookup` reuses `scheme_store.load_evidence`.
- (proposed) Optional profile fields `is_income_tax_payer`, `covered_by_statutory_social_security` so common exclusions stop forcing `manual`. **Needs B + team decision.**
