# GovScheme AI Architecture

## 3-Layer System Design

1. **Knowledge Layer (Offline scripts, Member A)**:
   - Scrape official government schemes (`*.gov.in`, `*.nic.in`, `myscheme.gov.in`).
   - Parse PDFs with Docling preserving bounding boxes (`bbox`), sections, and pages.
   - Section-aware chunking into ~300-500 token chunks.
   - Vector indexing in Qdrant (`scheme_chunks`) using `BAAI/bge-small-en-v1.5` embeddings.
   - LLM-assisted factual extraction into PostgreSQL (`schemes`, `eligibility_rules`).

2. **Agent Layer (FastAPI backend, Member B)**:
   - Orchestrated via **Workflow Controller** using the blackboard pattern (`WorkflowState`).
   - Deterministic agents: Profiling Agent, Eligibility Agent, Scoring Agent.
   - Evidence agents (Knowledge): Retrieval Agent, Comparison Agent, Summary Agent, Citation Service.
   - Strict write-ownership: agents never import or invoke each other; each writes only to dedicated state fields.

3. **Experience Layer (React, Member C)**:
   - React + TypeScript + Vite + Tailwind CSS.
   - Mocked initially with MSW via `contracts/fixtures/` with seamless switch to live backend via `VITE_API_BASE`.
   - Guided onboarding, verified Library recommendations, deep scheme analysis with evidence chips, PDF document viewer with highlight bounding box rendering, and multi-scheme comparative matrix.
