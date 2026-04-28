# Catalog Health AI

> AI reliability layer on top of Collibra. 24/7 agents that detect metadata decay, broken lineage, and governance gaps — and surface them in a governance dashboard with Claude-generated executive summaries.

## Architecture

- **4 AI Agents**: MetadataCurator + LineageGuardian (parallel) → GovernanceGap → ExecutiveRisk
- **Health Score**: 100 − (5×High + 3×Medium + 1×Low), floor 0
- **AI Layer**: Claude claude-sonnet-4-20250514 with 24h response caching
- **Stack**: FastAPI · SQLAlchemy 2.0 async · Supabase PostgreSQL · Next.js 14 · Tailwind CSS · NetworkX

---

## Prerequisites

- Python 3.12 (not 3.13/3.14 — binary wheels for `asyncpg` and `pydantic-core` require 3.12)
- Node 20+
- A [Supabase](https://supabase.com) project (free tier works)
- An [Anthropic API key](https://console.anthropic.com/settings/keys)

---

## Backend Setup

### 1. Create a Python 3.12 virtual environment

```bash
cd ~/CatalogHealthAI
python3.12 -m venv .venv
source .venv/bin/activate
```

Re-activate in every new terminal session:
```bash
source ~/CatalogHealthAI/.venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Configure environment variables

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Fill in these required values:

| Variable | Where to get it |
|---|---|
| `DATABASE_URL` | Supabase → Settings → Database → Connection pooling (see note below) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| `NOTION_TOKEN` | [notion.so/my-integrations](https://www.notion.so/my-integrations) |

**Important — DATABASE_URL format:**

Use the Supabase **connection pooler** URL (not the direct DB host). The direct host returns IPv6 addresses which may not be reachable from all machines.

In Supabase → Settings → Database → Connection pooling, copy the Session mode host. Your URL should look like:

```
DATABASE_URL=postgresql+asyncpg://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@aws-1-us-east-1.pooler.supabase.com:5432/postgres
```

If your password contains special characters (e.g. `@`), URL-encode them:
- `@` → `%40`
- `#` → `%23`
- `%` → `%25`

Test connectivity before starting the server:
```bash
python -c "
import asyncio, asyncpg
async def test():
    conn = await asyncpg.connect(
        host='aws-1-us-east-1.pooler.supabase.com',
        port=5432,
        user='postgres.YOUR_PROJECT_REF',
        password='YOUR_PASSWORD',
        database='postgres'
    )
    print('Connected:', await conn.fetchval('SELECT NOW()'))
    await conn.close()
asyncio.run(test())
"
```

### 4. Apply the database schema

In your Supabase project → **SQL Editor**, paste the contents of `backend/db/schema.sql` and click Run. This creates all tables (assets, lineage, scan_runs, findings, ai_summaries).

### 5. Start the backend

Always run uvicorn from the `backend/` directory:

```bash
cd ~/CatalogHealthAI/backend
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.
Open `http://localhost:8000/docs` for the interactive Swagger UI.

---

## Running a scan (end-to-end test)

Use the Swagger UI at `http://localhost:8000/docs` or curl:

**Step 1 — Upload assets**
```bash
curl -X POST http://localhost:8000/upload-assets \
  -F "file=@backend/tests/fixtures/seed_assets.csv"
```
Copy the `scan_id` from the response.

**Step 2 — Upload lineage**
```bash
curl -X POST "http://localhost:8000/upload-lineage?scan_id=YOUR_SCAN_ID" \
  -F "file=@backend/tests/fixtures/seed_lineage.csv"
```

**Step 3 — Run the agent pipeline**
```bash
curl -X POST "http://localhost:8000/run-scan?scan_id=YOUR_SCAN_ID"
```

**Step 4 — View results**
```bash
curl http://localhost:8000/health-score
curl http://localhost:8000/issues
curl http://localhost:8000/summary     # calls Claude — requires ANTHROPIC_API_KEY
```

---

## Running tests

```bash
cd ~/CatalogHealthAI/backend
pytest tests/ -v
```

16 unit tests covering all 6 governance rules and the health score formula. No database required.

---

## Frontend Setup

```bash
cd ~/CatalogHealthAI/frontend
npm install
```

Create a `.env.local` file:
```bash
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```

Start the dev server:
```bash
npm run dev
```

Open `http://localhost:3000`. With the backend running in parallel, all four pages (Overview, Issues, Lineage, Recommendations) will load live data.

---

## Scripts

### Sync Notion task statuses

Requires `NOTION_TOKEN` in `backend/.env` and the integration connected to the Task Tracker database (Notion DB → ··· → Connections → add integration).

```bash
cd ~/CatalogHealthAI
python scripts/update_notion_status.py           # dry-run, prints plan
python scripts/update_notion_status.py --apply   # pushes to Notion
```

### Weekly email report

Requires `RESEND_API_KEY` and `REPORT_RECIPIENT_EMAIL` in `backend/.env`.

```bash
python scripts/send_weekly_report.py
```

---

## Project structure

```
CatalogHealthAI/
├── backend/
│   ├── .env.example          # copy to .env and fill in secrets
│   ├── requirements.txt
│   ├── app/
│   │   ├── config.py         # settings (pydantic-settings, reads backend/.env)
│   │   ├── database.py       # async SQLAlchemy engine + get_db dependency
│   │   ├── main.py           # FastAPI app + all 5 endpoints
│   │   ├── models/           # SQLAlchemy ORM models
│   │   └── services/
│   │       ├── claude_client.py   # Anthropic API wrapper
│   │       └── ingest_service.py  # CSV parser + DB upsert
│   ├── agents/__init__.py    # 4 agents + orchestrator
│   ├── rules/rules_engine.py # 6 governance rules
│   ├── db/schema.sql         # run this in Supabase SQL Editor
│   └── tests/
│       ├── test_rules.py
│       └── fixtures/
│           ├── seed_assets.csv    # 50-asset test dataset
│           └── seed_lineage.csv   # lineage pairs for the seed data
├── frontend/
│   ├── src/app/              # Next.js 14 app router pages
│   ├── src/components/       # HealthGauge, SeverityBadge, ScoreTrendChart, Sidebar
│   └── src/lib/api.ts        # typed API client
├── scripts/
│   ├── update_notion_status.py
│   └── send_weekly_report.py
├── .github/workflows/ci.yml  # pytest + tsc/build + weekly email cron
├── vercel.json               # frontend deploy config (root dir: frontend/)
└── .gitignore
```

---

## Deployment

### Backend → Railway

1. Push repo to GitHub
2. New Railway project → Deploy from GitHub repo
3. Set env vars (copy from `backend/.env`) in Railway dashboard
4. Railway auto-detects FastAPI and runs `uvicorn app.main:app`

### Frontend → Vercel

1. Import GitHub repo in Vercel
2. Vercel reads `vercel.json` automatically — root directory is set to `frontend/`
3. Add environment variable: `NEXT_PUBLIC_API_URL` = your Railway backend URL
4. Deploy

---

## Notion Project Hub
https://www.notion.so/34d8afb1a56f8167a074e9bccadc46d2
