# Backend: run, test, and how it is wired

## Run (from the repo root)
```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload --port 8000
```
Interactive API docs: http://localhost:8000/docs · Health: http://localhost:8000/api/health

## Test
```powershell
python -m pytest -q          # 169 tests; API tests use an in-memory repo + stubs (no DB writes)
```

## `.env` keys the backend uses
`DATABASE_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `GROQ_*` / `GEMINI_*` / `LLM_PROVIDER_PRIORITY`, `JWT_SECRET`,
`USE_STUBS` (`false` = real knowledge layer, `true` = contracts/fixtures), optional `JWT_ISSUER`, `JWT_TTL_S`, `CORS_ORIGINS`.

## How Person B's code is connected (integrated 2026-10-13)
| Layer | Files | Connected to |
|---|---|---|
| API (16 endpoints: section 5 + `POST /api/profile/questions`) | `main.py` (routes), `api/*.py` (B's service functions), `api/deps.py` (JWT → user) | contract error shape via `core/errors.py` |
| Controller W1–W6 | `controller/workflow.py`, `controller/cache.py` | cache = memory LRU + `workflow_runs` (keyed by profile_version) |
| Agents (deterministic) | `agents/profiling.py`, `eligibility.py`, `scoring.py`, `question_bank.json` | `contracts/semantics.py` |
| Registry (A↔B switch) | `agents/registry.py` | stubs ↔ `knowledge/` (retrieval, scheme_store, comparison, summary, citations) |
| Persistence | `db/repositories.py` (SQL; was in-memory) | shared `db/session.py`, `db/models.py` |
| Auth | `core/security.py` (B's PBKDF2 + HS256 JWT) | shared `core/config.py` |

Changes made while connecting (B's behaviour kept otherwise):
* `candidates()` takes the profile; library loads only retrieved schemes; `build_library` follows section 9
  (top 5 by match among not NOT_ELIGIBLE; "more" = sector matches by retrieval score, no %).
* Question bank: all 36 states/UTs; new multi-choice `needs` question; answers validated (`validate_answer`).
* W3 summary falls back to stored, cited facts when the LLM is unavailable; W4 insights are deterministic and cited.
* Cached results never reused across profile versions; W5 invalidates the user's runs; W6 invalidates runs
  that used affected schemes.

## Dynamic questioning agent (`agents/profiling.py` + `question_bank.json`)
Each question can carry conditions evaluated against the answers so far
(`equals`, `in`, `not_in`, `gte`, `lte`, `all`, `any`, `not`; an unanswered field never matches):
* `show_if` — ask only when it applies (land size → farmers; education → students or age ≤ 25;
  disability % → disabled; marital status → age ≥ 18).
* `text_if` — reword the question for this person.
* `option_show_if` — offer only relevant options (e.g. pension for age ≥ 40/widowed/disabled, scholarship for students/age ≤ 30).
Changing an answer clears follow-ups that no longer apply (`prune_hidden`), in onboarding and on `PUT /api/profile`.
`PUT /api/profile` validates every sent value like onboarding (422 `validation_error`).

`POST /api/profile/questions` — body `{"attributes": {...partial draft...}}` → `Question[]` that apply to that draft
(nothing is saved). The profile page calls it as the user edits, so the form changes with the answers.

## Frontend (`frontend/frontend`)
```powershell
cd frontendrontend; npm install; npm run dev      # http://localhost:5173
```
`.env.local` sets `VITE_API_BASE=http://localhost:8000` (live backend). Remove it to use the MSW mocks.
Signed-in users with an incomplete profile are sent to `/onboarding` (only `/onboarding` and `/profile` are open until done).

## Known limits / decisions for later
* **Latency:** Supabase is in Seoul (~250 ms per DB round trip from here). First library build ≈ 11 s, cached
  ≈ 0.5 s. Moving the project to Mumbai (ap-south-1) would cut most of the remaining time.
* Each onboarding answer creates a profile version (B's design; ~13 rows per user). Works; could be reduced.
* `/api/admin/refresh` requires login but there is no admin role yet; it is slow (re-downloads sources).
* Single server process assumed for the in-memory cache layer (the DB cache is shared and authoritative).
