# GovScheme AI: Phase 1 Proposal (Person A, Knowledge & Evidence)

*Prepared 2026-10-12. Nothing in this document has been built yet. It is for review and approval.*

Files in this folder:

| File | What it is |
|---|---|
| `PHASE1_PROPOSAL.md` | This document: taxonomy, scheme list summary, folder structure, contract review, database design, install plan, open questions |
| `schemes_proposed.csv` | The proposed list of 58 schemes, one per row, with ministry, sectors, tags, eligibility notes, official PDF URL, link-check result, status and issues |
| `link_check_2026-10-12.csv` | Raw log of the link check (robots.txt result, HTTP status, PDF header check, size) |

---

## 0. What I inspected

* `C:\projects\GovScheme_AI` was **empty apart from this proposal**: no `contracts/`, no schemas, no config, no PDFs, no git repo.
* The contracts were therefore reviewed from the **build plan PDF (section 4)**, not from code. If you resubmit `contracts/schemas.py`, I will diff it against this review before writing any code that depends on it.
* Machine: Windows 11, Python 3.11.9, git 2.55, **Docker not installed**, RTX 3050 (4 GB) not needed for now (CPU first, as you asked).

---

## 1. Sector taxonomy (proposal)

### 1.1 Final list (10 primary sectors)

| # | `sector_id` (stored in DB/API) | Display name | Covers |
|---|---|---|---|
| 1 | `agriculture_rural` | Agriculture, Farming & Rural Development | crops, irrigation, farm machinery, fisheries, animal husbandry, farm credit |
| 2 | `education` | Education & Scholarships | scholarships, fellowships, education loans, coaching |
| 3 | `employment_skills` | Employment, Skills & Livelihoods | skilling, apprenticeships, internships, wage-employment guarantee |
| 4 | `business_msme` | Business, Entrepreneurship & MSMEs | enterprise loans, subsidies, startup funding, street vendors |
| 5 | `health` | Healthcare & Medical Assistance | hospital cover, treatment grants, maternal health |
| 6 | `housing_utilities` | Housing, Sanitation & Basic Needs | houses, toilets, cooking gas, food security |
| 7 | `women_child` | Women, Children & Family Welfare | maternity benefit, child protection, women's safety |
| 8 | `social_welfare` | Social Welfare & Inclusion | non-contributory pensions, disability, senior citizens, transgender persons |
| 9 | `financial_inclusion` | Financial Inclusion, Insurance & Savings | bank accounts, insurance, contributory pensions, small savings |
| 10 | `energy_environment` | Energy & Environment | rooftop solar, clean energy for households |

### 1.2 What I changed from your draft, and why

1. **#10 "Infrastructure, Energy & Environment" became "Energy & Environment".** Infrastructure schemes (roads, smart cities, water mains) are not things a citizen applies for, so the category would stay empty. Even after renaming it is thin: only PM Surya Ghar is *primary* here, while PM-KUSUM and micro-irrigation use it as a *secondary* sector. **Alternative:** merge it into `housing_utilities`. I recommend keeping it, because state solar and EV schemes will fill it later.
2. **#6 "Utilities" became "Sanitation"** in the display name, because the real schemes are toilets, cooking gas and food. The `sector_id` stays the same.
3. **#9 adds "Savings"**, because Sukanya Samriddhi and the pension schemes need a home.

### 1.3 Assignment rules (these stop the categories overlapping)

These make every scheme's classification repeatable instead of a judgment call:

* **R1. The primary sector is *what the benefit is for*, not *who gets it*.** Who gets it is recorded in beneficiary tags. Example: Post-Matric Scholarship for SC → `education` plus tag `sc`, not `social_welfare`.
* **R2. Pensions:** pensions paid by the government for free to people who qualify (e.g. NSAP old-age pension) → `social_welfare`. Pensions you pay into (APY, PM-SYM, PM-KMY) → `financial_inclusion`.
* **R3. Loans and credit** go to the purpose: business → `business_msme`, farming → `agriculture_rural`, studies → `education`.
* **R4. Maternity or child cash** → `women_child`; hospital treatment cover → `health`.
* **R5.** At most **3 secondary sectors** per scheme. The primary sector is never repeated as a secondary.

### 1.4 Beneficiary tags (fixed list)

The match formula's **P** component compares scheme tags with tags *derived from the user's profile*. A tag that can never be derived from the profile unfairly lowers P, so each tag is marked:

| Derivable from current `ProfileAttributes` | Not derivable yet (display/filter only unless B adds profile fields) |
|---|---|
| `farmer`, `student`, `unemployed` (occupation) · `woman` (gender) · `sc`, `st`, `obc`, `ews` (social_category) · `senior` (age ≥ 60) · `youth` (age 18–35) · `child` (age < 18) · `widow` (marital_status) · `disabled` · `rural`, `urban` (area_type) · `bpl` | `girl_child`, `pregnant_woman`, `transgender`, `dnt`, `artisan`, `street_vendor`, `fisher`, `entrepreneur`, `unorganised_worker`, `sanitation_worker`, `homeowner`, `shg`, `fpo`, `lig`, `mig` |

### 1.5 Benefit-type tags (fixed list)

`cash_transfer`, `scholarship`, `stipend`, `loan`, `interest_subsidy`, `credit_guarantee`, `capital_subsidy`, `grant`, `insurance`, `health_cover`, `pension`, `savings`, `bank_account`, `housing`, `in_kind`, `training`, `employment`, `service`

### 1.6 Effect on the contracts and teammates

* `Scheme.sector` keeps its name and holds the **primary** `sector_id`.
* New **optional** fields are needed on `Scheme` (allowed under the append-only rule): `secondary_sectors: list[str] = []` and `benefit_types: list[str] = []`.
* **`ProfileAttributes.sectors_of_interest` must use the same `sector_id` values.** The build plan's example words (`agriculture, education, health, housing, business, women, pension, skill`) do not match: `pension` and `skill` are not sectors. This affects **B** (question options, the **B** score component) and **C** (labels), so it needs agreement before anyone codes it.
* The taxonomy is stored once in `contracts/constants.py` and the `sectors`/`tags` tables. Nothing hard-codes it anywhere else.

---

## 2. Scheme list (summary; details in `schemes_proposed.csv`)

### 2.1 How the list was built and checked

* Sources: official ministry and department sites, scheme portals, PIB and the National Scholarship Portal, found by web search restricted to `gov.in`/`nic.in`. myScheme and india.gov.in pages are JavaScript-rendered and link out to the ministries, so I followed those links to the ministry PDFs rather than scraping the portals.
* **Link check (no full downloads):** for each PDF I read the host's `robots.txt` once, then requested **only the first 2 KB** of the file. That confirmed the HTTP status, that the bytes start with `%PDF`, and the file size. I waited at least 2 s per host, sent a descriptive User-Agent with your contact email, and kept TLS certificate checking on.
* **The eligibility and benefit text in the CSV comes from search snippets** and is marked `[from search snippets; verify against PDF]`. It is there to help you judge relevance. The real facts will come only from the PDFs, with citations, in Phase 2.
* **Digital vs scanned is `not_yet_verified` for every PDF.** I can't tell without the full file. Phase 2 checks every page's text layer before deciding whether to OCR.

### 2.2 Result

| Status | Count | Meaning |
|---|---|---|
| `VERIFIED` | 22 | Hosted by the owning ministry or its portal; robots.txt allows it; real PDF |
| `VERIFIED_OFFICIAL_COPY` | 7 | Real PDF on another **official government** host (state department, National Horticulture Board, UGC, Invest India, Ministry of Power portal), because the owner's copy was blocked, missing or Hindi-only |
| `MANUAL` | 16 | An official PDF exists, but automated download was **blocked (403), unreachable (timeout/DNS), disallowed by robots.txt, or failed a TLS hostname check**. I will **not** work around these. You can download them in a normal browser and drop them into `data/inbox/` (Phase 2 registers them with their official URL) |
| `NEEDS_DECISION` | 6 | A PDF exists but is weak (2015 SOP, 2014 brochure, fact sheet, outdated version) or the scheme has closed to new applicants |
| `EXCLUDED` | 7 | No usable official English guideline PDF on a government domain, or the scheme has been repealed |

**Shortfall (reported honestly): only 29 schemes can be downloaded automatically and verified today.** That rises to **45** if you download the 16 `MANUAL` files in a browser, and to at most **51** if all `NEEDS_DECISION` rows are kept. I did not invent links to reach 50.

### 2.3 Findings you should know about

* **MGNREGA was repealed from 1 July 2026** and replaced by the **VB-G RAM G Act, 2025** (125 days of guaranteed work). I added VB-G RAM G and excluded MGNREGA. Its final Rules were still in draft consultation in May 2026.
* **The Ministry of Social Justice site (`socialjustice.gov.in`) was unreachable** from this machine (7 schemes, plus PM-DAKSH on `pmdaksh.dosje.gov.in`). This may be temporary or specific to the network. I will retry in Phase 2 before asking you to download anything.
* Many new ministry sites (`msde`, `mohua`, `dord`, `mohfw`, `labour`, `dof`, `wcd`) **return 403 to any non-browser client**. Pretending to be a browser would get around an access control, so the scraper will record these as `failed: 403` and list them for manual download.
* **Several documents are outdated or have later amendments** (PMFBY 2023 OG, AIF 2021 revision, NAPS-2, PM-KISAN English). Each one is noted in the `issues` column.
* All 52 candidate schemes are **central**. State schemes would multiply the list by 36 states, so I suggest adding a few state schemes only after the pipeline works (see question Q2).

### 2.4 Proposed first test corpus (3 PDFs, chosen to exercise different paths)

| Scheme | Why |
|---|---|
| `pmsby` (88 KB) | Small, clean, digital: the "happy path" |
| `pm-kmy` (1.1 MB) | Eligibility rules, contribution tables, exclusions: tests table parsing and rule extraction |
| `mission-shakti-osc` (2.9 MB) | Cover letter looks scanned (garbled text in the search index): tests OCR detection and quality checks |

---

## 3. Proposed folder structure (my part only, inside the agreed team tree)

`NEW` marks additions to the team's file-structure document. Everything else is already agreed.

```
govscheme-ai/
├── contracts/                     ALL   frozen models (needs Q3 decision)
├── data/                          A     (gitignored; data only, never code)
│   ├── index.csv                        one row per source URL: scheme_id, url, doc_id, fetch status
│   ├── inbox/                     NEW   PDFs you download by hand for MANUAL rows
│   ├── raw/{doc_id}.pdf                 original files, never edited
│   ├── parsed/{doc_id}.json             Docling output
│   ├── chunks/{doc_id}.jsonl            chunks before embedding
│   ├── extractions/               NEW   raw LLM outputs per run (audit trail)
│   └── logs/                      NEW   ingestion logs
├── ingestion/                     A     offline pipeline; plain scripts, run in order
│   ├── __init__.py
│   ├── config.py                        ingestion-only settings (paths, delay, size limit)
│   ├── allowlist.yaml             NEW   exact approved hosts (not "*.gov.in")
│   ├── seeds/schemes.csv          NEW   the APPROVED scheme list (committed, because data/ is gitignored)
│   ├── common.py                  NEW   shared helpers: sha256 → doc_id, atomic writes, JSONL, stage logging
│   ├── fetcher.py                 NEW   the ONE polite HTTP client (robots, per-host delay, retries, TLS, %PDF check),
│   │                                    used by both scrape.py and refresh.py so the logic isn't written twice
│   ├── preflight.py               NEW   checks .env, PostgreSQL, Qdrant, LLM reachability before any run
│   ├── audit_corpus.py                  hash files in raw/ + inbox/, find duplicates, update index.csv
│   ├── scrape.py                        download approved, missing PDFs only
│   ├── parse.py                         Docling + text-layer check + OCR + quality check
│   ├── chunk.py                         section-aware chunks with page + bbox
│   ├── embed_index.py                   BGE → Qdrant 'scheme_chunks'
│   ├── extract_facts.py                 LLM (JSON) → validated facts/rules → PostgreSQL
│   ├── refresh.py                       W6: re-check sources, re-version changed documents
│   ├── run_all.py                       preflight → audit → scrape → parse → chunk → embed → extract
│   └── requirements.txt           NEW   ingestion-only deps (Docling, OCR)
├── backend/app/knowledge/         A     reusable functions the agents call at runtime
│   ├── embedder.py                      loads BGE once (cached), embed_documents()/embed_query()
│   ├── qdrant_store.py                  the ONE Qdrant client factory + collection setup + search
│   ├── llm.py                           the ONE LLM client: Groq + Gemini, priority, timeouts, retries, fallback
│   ├── prompts.py                       versioned prompt templates
│   ├── retrieval.py                     retrieve_candidates, get_evidence
│   ├── citations.py                     validate, resolve
│   ├── comparison.py                    compare (deterministic, from PostgreSQL facts)
│   └── summary.py                       summarize_scheme, explain_comparison
└── backend/tests/                 A's files
    ├── test_ingestion.py                duplicates, doc_id/chunk_id format, schema validation
    ├── test_retrieval.py                known query → right scheme in top 5
    ├── test_citations.py                uncited sentence dropped; resolve gives a real page
    ├── test_import_graph.py       NEW   fails if any import breaks the rules below
    └── golden.json
```

### Import rules (enforced by `test_import_graph.py`, which scans imports without running them)

```
ingestion/*            →  backend.app.knowledge.{embedder, qdrant_store, llm}
                       →  backend.app.db.{session, models}      (B's engine; no second DB client)
                       →  backend.app.core.config               (B's settings; no second .env reader)
                       →  contracts
backend.app.knowledge  →  backend.app.db, backend.app.core.config, contracts
backend.app.knowledge  ✗  ingestion, agents, controller, api    (never)
```

**Single instances:** one embedding model in memory, one Qdrant client, one LLM client, one database engine. If `ingestion/config.py` needs a database or Qdrant URL, it reads it from B's settings object instead of parsing `.env` again.

---

## 4. Contract review (against build plan section 4)

| # | Finding | Proposed resolution | Needs |
|---|---|---|---|
| C1 | `Evidence.scheme_id` is **required**, but `DocumentMeta.scheme_id` is **optional**, so a document without a scheme cannot produce valid chunks | Every document comes from a `source` row that **must** have a `scheme_id` (see DB design). Unmapped files stay at `downloaded` and are never chunked | none |
| C2 | Some PDFs cover several schemes (Mission Shakti covers PMMVY + One Stop Centres; NSAP covers 4 pensions) | MVP: one document maps to one `scheme_id`. Umbrella schemes are modelled as one scheme (as in the CSV). Later: optional `scheme_ids` | none now |
| C3 | `bbox` coordinate origin is not stated | `[x0, y0, x1, y1]` in PDF points, **origin bottom-left** (native PDF). The viewer flips the y-axis (`canvas_y = page_height − y`) | CHANGELOG line, tell **C** |
| C4 | `chunk_id = {doc_id}-p{page}-c{n}` is ambiguous for chunks that cross pages | `page` = page where the chunk **starts**; `n` = 0-based counter per (doc, page) in reading order; `bbox` = union of the chunk's boxes **on that page** | CHANGELOG line |
| C5 | Qdrant point IDs must be an integer or UUID, not `chunk_id` | Point ID = `uuid5(NAMESPACE_URL, chunk_id)` (deterministic, so re-runs overwrite instead of duplicating); `chunk_id` stays in the payload | none |
| C6 | `Scheme.sector` / `sectors_of_interest` vocabulary does not match the taxonomy | See §1.6 | **B, C** |
| C7 | `Scheme.benefits / documents_required / application_steps` are plain strings without `citation_id`, but the accuracy rule says "no chunk, no fact" | The DB keeps a citation **per item** (`scheme_facts`). The API shape stays as is, and cited text reaches users through `SchemeSummary` | none |
| C8 | `DocumentMeta` cannot say whether a PDF was scanned, which language it is in, or why it failed | Optional fields: `language: str = 'en'`, `text_layer: Literal['digital','scanned','mixed'] \| None = None`, `fetch_method: Literal['auto','manual'] = 'auto'`, `error: str \| None = None` | CHANGELOG |
| C9 | `ingestion_status` has no `chunked`/`embedded` steps | Keep the contract as is; detailed per-stage history goes in an `ingestion_events` table | none |
| C10 | `EligibilityRule.field` must be a `ProfileAttributes` field, but common conditions have no field: **"not an income-tax payer"** (PM-KISAN, APY, PM-SYM, PM-KMY), "has a bank account", "pregnant", "owns a house" | Such rules become `operator='manual'` with `field='_unmapped'` → `NEEDS_VERIFICATION`. **Suggest B adds** optional `is_income_tax_payer`, `has_bank_account`, `owns_pucca_house` to the profile | **B** |
| C11 | `max_benefit_inr` doesn't say whether it is one-time, per year or per month, so comparisons can mislead | Optional `max_benefit_period: Literal['one_time','per_year','per_month'] \| None = None` | CHANGELOG |
| C12 | When a document is re-versioned, old chunks must not be retrieved, but old citations must still open | Old document rows stay in PostgreSQL with `is_current=false`; their Qdrant points get payload `is_current=false` and retrieval filters `is_current=true`. Raw files are never deleted, so old citations still resolve | none |
| C13 | `ProfileAttributes.state` and `Scheme.states` have no agreed spelling ("Uttar Pradesh" vs "UP" vs "IN-UP") | One canonical list in `contracts/constants.py` (suggest ISO 3166-2:IN codes, e.g. `IN-UP`, plus `ALL`) | **B, C** |

---

## 5. PostgreSQL design proposal

**In plain words:** PostgreSQL is the **source of truth** for schemes, rules, documents and chunks. Qdrant is a **search index built from it**, which can be deleted and rebuilt at any time. Every fact and rule must point at a real chunk, and the database enforces that with foreign keys. It does not rely on code being careful.

**Ownership:** the tables below hold A's data (A writes them). B owns Alembic migrations and B's own tables (`users`, `profiles`, `workflow_runs`, `comparison_sessions`), which are not repeated here. See Q4 for who writes this migration.

Enums are `TEXT + CHECK` constraints rather than PostgreSQL `ENUM` types, because adding a value later is a one-line migration.

```sql
-- ── Reference data ──────────────────────────────────────────────────────────
CREATE TABLE sectors (
  sector_id    TEXT PRIMARY KEY,                       -- 'education'
  name         TEXT NOT NULL UNIQUE,
  sort_order   SMALLINT NOT NULL
);

CREATE TABLE tags (
  tag_id       TEXT PRIMARY KEY,                       -- 'sc', 'scholarship'
  kind         TEXT NOT NULL CHECK (kind IN ('beneficiary','benefit_type')),
  label        TEXT NOT NULL,
  profile_rule TEXT NULL                               -- how B derives it from a profile; NULL = not derivable
);

-- ── Schemes ─────────────────────────────────────────────────────────────────
CREATE TABLE schemes (
  scheme_id        TEXT PRIMARY KEY CHECK (scheme_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  name             TEXT NOT NULL,
  department       TEXT NOT NULL,
  level            TEXT NOT NULL CHECK (level IN ('central','state')),
  primary_sector   TEXT NOT NULL REFERENCES sectors(sector_id),
  summary          TEXT NULL,
  max_benefit_inr  BIGINT NULL CHECK (max_benefit_inr >= 0),
  max_benefit_period TEXT NULL CHECK (max_benefit_period IN ('one_time','per_year','per_month')),
  official_url     TEXT NULL,
  application_url  TEXT NULL,
  facts_status     TEXT NOT NULL DEFAULT 'incomplete'
                   CHECK (facts_status IN ('verified','extracted','incomplete')),
  is_active        BOOLEAN NOT NULL DEFAULT TRUE,
  last_checked     DATE NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_schemes_primary_sector ON schemes(primary_sector);

CREATE TABLE scheme_secondary_sectors (
  scheme_id  TEXT NOT NULL REFERENCES schemes(scheme_id) ON DELETE CASCADE,
  sector_id  TEXT NOT NULL REFERENCES sectors(sector_id),
  PRIMARY KEY (scheme_id, sector_id)
);  -- app check: sector_id <> schemes.primary_sector, max 3 rows per scheme

CREATE TABLE scheme_tags (
  scheme_id  TEXT NOT NULL REFERENCES schemes(scheme_id) ON DELETE CASCADE,
  tag_id     TEXT NOT NULL REFERENCES tags(tag_id),
  PRIMARY KEY (scheme_id, tag_id)
);
CREATE INDEX ix_scheme_tags_tag ON scheme_tags(tag_id);

CREATE TABLE scheme_states (
  scheme_id   TEXT NOT NULL REFERENCES schemes(scheme_id) ON DELETE CASCADE,
  state_code  TEXT NOT NULL,                          -- 'ALL' or canonical code (C13)
  PRIMARY KEY (scheme_id, state_code)
);
CREATE INDEX ix_scheme_states_state ON scheme_states(state_code);

-- ── Provenance: where each file came from ──────────────────────────────────
CREATE TABLE sources (
  source_id     BIGSERIAL PRIMARY KEY,
  scheme_id     TEXT NOT NULL REFERENCES schemes(scheme_id),   -- fixes C1: no source without a scheme
  url           TEXT NOT NULL UNIQUE,
  host          TEXT NOT NULL,
  approved      BOOLEAN NOT NULL DEFAULT FALSE,               -- only approved sources are fetched
  robots        TEXT NULL CHECK (robots IN ('allowed','disallowed','no-robots','unknown')),
  last_status   TEXT NULL,                                    -- '206', '403', 'timeout', ...
  last_checked  TIMESTAMPTZ NULL
);
CREATE INDEX ix_sources_scheme ON sources(scheme_id);

CREATE TABLE documents (
  doc_id           CHAR(16) PRIMARY KEY CHECK (doc_id ~ '^[0-9a-f]{16}$'),
  sha256           CHAR(64) NOT NULL UNIQUE,                  -- same bytes = same document = skip
  source_id        BIGINT NOT NULL REFERENCES sources(source_id),
  version          INTEGER NOT NULL CHECK (version >= 1),
  is_current       BOOLEAN NOT NULL DEFAULT TRUE,
  title            TEXT NOT NULL,
  local_path       TEXT NOT NULL,
  pages            INTEGER NULL CHECK (pages > 0),
  language         TEXT NOT NULL DEFAULT 'en',
  text_layer       TEXT NULL CHECK (text_layer IN ('digital','scanned','mixed')),
  fetch_method     TEXT NOT NULL DEFAULT 'auto' CHECK (fetch_method IN ('auto','manual')),
  ingestion_status TEXT NOT NULL CHECK (ingestion_status IN ('downloaded','parsed','indexed','failed')),
  error            TEXT NULL,
  fetched_at       TIMESTAMPTZ NOT NULL,
  last_checked     TIMESTAMPTZ NOT NULL,
  UNIQUE (source_id, version)
);
CREATE UNIQUE INDEX ux_documents_one_current ON documents(source_id) WHERE is_current;
-- Contract view: DocumentMeta.scheme_id / source_url come from the joined source row
CREATE VIEW document_meta_v AS
  SELECT d.*, s.scheme_id, s.url AS source_url FROM documents d JOIN sources s USING (source_id);

CREATE TABLE chunks (
  chunk_id     TEXT PRIMARY KEY CHECK (chunk_id ~ '^[0-9a-f]{16}-p[0-9]+-c[0-9]+$'),
  doc_id       CHAR(16) NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  page         INTEGER NOT NULL CHECK (page >= 1),
  section      TEXT NULL,
  text         TEXT NOT NULL,
  bbox         DOUBLE PRECISION[] NULL CHECK (bbox IS NULL OR cardinality(bbox) = 4),
  token_count  INTEGER NOT NULL CHECK (token_count > 0),
  embedded_at  TIMESTAMPTZ NULL                              -- NULL = not yet in Qdrant
);
CREATE INDEX ix_chunks_doc_page ON chunks(doc_id, page);

-- ── Extracted knowledge (every row must cite a real chunk) ─────────────────
CREATE TABLE extraction_runs (
  run_id           BIGSERIAL PRIMARY KEY,
  scheme_id        TEXT NOT NULL REFERENCES schemes(scheme_id),
  provider         TEXT NOT NULL,                            -- 'groq' | 'gemini'
  model            TEXT NOT NULL,
  prompt_version   TEXT NOT NULL,
  input_chunk_ids  TEXT[] NOT NULL,
  raw_output_path  TEXT NULL,                                -- data/extractions/...
  status           TEXT NOT NULL CHECK (status IN ('ok','partial','invalid_json','failed')),
  error            TEXT NULL,                                -- never contains secrets
  started_at       TIMESTAMPTZ NOT NULL,
  finished_at      TIMESTAMPTZ NULL
);
CREATE INDEX ix_extraction_runs_scheme ON extraction_runs(scheme_id, started_at DESC);

CREATE TABLE scheme_facts (
  fact_id        BIGSERIAL PRIMARY KEY,
  scheme_id      TEXT NOT NULL REFERENCES schemes(scheme_id) ON DELETE CASCADE,
  kind           TEXT NOT NULL CHECK (kind IN ('summary','benefit','document_required','application_step')),
  position       SMALLINT NOT NULL CHECK (position >= 0),
  text           TEXT NOT NULL,
  citation_id    TEXT NOT NULL REFERENCES chunks(chunk_id),  -- no chunk, no fact
  review_status  TEXT NOT NULL DEFAULT 'unreviewed'
                 CHECK (review_status IN ('unreviewed','verified','flagged','rejected')),
  run_id         BIGINT NULL REFERENCES extraction_runs(run_id),
  UNIQUE (scheme_id, kind, position)
);

CREATE TABLE eligibility_rules (
  rule_id        TEXT PRIMARY KEY,                           -- '{scheme_id}-r{n}'
  scheme_id      TEXT NOT NULL REFERENCES schemes(scheme_id) ON DELETE CASCADE,
  field          TEXT NOT NULL,                              -- ProfileAttributes field or '_unmapped'
  operator       TEXT NOT NULL CHECK (operator IN
                   ('eq','in','not_in','lte','gte','between','is_true','is_false','manual')),
  value          JSONB NULL,
  kind           TEXT NOT NULL CHECK (kind IN ('required','exclusion')),
  source_text    TEXT NOT NULL,                              -- original wording from the PDF
  citation_id    TEXT NOT NULL REFERENCES chunks(chunk_id),  -- stricter than contract (which allows NULL)
  confidence     REAL NULL CHECK (confidence BETWEEN 0 AND 1),
  review_status  TEXT NOT NULL DEFAULT 'unreviewed'
                 CHECK (review_status IN ('unreviewed','verified','flagged','rejected')),
  run_id         BIGINT NULL REFERENCES extraction_runs(run_id)
);
CREATE INDEX ix_rules_scheme ON eligibility_rules(scheme_id);

-- ── Processing history (checkpoints + audit) ───────────────────────────────
CREATE TABLE ingestion_events (
  event_id    BIGSERIAL PRIMARY KEY,
  source_id   BIGINT NULL REFERENCES sources(source_id),
  doc_id      CHAR(16) NULL REFERENCES documents(doc_id),
  stage       TEXT NOT NULL CHECK (stage IN
                ('audit','download','parse','ocr','chunk','embed','extract','refresh')),
  status      TEXT NOT NULL CHECK (status IN ('started','ok','skipped','failed')),
  message     TEXT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_events_doc ON ingestion_events(doc_id, created_at DESC);
```

**How this maps to the frozen contracts:**

* `Scheme` = `schemes` + secondary sectors + tags + states + facts (assembled into lists) + `doc_ids` of current documents
* `EligibilityRule` = `eligibility_rules`, one row each
* `DocumentMeta` = `document_meta_v`
* `Evidence` = `chunks` + its document (`source_url`, `version`)

**Qdrant collection `scheme_chunks`:** 384-dimensional vectors, cosine distance. The payload is `Evidence` minus `score`, plus `is_current`. Payload indexes on `scheme_id`, `doc_id`, `section` and `is_current`.

---

## 6. Dependency and installation plan

### 6.1 Python (CPU only for now)

| Step | Command (PowerShell, repo root) | What it does |
|---|---|---|
| 1 | `py -3.11 -m venv .venv` | Creates a private Python environment, so project packages don't mix with system ones |
| 2 | `.\.venv\Scripts\Activate.ps1` | Turns that environment on for this terminal |
| 3 | `pip install -r ingestion/requirements.txt` | Installs ingestion + knowledge dependencies (below) |
| 4 | `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"` | Downloads the embedding model once (~130 MB) |

Planned packages: `docling` (PDF parsing; on Windows it installs the **CPU** build of PyTorch from PyPI), Docling's OCR engine (EasyOCR by default; I will time it on the scanned test PDF and switch to RapidOCR if it is too slow), `sentence-transformers`, `qdrant-client`, `sqlalchemy>=2`, `psycopg[binary]`, `pydantic>=2`, `pydantic-settings`, `pyyaml`, `truststore` (uses Windows' certificate store, which fixes the incomplete certificate chains many gov.in servers send **without turning verification off**), `groq`, `google-genai`, `pytest`. Expect about 3 GB disk including models. Exact versions get pinned after a clean install test.

**Coordination:** `backend/app/knowledge/` runs inside B's backend, so its packages (`sentence-transformers`, `qdrant-client`, `groq`, `google-genai`, `truststore`) must also go into B's `backend/pyproject.toml`. I will send B the list instead of editing their file.

### 6.2 Databases (you create them; Docker is not installed)

| Option | What you install | Pros | Cons |
|---|---|---|---|
| **A. Docker Desktop** (recommended) | Docker Desktop (needs WSL2 + virtualisation on) → `docker compose up -d postgres qdrant` | Identical to teammates' setup and C's `docker-compose.yml` | ~4 GB, one reboot |
| B. Native Windows | PostgreSQL 16 installer + Qdrant `qdrant.exe` (Windows zip from Qdrant's GitHub releases) | No Docker | Setup differs from teammates' |
| C. Cloud free tiers | e.g. Neon/Supabase (Postgres) + Qdrant Cloud | Nothing to install | Needs accounts; network dependency |

`.env` keys my part needs (values are yours; **never paste them in chat**):

```
DATABASE_URL=postgresql+psycopg://govscheme:<password>@localhost:5432/govscheme
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=                      # only for Qdrant Cloud
QDRANT_COLLECTION=scheme_chunks
EMBED_MODEL=BAAI/bge-small-en-v1.5
LLM_PROVIDER_PRIORITY=groq,gemini    # first = primary, rest = fallback
GROQ_API_KEY=
GROQ_MODEL=
GEMINI_API_KEY=
GEMINI_MODEL=
LLM_TIMEOUT_S=60
LLM_MAX_RETRIES=3
SCRAPER_CONTACT_EMAIL=sravyaullamgunta06@gmail.com
SCRAPER_MIN_DELAY_S=2
SCRAPER_MAX_PDF_MB=50
DOCS_DIR=data
```

The build plan's `.env.example` has a single `LLM_PROVIDER / LLM_MODEL / LLM_API_KEY`. Supporting Groq **and** Gemini with priority needs the keys above. **C** owns `.env.example` (see Q6).

### 6.3 LLM client behaviour (`knowledge/llm.py`, used by extraction and summaries)

* One interface: `complete_json(prompt, schema) -> dict`, the same for Groq and Gemini.
* Timeout on every call. **Bounded** retries with exponential backoff, **only** for transient errors (timeouts, 429 rate limit, 5xx).
* **Falls back to the next provider only** on quota exhaustion, repeated transient failure, or auth/config errors. It does **not** switch providers just because an answer is bad.
* An invalid-JSON answer is retried once with the validation error included; then the run is recorded as `invalid_json` and nothing is saved.
* Logs record provider, model, status and latency, **never keys or full prompts with secrets**.

### 6.4 Phase 2 order (after approval)

`preflight` → `audit_corpus` → `scrape` (3 test PDFs) → `parse` (+ OCR check) → `chunk` → `embed_index` → `extract_facts` → knowledge functions → tests → **review the 3-PDF results with you** → full approved list. Each script can be re-run safely: it skips work whose output already exists and is valid, and it records each step in `ingestion_events` / `data/logs`.

---

## 7. Decisions needed from you

| # | Question | My recommendation |
|---|---|---|
| Q1 | Approve the taxonomy (§1), including renaming #10 to `energy_environment` and rules R1–R5? | Approve |
| Q2 | Approve the scheme list? Will you download the 16 `MANUAL` PDFs in a browser (I'll give you a checklist)? Keep or drop the 6 `NEEDS_DECISION` rows? Add a few state schemes to reach 50? | Approve; do the manual downloads after the pipeline works on the 3 test PDFs; drop `sisfs`, `pmjdy`, `apy`; decide on states later |
| Q3 | Contracts: will you resubmit the team's actual `contracts/` files, or should I write them from the build plan plus the optional fields proposed in §1.6 and §4 for the team to review? | Resubmit if they exist; otherwise I write them and you share them |
| Q4 | Migrations: does B write the tables in §5 from this spec, or do I write a separate Alembic migration for these tables for B to review? | I write it, B reviews (unblocks me) |
| Q5 | Databases: Docker Desktop, native install, or cloud (§6.2)? | Docker Desktop |
| Q6 | You asked me to provide `.env.example` and requirements, but the team plan gives `.env.example`/README to C and `pyproject.toml` to B. May I add my keys to `.env.example` and keep my own `ingestion/requirements.txt`? | Yes, and tell C and B |
| Q7 | Pass to B: profile fields for C10 (`is_income_tax_payer`, etc.) and the state-code convention (C13) | Raise at the next checkpoint |
