# ProCare OS — Backend (FastAPI)

**Phase 1 — mirror & read (shadow mode).** Runs out of the box with **no
external database**: on first start it seeds a local SQLite *shadow* database
(`data/procare_demo.sqlite`, git-ignored) with realistic synthetic data, so the
dashboard, Arabic AI assistant, expiry/low-stock alerts, drug-interaction lookup
and reconciliation all work immediately. When `config/connections.json` carries
real `procare_database` credentials (and `pyodbc` is installed), the same code
reads ProCare's SQL Server system of record instead. See
[`../../docs/06-roadmap.md`](../../docs/06-roadmap.md).

## Run

```bash
# from this folder
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt      # macOS/Linux
# .venv\Scripts\python -m pip install -r requirements.txt  # Windows
.venv/bin/python run.py
```

API → http://127.0.0.1:8000  ·  interactive docs → http://127.0.0.1:8000/docs

The first request seeds the demo DB (logged at startup). To regenerate it:
`python -m app.seed` (or `POST /api/etl/mirror`).

## Architecture

The core logic is **standard-library-first** (built-in `sqlite3`), so it runs
and is fully unit-tested with no SQL Server. FastAPI, SQLAlchemy, `anthropic`
and APScheduler are optional layers that degrade gracefully.

```
app/
  config.py     reads config/connections.json (secrets stay server-side)
  db.py         data facade: SQLite demo  OR  SQL Server (pyodbc) — one query() API
  sql/          schema_sqlite.sql (clean schema) + views_sqlite.sql (AI whitelist)
  seed.py       deterministic synthetic data (2 branches, ~90 days of sales)
  queries.py    dashboard KPIs (branch + date aware)
  alerts.py     expiry (90/30/7), low-stock reorder drafts, debtors
  ai.py         PharmacyAI — constrained Arabic NL -> read-only SQL (+ validator)
  drugs.py      advisory drug interactions (Titan/Drug-Eye stand-in)
  etl.py        eStock read-only mirror + data-quality rules + reconciliation
  scheduler.py  APScheduler automation jobs (compute + log; nothing is sent yet)
  api/routes.py the HTTP surface
```

## Endpoints (Phase 1)

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/health` | status, data backend, configured sources, AI engine |
| GET  | `/api/branches` | the two branches (Main / Elsanta) |
| GET  | `/api/dashboard/summary?branch=` | headline KPIs |
| GET  | `/api/dashboard/daily-sales?branch=&days=` | sales time series |
| GET  | `/api/dashboard/top-products?branch=&days=&limit=` | best sellers |
| GET  | `/api/dashboard/hourly` · `/cashiers` · `/profit` | more reports |
| GET  | `/api/alerts/expiry?branch=` | 90/30/7-day horizons + auto-lock candidates |
| GET  | `/api/alerts/low-stock?branch=` | reorder **drafts** (human approves) |
| GET  | `/api/alerts/debtors` | customers over their credit limit |
| GET  | `/api/inventory/lookup?q=&branch=` | FEFO batch lookup |
| POST | `/api/ai/chat` | Arabic question -> answer + the SQL used (read-only) |
| GET  | `/api/ai/status` | engine (llm / rules), view whitelist, row cap |
| POST | `/api/drugs/check` | advisory interaction check for a basket |
| GET  | `/api/drugs/product/{id}` | interactions for one product (advisory) |
| GET  | `/api/etl/status` · POST `/api/etl/reconcile` · POST `/api/etl/mirror` | ETL |
| GET  | `/api/automation/jobs` · POST `/api/automation/run/{job}` | scheduler |

Secrets are **never** returned — `/api/health` only reports whether each source
has real (non-placeholder) credentials.

## Tests

```bash
python -m pytest      # 41 tests: data-quality rules, KPIs, AI SQL guard, ETL, alerts, API
```

## The AI assistant (guardrail)

`POST /api/ai/chat` turns an Arabic question into a **single validated SELECT**
over a fixed whitelist of `vw_*` views. The validator rejects anything that is
not a safe read (no `INSERT/UPDATE/DELETE/DDL/EXEC`, no `;`-stacking, no object
off the whitelist) and caps rows. With `ANTHROPIC_API_KEY` set it uses Claude
(model from config, default `claude-opus-4-8`); without a key it falls back to a
fully offline Arabic rule router — so the assistant always works and is
**read-only by construction**.
