# src/ — Application source

ProCare OS application code. The design is locked in [`../docs/`](../docs); this
is the working implementation of it. The system runs **standalone on ProCare's
own database** (SQLite in dev, SQL Server in prod) with realistic seeded data, so
the full stack is runnable with zero infrastructure. eStock / Titan are read-only
sources reached only by the mirror adapter — never written to.

## Quick start

```bash
# 1) Backend  (http://127.0.0.1:8000, docs at /docs)
cd backend && python -m pip install -r requirements.txt && python run.py

# 2) Frontend (http://localhost:3000)  — in another terminal
cd frontend && npm install && npm run dev
```

The backend auto-creates and seeds its database on first run. Open
http://localhost:3000 for the Arabic-first dashboard.

## Layout

```
src/
├── backend/                 # Python + FastAPI  (see backend/README.md)
│   ├── app/
│   │   ├── main.py          # entrypoint; seeds the DB on startup
│   │   ├── config.py        # reads ../../config/connections.json
│   │   ├── db/              # engine + ORM (= sql/procare-schema.sql) + seed
│   │   ├── services/        # dashboard, inventory, parties, pos, alerts, ai, etl, clinical
│   │   ├── api/             # REST routers
│   │   └── tests/           # POS guardrail + API tests (pytest)
│   └── requirements.txt
│
└── frontend/                # React / Next.js (RTL, i18n ar/en, light/dark)
    └── app/
        ├── page.js          # dashboard (KPIs, charts)
        ├── inventory/       # catalogue + stock
        ├── pos/             # point of sale (cash/credit, FEFO)
        ├── customers/       # customers + credit picture
        ├── alerts/          # expiry risk + reorder drafts
        ├── clinical/        # drug card: interactions, in-stock alternatives, dosing
        ├── assistant/       # Arabic AI assistant chat
        ├── components/      # Shell (nav + branch switcher), charts
        ├── api.js           # backend client
        ├── i18n.js          # ar (default) / en strings
        └── providers.js     # lang + theme + branch context (persisted)
```

## What's implemented (maps to the roadmap)

- **Phase 1 — read & shadow:** clean schema as ORM; KPI dashboard + 30-day
  trend, top products, cashier performance; expiry alerts (7/30/90), low-stock
  and transfer-aware smart-reorder drafts; Arabic AI assistant; the read-only
  eStock mirror adapter (`services/etl.py`, activates with real credentials).
- **Phase 2 — POS write-path:** `sp_create_sale` / `sp_deduct_stock` (FEFO) /
  `sp_check_credit` / `sp_transfer_stock` as atomic, tested services, with the
  eStock data-quality issues fixed by design (credit limit enforced, expired
  stock locked, stock never negative). T-SQL equivalents in
  [`../sql/procedures-and-views.sql`](../sql/procedures-and-views.sql).
- **Clinical advisory (Titan/Drug-Eye layer):** `services/clinical.py` surfaces
  drug interactions (incl. duplicate-ingredient/-class), in-stock generic
  alternatives, and age-band dosing — **advisory only, never blocks a sale**
  (docs/03 §5–6). Runs offline on curated active-ingredient rules and flips to a
  live read-only Titan source when one is configured (same gated-adapter pattern
  as the eStock mirror). Surfaced at POS (advisory banner), on the drug-card
  page, and via the Arabic assistant (`drug_advice`).

## Principles
- ProCare DB is the system of record; **eStock and Titan are read-only sources** (transition only).
- All strings externalized for ar/en. Arabic + light are defaults; English + dark are toggles.
- Secrets only in `config/connections.json` (git-ignored); the AI key comes from the environment.
