# ProCare OS — Backend (FastAPI)

ProCare's own, independent system of record. Runs **standalone on its own
database** — SQLite in dev (zero setup), SQL Server in production — and serves
the dashboard, inventory, customers/vendors, POS write-path, automation alerts,
and the Arabic AI assistant.

eStock and Titan/Drug-Eye are read-only **sources**, reached only by the
[`app/services/etl.py`](app/services/etl.py) mirror adapter — never written to.
When no live eStock login is configured, the system seeds realistic demo data
([`app/db/seed.py`](app/db/seed.py)) so the whole stack is runnable offline.

## Run

```bash
# from this folder
python -m pip install -r requirements.txt
python run.py
```

First start auto-creates the schema and seeds demo data into `data/procare.db`
(git-ignored). API → http://127.0.0.1:8000 · interactive docs → `/docs`.

```bash
python -m app.db.seed   # force a clean reseed
python -m pytest        # run the test suite (POS guardrails + API)
```

## Architecture

```
app/
├── main.py            # FastAPI app; seeds the DB on startup
├── config.py          # reads config/connections.json (DB URL, AI, branches)
├── db/
│   ├── base.py        # engine/session (SQLite dev ↔ SQL Server prod)
│   ├── models.py      # ORM = sql/procare-schema.sql (FKs, checks, branch_id)
│   └── seed.py        # realistic demo data (stands in for the eStock ETL)
├── services/
│   ├── dashboard.py   # KPIs / charts (sql/dashboard-queries.sql, cleaned)
│   ├── inventory.py   # catalogue + FEFO batch lookup
│   ├── parties.py     # customers (credit picture) + vendors
│   ├── pos.py         # sp_create_sale / sp_deduct_stock(FEFO) / sp_check_credit
│   │                  #   / sp_transfer_stock — atomic, guardrailed
│   ├── alerts.py      # expiry risk, low-stock, smart reorder, forecast
│   ├── ai.py          # PharmacyAI.chat — constrained, read-only, Arabic-first
│   └── etl.py         # read-only eStock → ProCare mirror (Phase 1 adapter)
└── api/               # thin routers over the services
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | status, DB mode, AI engine, configured sources |
| GET | `/api/branches` | branches (Main / Elsanta) |
| GET | `/api/etl/status` | live vs offline mirror + the table-mapping plan |
| GET | `/api/dashboard/summary` · `/daily-sales` · `/top-products` · `/hourly` · `/cashiers` | KPIs + charts |
| GET | `/api/inventory/products` · `/products/{id}/batches` | catalogue + FEFO batches |
| GET | `/api/customers` · `/api/vendors` | parties + credit picture |
| GET | `/api/alerts/expiry` · `/low-stock` · `/reorder` · `/forecast/{id}` | automation |
| POST | `/api/sales` · `/api/sales/transfer` | POS write-path (FEFO, credit, atomic) |
| GET | `/api/sales/recent` | recent invoices |
| POST | `/api/ai/chat` | Arabic assistant (read-only) |

**Guardrails enforced in code** (see [`app/services/pos.py`](app/services/pos.py)):
FEFO deduction, credit-limit block (override needs `can_sale_credit`),
expired-stock lock, never-negative stock, all-or-nothing transactions. Secrets
are never returned by the API — `/api/health` only reports *whether* each source
is configured.
