# GovScheme AI — Methodology & Architecture

GovScheme AI helps an Indian citizen find the government schemes that fit them. The user answers a short,
adaptive questionnaire. The system then ranks schemes they may qualify for, explains each one in plain
language, and backs every sentence with a citation that opens the official PDF at the exact page.

---

## 1. Methodology

### 1.1 Design principles

| Principle | What it means in this project |
|---|---|
| **Evidence first** | Every claim shown to a user cites a chunk of an official government PDF. A sentence without a valid citation is dropped, never shown. |
| **Deterministic decisions, LLM only for language** | Eligibility, scoring, ranking and comparison are plain Python rules. The LLM only (a) proposes facts/rules during offline extraction and (b) writes readable summaries from retrieved evidence. |
| **"LLM proposes, code decides"** | LLM output is validated against schemas, citations and word overlap before anything is stored or shown. |
| **Contracts first** | `contracts/` (Pydantic `schemas.py`, TypeScript `types.ts`, `constants.py`, `semantics.py`) is the single shared definition of data shapes and rules for all three team members. |
| **Privacy** | The user's profile is never sent to the LLM. Personal relevance sentences come from deterministic eligibility checks. |
| **Honest uncertainty** | Missing data gives `PARTIALLY_ELIGIBLE` / `NEEDS_VERIFICATION`, and a missing fact reads "Not stated in source". The system never guesses. The match % is labelled a *relevance match*, not a chance of approval. |
| **Polite, lawful collection** | An allowlist of official hosts, robots.txt respected, rate limiting, a contact email in the User-Agent, and no UA spoofing. Hosts that block bots go to a manual browser download into `data/inbox/`. |
| **Reproducible & versioned** | Content-hashed document IDs, versioned chunker/prompt/formula, and `extraction_runs` / `ingestion_events` audit tables. Old citations keep resolving after a document changes. |

### 1.2 Phases of work

1. **Phase 1: research & proposal.** Build a sector/tag taxonomy, shortlist schemes, check every source link,
   and review the contracts and DB. Findings that shaped the design: some gov.in hosts return 403 or broken TLS
   chains, so `truststore` is used and blocked hosts go to manual download. MGNREGA was repealed and replaced
   by VB-G RAM G.
2. **Phase 2: offline knowledge pipeline (Person A).** Scrape, parse, chunk, embed and index the PDFs, load
   PostgreSQL, then extract facts and rules with the LLM.
3. **Phase 3: online agents + API (Person B).** Workflow controller W1–W6, deterministic agents, FastAPI, JWT auth.
4. **Phase 4: frontend & delivery (Person C).** React/Vite UI, onboarding, library, detail, comparison, PDF viewer.
5. **Phase 5: integration & evaluation.** Switch `USE_STUBS=false`, run the 169 pytest tests and the golden set
   (`backend/tests/golden.json`), and check the import graph and contract sync between Python and TypeScript.

### 1.3 Data methodology

* **Sources:** official central and state scheme guideline PDFs (seeded in `ingestion/seeds/schemes.csv` and
  `sources.csv`; 81 seeded schemes, about 70 documents indexed).
* **Parsing:** Docling handles layout, headings, tables and bounding boxes. A pypdfium2 text-layer check means
  OCR runs only on scanned pages. A quality gate rejects empty, garbled or non-English documents.
* **Chunking:** Docling HybridChunker splits by section and never across a heading. Chunks are at most 480 BGE
  tokens. A 40-token overlap is added *only* to the embedded text; the cited text stays the exact source text.
  TOC, form-filler and Devanagari-heavy chunks are removed.
* **Embedding:** `BAAI/bge-small-en-v1.5` (384-d, cosine, normalised) runs on CPU. Queries get the BGE
  instruction prefix.
* **Fact & rule extraction:** the LLM reads the top chunks per topic and returns JSON. Code then:
  drops items citing chunks it was not shown; flags items with less than 50% word overlap with the cited chunk;
  converts rules that use an unknown field or wrong type into `manual` rules (→ NEEDS_VERIFICATION). Facts and
  rules a human marked `verified` are never overwritten.

### 1.4 Decision methodology

**Eligibility** (`contracts/semantics.py`): each rule is `field operator value` and either `required` or `exclusion`.
The scheme status follows this precedence:
`no rules → NEEDS_VERIFICATION` → `any fail → NOT_ELIGIBLE` → `all pass → ELIGIBLE` → `any unknown → PARTIALLY_ELIGIBLE` → else `NEEDS_VERIFICATION`.

**Match score** (frozen formula, `docs/SCORING.md`):

```
match % = round(100 × (0.35·P + 0.30·E + 0.20·N + 0.15·B))
P = profile relevance   matched beneficiary tags / tags the profile can evaluate
E = eligibility fit     ELIGIBLE 1.0 · PARTIAL 0.6 · NEEDS_VERIFICATION 0.5 · NOT_ELIGIBLE 0
N = need relevance      cosine(BGE(user needs), BGE(scheme summary))
B = benefit relevance   1 if scheme's primary/secondary sector is in user's interests
```

**Library:** top 5 by match among schemes that are not NOT_ELIGIBLE (ties broken by scheme_id). "More in your
sectors" lists up to 5 sector matches ordered by retrieval score, without a %.

### 1.5 Evaluation & quality

* 169 pytest tests: contracts, eligibility, scoring, retrieval, citations, extraction, controller, API, refresh,
  and the import graph.
* A golden persona set (`contracts/personas.json`, `backend/tests/golden.json`) with expected outcomes.
* `ingestion/audit_corpus.py` writes `data/logs/audit_report.json` with per-document pipeline status.
* An agent trace (`TraceStep`: agent, status, duration) is recorded for every workflow run.

---

## 2. Architecture (normal / layered view)

### 2.1 Tech stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Vite + Tailwind; MSW mocks; pdf.js document viewer |
| API | FastAPI (16 endpoints), PBKDF2 passwords + HS256 JWT |
| Orchestration | `WorkflowController` (W1–W6) with a memory LRU and a `workflow_runs` DB cache |
| Agents | Profiling, Retrieval, Eligibility, Scoring, Summary, Comparison, Citation |
| Knowledge layer | `backend/app/knowledge/` (embedder, qdrant_store, retrieval, scheme_store, summary, comparison, citations, llm) |
| Relational store | PostgreSQL (Supabase) + SQLAlchemy + Alembic |
| Vector store | Qdrant Cloud, collection `scheme_chunks` |
| LLMs | Groq (primary) → Gemini (fallback), JSON-only output |
| Offline pipeline | `ingestion/` with Docling, sentence-transformers, httpx + truststore |

### 2.2 System architecture

```mermaid
flowchart TB
    subgraph Client["Frontend - React/Vite"]
        UI_On["Onboarding"]
        UI_Lib["Library"]
        UI_Det["Scheme detail"]
        UI_Cmp["Comparison"]
        UI_PDF["PDF viewer with highlight"]
    end

    subgraph API["FastAPI backend - backend/app"]
        R["Routes main.py + api/*"]
        AUTH["JWT auth core/security.py"]
        CTRL["Workflow Controller W1-W6"]
        CACHE["Cache: memory LRU + workflow_runs"]
        subgraph AG["Agents"]
            A_P["Profiling"]
            A_E["Eligibility"]
            A_S["Scoring"]
        end
        REG["AgentRegistry - stubs or knowledge"]
        subgraph KN["Knowledge layer"]
            K_R["Retrieval"]
            K_SS["Scheme store"]
            K_SUM["Summary"]
            K_CMP["Comparison"]
            K_CIT["Citations"]
            K_EMB["BGE embedder"]
            K_LLM["LLM client"]
        end
    end

    subgraph Stores["Data stores"]
        PG[("PostgreSQL / Supabase")]
        QD[("Qdrant scheme_chunks")]
        FS[("data/ raw PDFs, parsed, chunks")]
    end

    subgraph LLMs["LLM providers"]
        GROQ["Groq"]
        GEM["Gemini"]
    end

    subgraph Offline["Offline ingestion - ingestion/"]
        ING["scrape - parse - chunk - embed_index - load_db - extract_facts - refresh"]
    end

    GOV["Official gov.in scheme PDFs"]

    Client -->|"HTTPS JSON + JWT"| R
    R --> AUTH
    R --> CTRL
    CTRL <--> CACHE
    CTRL --> A_P & A_E & A_S
    CTRL --> REG
    REG --> K_R & K_SS & K_SUM & K_CMP & K_CIT
    K_R --> K_EMB
    K_R --> QD
    K_SS --> PG
    K_CIT --> PG
    K_SUM --> K_LLM
    K_LLM --> GROQ
    K_LLM -.->|fallback| GEM
    CACHE --> PG
    R -->|"/api/documents/id/file"| FS

    GOV --> ING
    ING --> FS
    ING --> QD
    ING --> PG
    ING --> K_LLM
```

### 2.3 Module dependency rule (enforced by `test_import_graph.py`)

```mermaid
flowchart LR
    ING["ingestion"] --> KN["backend.app.knowledge"]
    KN --> DB["backend.app.db"]
    KN --> CORE["backend.app.core"]
    DB --> C["contracts"]
    CORE --> C
    AGT["agents / controller / api"] -->|"only via agents/registry.py"| KN
    AGT --> DB
    AGT --> CORE
    AGT --> C
```

### 2.4 Data model (main tables)

```mermaid
erDiagram
    SCHEMES ||--o{ SCHEME_TAGS : has
    SCHEMES ||--o{ SCHEME_STATES : "available in"
    SCHEMES ||--o{ SCHEME_SECONDARY_SECTORS : has
    SCHEMES ||--o{ SOURCES : "published at"
    SOURCES ||--o{ DOCUMENTS : "versions"
    DOCUMENTS ||--o{ CHUNKS : "split into"
    SCHEMES ||--o{ SCHEME_FACTS : "facts"
    SCHEMES ||--o{ ELIGIBILITY_RULES : "rules"
    CHUNKS ||--o{ SCHEME_FACTS : "cited by"
    CHUNKS ||--o{ ELIGIBILITY_RULES : "cited by"
    EXTRACTION_RUNS ||--o{ SCHEME_FACTS : produced
    USERS ||--o{ PROFILES : "versions"
    USERS ||--o{ WORKFLOW_RUNS : "cached runs"
    USERS ||--o{ COMPARISON_SESSIONS : saves
    DOCUMENTS ||--o{ INGESTION_EVENTS : logs
```

### 2.5 API surface

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/me` |
| Onboarding (W1) | `GET /api/onboarding/next`, `POST /api/onboarding/answer` |
| Profile (W5) | `GET /api/profile`, `PUT /api/profile`, `POST /api/profile/questions` |
| Library (W2) / Detail (W3) | `GET /api/library`, `GET /api/schemes/{scheme_id}` |
| Comparison (W4) | `GET /api/comparison/options`, `POST /api/comparison` |
| Citations | `GET /api/citations/{citation_id}`, `GET /api/documents/{doc_id}/file` |
| Admin (W6) / Health | `POST /api/admin/refresh`, `GET /api/health` |

---

## 3. Multi-agent workflows

The system uses a **controller-orchestrated (hub-and-spoke) multi-agent design**. Agents never call each other.
The `WorkflowController` loads what each agent needs into a shared `WorkflowState`, calls the agents in order,
records a trace step per agent, and caches the result keyed by `(workflow, user, profile_version)`.

| Agent | Kind | Responsibility |
|---|---|---|
| Profiling | deterministic | Picks the next question (`show_if`, `text_if`, `option_show_if`), validates answers, prunes follow-ups that no longer apply |
| Retrieval | deterministic + vectors | Profile → candidate schemes; scheme → evidence chunks |
| Eligibility | deterministic | Evaluates rules → `ELIGIBLE` / `PARTIALLY_ELIGIBLE` / `NOT_ELIGIBLE` / `NEEDS_VERIFICATION` |
| Scoring | deterministic | P/E/N/B components → match %, then builds the library |
| Summary | LLM + validator | Cited plain-language summary; falls back to stored facts if the LLM is down |
| Comparison | deterministic | Side-by-side matrix from verified facts, plus cited insights |
| Citation | deterministic | Validates citation IDs; resolves them to PDF page and bbox |
| Extraction (offline) | LLM + validator | Proposes facts and rules from chunks; code verifies before storing |

### 3.1 Overview: workflows W1–W6

```mermaid
flowchart TB
    U(["User / Admin"]) --> API["FastAPI"]
    API --> C{"Workflow Controller"}

    C -->|"W1 onboarding"| W1["Profiling agent - next question"]
    C -->|"W2 library"| W2["Retrieval - Eligibility - Scoring - Build library"]
    C -->|"W3 scheme detail"| W3["Eligibility - Evidence retrieval - Summary - Citation filter"]
    C -->|"W4 comparison"| W4["Eligibility - Comparison matrix - Insights - Evidence"]
    C -->|"W5 profile change"| W5["Invalidate user cache - rerun W2"]
    C -->|"W6 refresh"| W6["Re-fetch sources - re-ingest changed docs - invalidate affected runs"]

    W1 --> ST[("WorkflowState + trace")]
    W2 --> ST
    W3 --> ST
    W4 --> ST
    W5 --> W2
    ST --> CACHE[("Cache: LRU + workflow_runs<br/>key = user + profile_version")]
```

### 3.2 W1: adaptive onboarding

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as FastAPI
    participant CT as Controller
    participant PA as Profiling agent
    participant DB as PostgreSQL

    User->>FE: Start onboarding
    FE->>API: GET /api/onboarding/next
    API->>CT: onboarding_next(profile)
    CT->>PA: next_question(profile)
    PA-->>CT: Question - filtered by show_if / text_if / option_show_if
    CT-->>FE: question
    loop until profile complete
        User->>FE: answer
        FE->>API: POST /api/onboarding/answer
        API->>PA: validate_answer + prune_hidden
        API->>DB: save new profile version
        API->>PA: next_question
        API-->>FE: next question or done
    end
    FE->>FE: redirect to Library
```

### 3.3 W2: personalised library

```mermaid
sequenceDiagram
    participant API as FastAPI
    participant CT as Controller
    participant CA as Cache
    participant RG as AgentRegistry
    participant RA as Retrieval agent
    participant QD as Qdrant
    participant SS as Scheme store - PG
    participant EA as Eligibility agent
    participant SA as Scoring agent

    API->>CT: library(profile)
    CT->>CA: get W2, user, profile_version
    alt cache hit
        CA-->>CT: WorkflowState
        CT-->>API: library - served from cache
    else cache miss
        CT->>RG: candidates(profile)
        RG->>RA: retrieve_candidates
        RA->>SS: schemes_available_in(state)
        RA->>QD: search(BGE(profile query), filter scheme_id in pool, is_current)
        RA-->>CT: Candidates - retrieval_score, matched_sectors, need_similarity
        CT->>RG: schemes(ids) and rules(ids)
        RG->>SS: load metadata + eligibility rules
        CT->>EA: evaluate(attrs, scheme, rules) per scheme
        EA-->>CT: EligibilityResult per scheme
        CT->>SA: score_scheme per candidate
        SA-->>CT: match % = 0.35P+0.30E+0.20N+0.15B
        CT->>SA: build_library - top 5 + more in your sectors
        CT->>CA: set(state)
        CT-->>API: LibraryResult + trace
    end
```

### 3.4 W3: scheme detail (RAG + cited summary)

```mermaid
sequenceDiagram
    participant API as FastAPI
    participant CT as Controller
    participant EA as Eligibility agent
    participant RA as Retrieval agent
    participant QD as Qdrant
    participant PG as PostgreSQL
    participant SU as Summary agent
    participant LLM as Groq / Gemini
    participant CI as Citation validator

    API->>CT: scheme_detail(profile, scheme_id)
    CT->>PG: load scheme + rules
    CT->>EA: evaluate(profile, rules)
    CT->>RA: evidence(scheme)
    RA->>PG: load chunks cited by stored facts
    RA->>QD: top-k chunks for "name benefits eligibility"
    RA-->>CT: deduplicated Evidence list
    CT->>SU: summarize_scheme(scheme, eligibility, evidence)
    SU->>LLM: prompt with evidence passages only - no profile
    alt LLM answers
        LLM-->>SU: JSON sections with citation_ids
        SU->>CI: validate_summary - drop uncited sentences
    else LLM unavailable
        SU->>PG: summary_from_facts - stored verified facts
    end
    SU->>SU: relevance sentences from eligibility checks - no LLM
    SU-->>CT: SchemeSummary
    CT-->>API: SchemeDetail + only the cited evidence
```

### 3.5 W4: comparison

```mermaid
flowchart LR
    S["User picks 2-5 schemes<br/>from top recommendations"] --> V{"Allowed and<br/>2 to 5?"}
    V -->|no| ERR["400 error"]
    V -->|yes| L["Load schemes + rules"]
    L --> E["Eligibility agent per scheme"]
    E --> M["Comparison agent:<br/>matrix from verified facts<br/>missing = Not stated in source"]
    M --> I["Insights from matrix<br/>deterministic, cited"]
    M --> EV["evidence_for_matrix"]
    I --> R["ComparisonResponse"]
    EV --> R
    R --> SAVE[("comparison_sessions")]
```

### 3.6 W5 and W6: profile change and source refresh

```mermaid
flowchart TB
    subgraph W5["W5 - profile change"]
        P1["PUT /api/profile"] --> P2["validate + prune_hidden"]
        P2 --> P3["new profile_version"]
        P3 --> P4["invalidate all cached runs of user"]
        P4 --> P5["rerun W2 without cache"]
    end

    subgraph W6["W6 - refresh sources - admin"]
        R1["POST /api/admin/refresh"] --> R2["PoliteFetcher re-downloads auto sources"]
        R2 --> R3{"SHA-256 changed?"}
        R3 -->|no| R4["skip"]
        R3 -->|yes| R5["new document version:<br/>parse - chunk - embed - extract facts"]
        R5 --> R6["flip is_current after full index<br/>old version stays until then"]
        R6 --> R7["RefreshResult: changed_docs, affected_schemes"]
        R7 --> R8["invalidate workflow_runs using affected schemes"]
    end
```

### 3.7 Eligibility agent decision logic

```mermaid
flowchart TB
    A["Rule: field op value, kind"] --> B{"operator manual<br/>or unmapped field?"}
    B -->|yes| AMB["ambiguous"]
    B -->|no| C{"profile field<br/>missing?"}
    C -->|yes| UNK["unknown + add to missing_fields"]
    C -->|no| D{"condition true?"}
    D -->|"required + true"| PASS["pass"]
    D -->|"required + false"| FAIL["fail"]
    D -->|"exclusion + true"| FAIL
    D -->|"exclusion + false"| PASS

    PASS & FAIL & UNK & AMB --> AGG{"Aggregate all checks"}
    AGG -->|no rules| NV["NEEDS_VERIFICATION"]
    AGG -->|any fail| NE["NOT_ELIGIBLE"]
    AGG -->|all pass| EL["ELIGIBLE"]
    AGG -->|any unknown| PE["PARTIALLY_ELIGIBLE"]
    AGG -->|pass + ambiguous| NV
```

### 3.8 LLM client: provider fallback

```mermaid
stateDiagram-v2
    [*] --> Groq
    Groq --> Validate: HTTP 200
    Groq --> Groq: transient error, retry with backoff
    Groq --> Gemini: quota / auth / model missing / retries exhausted
    Gemini --> Validate: HTTP 200
    Gemini --> Gemini: transient error, retry
    Gemini --> Failed: all providers exhausted
    Validate --> Done: valid JSON for schema
    Validate --> Repair: invalid JSON
    Repair --> Done: fixed
    Repair --> InvalidOutput: still invalid
    Failed --> FallbackFacts: Summary uses stored facts
    Done --> [*]
    InvalidOutput --> [*]
    FallbackFacts --> [*]
```

---

## 4. RAG (retrieval-augmented generation)

RAG has two halves: **offline indexing** (build the knowledge base once and refresh it) and **online retrieval +
grounded generation** (per request). A citation guardrail sits between generation and the user.

### 4.1 Offline indexing pipeline

```mermaid
flowchart LR
    SEED["seeds/schemes.csv<br/>seeds/sources.csv<br/>allowlist.yaml"] --> PRE["preflight<br/>.env + connectivity"]
    PRE --> SCR["scrape<br/>PoliteFetcher: robots, rate limit,<br/>truststore TLS, size cap"]
    INBOX["data/inbox<br/>manual downloads<br/>for 403 hosts"] --> SCR
    SCR --> RAW[("data/raw<br/>doc_id = sha256 prefix")]
    RAW --> PAR["parse<br/>Docling layout, tables, bbox<br/>OCR only scanned pages<br/>quality gate"]
    PAR --> PJ[("data/parsed")]
    PJ --> CH["chunk<br/>HybridChunker, max 480 tokens<br/>+40 overlap in embed_text only<br/>drop TOC, filler, Hindi"]
    CH --> CJ[("data/chunks jsonl<br/>chunk_id = doc-pPAGE-cN")]
    CJ --> EMB["embed_index<br/>BGE-small 384-d, normalised"]
    EMB --> QD[("Qdrant scheme_chunks<br/>payload: scheme_id, doc_id,<br/>section, page, bbox, is_current")]
    CJ --> LDB["load_db"]
    LDB --> PG[("PostgreSQL<br/>schemes, sources,<br/>documents, chunks")]
    PG --> EXT["extract_facts<br/>LLM proposes, code verifies"]
    QD --> EXT
    EXT --> PG2[("scheme_facts<br/>eligibility_rules<br/>extraction_runs")]
    EXT --> AUD["audit_corpus<br/>audit_report.json"]
```

### 4.2 Online retrieval + grounded generation

```mermaid
flowchart TB
    subgraph Q["Query construction - no PII"]
        P["Profile attributes"] --> TAGS["evaluate_tags<br/>farmer, woman, SC, senior..."]
        TAGS --> QT["Query text:<br/>Government scheme for a ...<br/>needs: ... interested in: ..."]
        QT --> QE["BGE embed_query<br/>with instruction prefix"]
    end

    subgraph F["Filtered vector search"]
        POOL["Pool = active schemes<br/>in ALL + user state"] --> SRCH
        QE --> SRCH["Qdrant cosine search<br/>filter: is_current AND scheme_id in pool<br/>limit = top_k x 4"]
        SRCH --> GRP["Group by scheme<br/>score = best chunk"]
        GRP --> TOPK["top 30 schemes<br/>+ all sector-of-interest matches"]
        TOPK --> NS["need_similarity =<br/>cosine BGE needs vs scheme summary"]
    end

    NS --> CAND["Candidates to Eligibility + Scoring"]

    subgraph G["Grounded generation - W3"]
        EVQ["Evidence = chunks cited by stored facts<br/>+ top-k chunks of this scheme"] --> PR["Prompt: evidence passages only,<br/>each tagged with citation_id"]
        PR --> LLM["Groq then Gemini<br/>JSON mode"]
        LLM --> VAL["Citation validator:<br/>strip unknown ids,<br/>drop sentences with none"]
        VAL --> OUT["Cited summary sections"]
        REL["Relevance from eligibility checks<br/>no LLM"] --> OUT
    end

    CAND -. "user opens a scheme" .-> EVQ
    OUT --> UI["UI: click a citation"]
    UI --> RES["resolve citation_id<br/>to doc, page, bbox, quote"]
    RES --> PDF["PDF viewer jumps to page<br/>and highlights passage"]
```

### 4.3 Hallucination guardrails (where each check happens)

```mermaid
flowchart LR
    subgraph Offline["Offline extraction"]
        X1["LLM proposes fact or rule"] --> X2{"cites a chunk<br/>it was shown?"}
        X2 -->|no| XD["DROPPED"]
        X2 -->|yes| X3{"word overlap<br/>at least 50%?"}
        X3 -->|no| XF["kept, FLAGGED"]
        X3 -->|yes| X4{"rule uses real field<br/>with correct type?"}
        X4 -->|no| XM["becomes manual rule<br/>NEEDS_VERIFICATION"]
        X4 -->|yes| XS["stored + audited"]
    end
    subgraph Online["Online summary"]
        Y1["LLM sentence"] --> Y2{"citation_ids in<br/>retrieved evidence?"}
        Y2 -->|no| YD["dropped"]
        Y2 -->|yes| YS["shown with clickable citation"]
    end
```

### 4.4 RAG design choices

| Choice | Reason |
|---|---|
| Section-aware chunks, not fixed windows | Eligibility clauses and benefit tables stay intact |
| Overlap only in `embed_text` | Better recall, while citations quote the exact source text |
| Metadata filter before ranking (state, `is_current`) | Never retrieve schemes the user cannot apply for, or outdated versions |
| Scheme-level aggregation (best chunk) | Ranking is per scheme, not per passage |
| Small CPU model (BGE-small, 384-d) | Runs on a laptop; the same tokenizer is used for chunk sizing |
| `citation_id == chunk_id`, deterministic Qdrant point IDs | Re-indexing is idempotent and citations are stable across versions |
| Profile never sent to the LLM | Privacy; personal relevance stays deterministic and auditable |
| Stored-facts fallback | The detail page still works when free-tier LLM quotas run out |

---

## 5. End-to-end in one picture

```mermaid
flowchart LR
    GOV["Gov PDFs"] -->|offline| KB[("Knowledge base<br/>Qdrant + PostgreSQL")]
    USER(["Citizen"]) --> ONB["W1 adaptive questions"]
    ONB --> PROF[("Versioned profile")]
    PROF --> LIB["W2 retrieve, check eligibility, score"]
    KB --> LIB
    LIB --> DET["W3 cited summary"]
    KB --> DET
    LIB --> CMP["W4 compare 2-5"]
    KB --> CMP
    DET --> CIT["Click citation - PDF page highlight"]
    CMP --> CIT
    PROF -->|edit| W5["W5 re-rank"]
    GOV -->|changes| W6["W6 refresh + invalidate"]
    W6 --> KB
```
