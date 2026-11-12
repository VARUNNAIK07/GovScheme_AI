# Database setup: Supabase (PostgreSQL) + Qdrant Cloud

No Docker. You create both services in the browser, put two URLs and one API key in `.env`,
then run one command to create every table.

## 1. Supabase (PostgreSQL)

1. Go to https://supabase.com → **New project**. Pick region **Mumbai (ap-south-1)** (closest to the data and users).
2. Set a **strong database password** and save it in your password manager. You need it in step 4.
3. When the project is ready, click **Connect** (top bar) → **Connection string** → choose **Session pooler**.
   *Why session pooler:* the "Direct connection" host only works over IPv6, which many home networks don't have.
   The session pooler works on normal IPv4 and supports everything our migrations need.
4. Copy the URI. It looks like
   `postgresql://postgres.<project-ref>:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres`
   * Replace `[YOUR-PASSWORD]` with your password. If the password has special characters, URL-encode them
     (`@` → `%40`, `#` → `%23`, `/` → `%2F`, `:` → `%3A`).
   * Add `?sslmode=require` at the end (forces an encrypted connection).
5. Put it in `.env` as `DATABASE_URL=...`.

**You do NOT need** Supabase's `anon` or `service_role` keys. The backend connects straight to PostgreSQL.
Don't put those keys anywhere. The migration turns on **row-level security on every table**, so
Supabase's automatic public REST API can read nothing, even with the anon key.

## 2. Qdrant Cloud (vector search)

1. Go to https://cloud.qdrant.io → create a **Free** cluster (1 GB is plenty for ~50 schemes). Pick the region closest to Mumbai.
2. Open the cluster → **API Keys** → create a key. It's shown **once**, so copy it now.
3. Copy the cluster **URL** from the cluster overview (looks like `https://<id>.<region>.<cloud>.cloud.qdrant.io`) and add `:6333`.
4. In `.env`: `QDRANT_URL=https://...:6333` and `QDRANT_API_KEY=...`.

## 3. Create the tables (once)

PowerShell, in the repo root:

```powershell
.\.venv\Scripts\Activate.ps1                    # turn on the project's Python environment
python -m ingestion.preflight                   # checks .env + connectivity (will say "no migration applied")
alembic -c backend/alembic.ini upgrade head     # creates all 18 tables, the view, reference data, RLS
python -m ingestion.preflight                   # now everything should say OK
```

## 4. Load what the pipeline already produced

```powershell
python -m ingestion.load_db       # schemes, sources, documents, chunks, events -> PostgreSQL
python -m ingestion.embed_index   # re-indexes chunks into Qdrant Cloud (local test index is separate)
```

## What lives where

| Store | Holds | Rebuildable? |
|---|---|---|
| PostgreSQL | users, profiles, workflow runs, schemes, rules, facts, sources, documents, chunks, events | **No**: source of truth, back it up |
| Qdrant | chunk vectors + Evidence payload | Yes, from `chunks` / `data/chunks` |
| `data/` folder | raw PDFs (never edited), Docling JSON, chunk files, logs | raw PDFs: re-download; rest: re-run the pipeline |
