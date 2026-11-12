# API Specification (Section 5)

Base URL: `/api` (or configured via `VITE_API_BASE`)
Auth: `Authorization: Bearer <JWT>` (all endpoints except `/auth/register`, `/auth/login`, and `/health`)
Error format: `{"error": {"code": "...", "message": "..."}}`

## Endpoints

| Method | Path | Request Body | Response Body | Workflow |
|---|---|---|---|---|
| `POST` | `/api/auth/register` | `{email, password, name}` | `{token, user}` | - |
| `POST` | `/api/auth/login` | `{email, password}` | `{token, user}` | - |
| `GET` | `/api/me` | - | `{user, profile_complete, profile_version}` | - |
| `GET` | `/api/onboarding/next` | - | `{done, question: Question \| null}` | W1 |
| `POST` | `/api/onboarding/answer` | `{field, value}` | `{ok, errors, done, question}` | W1 |
| `GET` | `/api/profile` | - | `Profile` | - |
| `PUT` | `/api/profile` | `{attributes: partial ProfileAttributes}` | `{profile, library: LibraryResult}` | W5 → W2 |
| `GET` | `/api/library` | - | `LibraryResult` (top 5 with %, up to 5 more without %) | W2 |
| `GET` | `/api/schemes/{scheme_id}` | - | `{scheme, eligibility, summary, evidence}` | W3 |
| `GET` | `/api/comparison/options` | - | `LibraryCard[]` (same top 5 cards) | - |
| `POST` | `/api/comparison` | `{scheme_ids: string[]}` (2 to 5 IDs) | `{matrix, insights, evidence}` | W4 |
| `GET` | `/api/citations/{citation_id}` | - | `CitationTarget` | - |
| `GET` | `/api/documents/{doc_id}/file` | - | PDF bytes (`application/pdf`) | - |
| `POST` | `/api/admin/refresh` | `{doc_id?}` | `{changed_docs, affected_schemes, invalidated_runs}` | W6 |
| `GET` | `/api/health` | - | `{postgres, qdrant, llm}` | - |
