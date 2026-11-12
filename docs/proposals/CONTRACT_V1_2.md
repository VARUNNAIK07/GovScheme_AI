# Contract v1.2: what changed, who does what

**Author:** A, 2026-10-12. **Status:** contract files implemented and tested in A's checkout. **Not yet reviewed by B or C.**
All changes are append-only: new optional fields and new models. Nothing was renamed or removed.

## 1. Contract changes (`contracts/schemas.py` + `contracts/types.ts`)

| Change | Why (which workflow breaks without it) | Writer → reader |
|---|---|---|
| `Scheme.fact_citations: dict[str, list[str]] = {}` | W4: comparison cells must cite sources; facts had no citations in the contract (the DB already had them) | A → Comparison, UI |
| `Scheme.limitations: list[str] = []` | W4 `limitations` field had no source | A → Comparison |
| `Candidate.need_similarity: float \| None = None` | W2: score part N needs embeddings; Scoring has no embedder | Retrieval (A) → Scoring (B) |
| `DocumentMeta.is_current: bool = True` | W6: replaced documents must stay citable but not retrieved (DB column already existed) | A |
| `RefreshResult {changed_docs, affected_schemes, invalidated_runs}` | W6 / `POST /api/admin/refresh` had no shape | A (`refresh.py`) + B (`invalidated_runs`) |
| `WorkflowState.schemes`, `.rules`, `.refresh` | W2/W3/W4: Eligibility needs rules, Scoring/Summary/Comparison need Scheme; none were on the state | **Controller (B)** loads them before agents run; agents only read |
| `Question.option_labels: dict[str, str] = {}` | W1: codes like `IN-UP` need display text | Profiling (B) → UI |
| API bodies: `ErrorBody`, `ErrorResponse`, `PublicUser`, `RegisterRequest`, `LoginRequest`, `AuthResponse`, `Me`, `OnboardingNext`, `AnswerRequest`, `AnswerResponse`, `ProfileUpdateRequest`, `ProfileUpdateResponse`, `SchemeDetail`, `ComparisonRequest`, `ComparisonResponse`, `RefreshRequest`, `HealthResponse` | Section 5 shapes were untyped | B returns them, C consumes them |
| `contracts/semantics.py` (new) | One executable definition of the section 9 rules (see 3) | B calls it (or matches it exactly) |
| `constants.py`: `SCORE_WEIGHTS`, `ELIGIBILITY_FIT`, `SCORE_UI_LABEL`, `LIBRARY_TOP_N/MORE_N`, `FACT_KIND_BY_FIELD` | Frozen section 9 numbers in one place | all |

Reused instead of duplicated: `GET /api/profile` → `Profile`, `GET /api/library` → `LibraryResult`,
`GET /api/comparison/options` → `LibraryCard[]` (TS alias `ComparisonOptions`), `GET /api/citations/{id}` → `CitationTarget`.

**Signature change (A's own function):** `summarize_scheme(scheme, eligibility, evidence, attrs)`. `attrs` is `ProfileAttributes`.
The general sections are written by the LLM from evidence only. The **relevance** section is built without the LLM, from
`eligibility.checks` (reason + the rule's citation). The profile is never sent to the LLM. Uncited sentences are dropped.
**B's stub (`agents/stubs.py`) must use this 4-argument signature.**

## 2. Rule meaning (now written down and tested)

`RuleCheck.result` is always from the **user's** point of view:

| result | `required` rule | `exclusion` rule |
|---|---|---|
| `pass` | condition met | exclusion does **not** apply |
| `fail` | condition not met | exclusion **applies** |
| `unknown` | profile field missing (**never** `fail`) | same |
| `ambiguous` | operator `manual` → needs official check | same |

Status order (section 9, unchanged): any `fail` → NOT_ELIGIBLE; all `pass` → ELIGIBLE; any `unknown` → PARTIALLY_ELIGIBLE;
else (pass + ambiguous) → NEEDS_VERIFICATION; no rules → NEEDS_VERIFICATION ("Eligibility criteria not extracted yet").
Code: `semantics.rule_result()` and `semantics.eligibility_status()`. Tests: `backend/tests/test_contract_semantics.py`.

## 3. Scoring corrections for B (formula and weights unchanged)

`match = round(100 * (0.35P + 0.30E + 0.20N + 0.15B))`. Use `semantics.match_percent()`.

* **P (profile):** matched tags ÷ the scheme tags that **this profile can evaluate**. Tags with no profile rule
  (`artisan`, `shg`, ...) and tags whose field is missing (e.g. `bpl` when `is_bpl` is null) are left out of the denominator.
  If no tag is evaluable, P = 0. Use `semantics.profile_relevance()`.
* **B (benefit):** 1.0 if the primary sector **or any secondary sector** is in `sectors_of_interest`, else 0. It's binary, so nothing is counted twice.
  Use `semantics.benefit_relevance()`. (`secondary_sectors` already existed in v1.1.)
* **N (need):** `semantics.need_relevance(candidate.need_similarity)`. Scoring must **not** load an embedding model.
* **E, tie-break, library rules:** unchanged (`ELIGIBILITY_FIT`, `semantics.ranking_key`, top 5 non-NOT_ELIGIBLE, more ≤ 5 with `match_percent = null`).
* UI label stays **"relevance match"** (`SCORE_UI_LABEL`).
* Question for B: P and B now give different numbers than a naive v1 would. Should `ScoreResult.formula_version` be `"v1.1"` so old cached runs are recognisable? The default was left at `"v1"`.

## 4. Database

| Need | Migration? | Status |
|---|---|---|
| `documents.is_current` | No: column + unique "one current per source" index already in 0001 | exists |
| `Scheme.fact_citations` for summary/benefits/documents/steps | No: `scheme_facts.citation_id` already exists | exists |
| citations for `max_benefit_inr` and `limitations` | **Yes:** `scheme_facts.kind` CHECK must allow `max_benefit`, `limitation` | **applied 2026-10-13** (`backend/migrations/versions/0002_scheme_fact_kinds.py`, `alembic current` = 0002); **B to review** |
| `WorkflowState.schemes/rules/refresh` | No: `workflow_runs.state` is JSONB | n/a |
| new optional profile fields (see 6) | No: `profiles.attributes` is JSONB | n/a |

Supabase is now at revision 0002 and the `xfail` marker on `test_fact_kinds_storable` has been removed (the test passes).

Versioning rule (implemented in `ingestion/` by A): a new version becomes current only after it reaches `indexed`.
Until then the old version stays current. Old chunks are never deleted, so `citations.resolve()` (which does not filter
on `is_current`) still opens them, while `qdrant_store.search()` filters `is_current = true`.

## 5. Tasks

**B (backend):**
1. Controller: before W2/W3/W4 run, fill `state.schemes` and `state.rules` (keyed by `scheme_id`; `rules[id] = []` when none).
2. Eligibility/Scoring: use `contracts/semantics.py` (rule meaning, status order, P/B/N/E, `match_percent`, `ranking_key`).
3. Stubs: `summarize_scheme(scheme, eligibility, evidence, attrs)`; fixtures in `contracts/fixtures/` are ready.
4. API: return the new response models. One exception handler for HTTPException, RequestValidationError and
   unhandled errors that always returns `ErrorResponse` (`{"error": {"code", "message"}}`), with no stack traces.
   `Me.user` / `AuthResponse.user` = `PublicUser` (never `password_hash`).
5. `POST /api/admin/refresh` → `RefreshResult` (A's `refresh.py` gives `changed_docs` + `affected_schemes`; B adds `invalidated_runs`).
6. Profiling: fill `Question.option_labels` (sectors → `constants.SECTORS`, states → `constants.STATES`).
7. Review migration 0002 (already applied to Supabase by A, since B owns migrations: please confirm or object).
8. W3: include the chunks cited by `eligibility.checks` in `state.evidence[scheme_id]`, so relevance sentences survive validation.

**C (frontend):**
1. Import the new types from `contracts/types.ts` (`SchemeDetail`, `ComparisonResponse`, `OnboardingNext`, `AnswerResponse`, `Me`, `AuthResponse`, `ErrorResponse`, `HealthResponse`, ...).
2. Show `option_labels[code] ?? code`; always send the **code** back as the answer.
3. v1.2 fields are optional in TS (`?`): read them with fallbacks (`scheme.limitations ?? []`).
4. Error handling: read `error.code` / `error.message` from every non-2xx response.
5. MSW: serve `contracts/fixtures/*.json` (ignore keys starting with `_`). `citation.json` points at `fixtures/sample.pdf`
   page 1 with a real bbox (origin bottom-left: flip y for the canvas).
6. Label the score "relevance match".

## 6. Open questions

1. **Manual exclusions block ELIGIBLE (found by A in real PDFs).** PM-KMY, PM-KISAN, APY and PM-SYM exclude income-tax payers,
   people covered by NPS/ESIC/EPFO, holders of constitutional posts, etc. The profile has no field for these, so they become
   `manual`. Under the section 9 order, one `manual` rule means the scheme can never be ELIGIBLE.
   Proposal (needs B + team approval; append-only, no migration): optional profile fields `is_income_tax_payer: bool | None`,
   `covered_by_statutory_social_security: bool | None`, asked only when relevant. **Not added yet.**
2. `Me.profile_version` is `int` per section 5, but a new user has no profile row (`profiles.version >= 1`). B: create version 1
   at registration, or return 0? (Contract keeps `int`.)
3. Units: some schemes define land in hectares but the profile stores `land_holding_acres`. The extractor converts to acres (A).
4. `formula_version` default (see 3).

## 7. Message draft for B and C (not sent)

> **Contracts v1.2 are ready for review: please pull `contracts/`.** Append-only; nothing renamed or removed.
> **Added:** `Scheme.fact_citations` + `Scheme.limitations`, `Candidate.need_similarity`, `DocumentMeta.is_current`,
> `RefreshResult`, `WorkflowState.schemes/rules/refresh`, `Question.option_labels`, and typed API bodies for every
> section 5 endpoint (`SchemeDetail`, `ComparisonResponse`, `OnboardingNext`, `AnswerResponse`, `Me`, `AuthResponse`,
> `ErrorResponse`, `HealthResponse`, requests). New `contracts/semantics.py` = the section 9 rules as code. Same
> formula/weights, but P now ignores tags the profile can't evaluate, and B counts secondary sectors.
> **Changed signature:** `summarize_scheme(scheme, eligibility, evidence, attrs)`.
> **B:** controller fills `state.schemes`/`state.rules`; use `semantics.py` in eligibility/scoring; update the summary stub;
> return `ErrorResponse` from one exception handler; `PublicUser` in auth/me; refresh → `RefreshResult`; fill `option_labels`;
> review migration 0002, already applied (widens `scheme_facts.kind`, no data change).
> Decisions needed: optional `is_income_tax_payer` / `covered_by_statutory_social_security` profile fields (manual
> exclusions currently block ELIGIBLE everywhere), `Me.profile_version` for new users, `formula_version`.
> **C:** use the new TS types; show `option_labels[code] ?? code`; read v1.2 fields with fallbacks; parse
> `{"error": {code, message}}`; MSW can serve `contracts/fixtures/*.json` now (real PMSBY evidence + `sample.pdf`).
> Details: `docs/proposals/CONTRACT_V1_2.md`. Tests: `pytest` (drift checker `test_contracts_ts_sync.py` fails if
> `schemas.py` and `types.ts` disagree).
