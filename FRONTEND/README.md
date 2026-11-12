# GovScheme AI — National Welfare Scheme & Evidence System

GovScheme AI is a civic decision-support portal that evaluates citizen eligibility for Indian government welfare programs deterministically, backed by verified, citation-grounded evidence from official scheme gazettes and guidelines.

Unlike generic chatbot assistants, **GovScheme AI separates deciding from explaining**:
1. **Deciding is deterministic:** Mathematical formulas and Python eligibility rules (not an LLM) evaluate eligibility and ranking.
2. **Explaining is grounded:** Every generated sentence is verified against extracted evidence chunks and carries clickable citation chips linking to exact bounding boxes inside official source PDFs.

---

## 1. System Architecture & Team Split

The system is architected across three decoupled layers coordinated through frozen contracts:

```
┌─────────────────────────────────────────────────────────────┐
│                 Experience Layer (React)                    │
│   Auth • Onboarding • Library • Detail • Compare • PDF.js   │
└──────────────────────────────┬──────────────────────────────┘
                               │ REST /api + JWT
┌──────────────────────────────▼──────────────────────────────┐
│                  Agent Layer (FastAPI)                      │
│        Workflow Controller (Blackboard / WorkflowState)     │
│   Profiling • Eligibility • Scoring • Comparison • Summary  │
└──────────────────────────────┬──────────────────────────────┘
                               │ SQL & Vector Retrieval
┌──────────────────────────────▼──────────────────────────────┐
│              Knowledge Layer (Offline Pipeline)             │
│        PostgreSQL (Schemes & Rules) • Qdrant (Chunks)       │
└─────────────────────────────────────────────────────────────┘
```

### Module Ownership Boundaries
* **Member A — Knowledge & Evidence:** `ingestion/`, `data/`, `backend/app/knowledge/`.
* **Member B — Brain & Backend:** `backend/app/` (except `knowledge/`), `backend/migrations/`.
* **Member C — Experience & Delivery (This Module):** `frontend/`, `tests/e2e/`, `docker-compose.yml`, `README.md`, `.env.example`, `Makefile`.
* **Shared (Frozen Hour 0):** `contracts/schemas.py`, `contracts/types.ts`, `contracts/constants.py`, `contracts/personas.json`, `contracts/fixtures/`.

---

## 2. Quickstart & Setup

### Prerequisites
* **Node.js** >= 20.0
* **Docker & Docker Compose**
* **Python** >= 3.11 (for backend and ingestion scripts)

### Environment Configuration
Copy the sample environment file:
```bash
cp .env.example .env
```

Key environment settings:
* `VITE_API_BASE`: When empty or set to `mock`, the frontend automatically operates in mock mode using **Mock Service Worker (MSW)** and `contracts/fixtures/`.
* Setting `VITE_API_BASE=http://localhost:8000` switches the frontend to the live FastAPI backend in a single environment variable change.

---

## 3. Knowledge Ingestion Pipeline Order

Before running the live multi-agent backend without stubs, the offline ingestion pipeline must be executed in the following sequential order:

```bash
# 1. Audit existing PDFs for duplicates and generate document registry
python -m ingestion.audit_corpus

# 2. Scrape missing PDFs from allowlisted government domains (*.gov.in)
python -m ingestion.scrape

# 3. Parse PDFs with Docling (preserving bounding boxes and section hierarchy)
python -m ingestion.parse

# 4. Generate section-aware chunks (~300-500 tokens)
python -m ingestion.chunk

# 5. Compute BGE embeddings (BAAI/bge-small-en-v1.5) and index into Qdrant
python -m ingestion.embed_index

# 6. Extract structured Scheme and EligibilityRule records into PostgreSQL
python -m ingestion.extract_facts

# Or execute all stages sequentially:
python -m ingestion.run_all
```

---

## 4. Running the Application

### Option A: Frontend Development with Mock Service Worker (Standalone)
Ideal for UI development and verification without running backend databases:
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173). MSW will intercept `/api/*` routes and serve validated fixtures from `contracts/fixtures/`.

### Option B: Full Stack with Docker Compose
Starts PostgreSQL, Qdrant vector database, FastAPI backend, and Nginx-served React frontend:
```bash
docker compose up -d --build
```
Service ports:
* **Frontend:** [http://localhost:5173](http://localhost:5173)
* **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **Qdrant Vector DB:** `http://localhost:6333`
* **PostgreSQL:** `localhost:5432`

---

## 5. Testing

### Frontend Build & Typecheck
```bash
cd frontend
npm run build
```

### End-to-End Tests (Playwright)
The automated Playwright test walks the entire Definition of Done using the benchmark persona from `contracts/personas.json` (Ramesh Patel — Smallholder Farmer):
1. **Registration** (`/register`)
2. **Onboarding Questionnaire** (`/onboarding` — one question per screen with live progress)
3. **Scheme Library** (`/library` — Top 5 'relevance match' cards + More in your sectors)
4. **Scheme Detail** (`/schemes/pm-kisan` — overview, pass/fail checks, numbered citation chips)
5. **Document Citation Viewer** (`/viewer/:doc_id` — PDF.js page jump + bounding box highlight)
6. **Comparison Matrix** (`/comparison` — 2–5 scheme matrix with cited cells + insight synthesis)
7. **Profile Update** (`/profile` — PUT `/api/profile` and immediate library refresh)

To execute the test:
```bash
cd frontend
npx playwright test
```

---

## 6. Deployment & Health Checks

For production deployment:
```bash
# Verify health of system components
curl http://localhost:8000/api/health
# Returns: {"postgres": "ok", "qdrant": "ok", "llm": "ok"}
```

The frontend Docker container uses a multi-stage Alpine Nginx build with HTML5 push-state SPA routing fallback and upstream API proxying.
