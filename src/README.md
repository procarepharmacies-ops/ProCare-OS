# src/ — Application source (Phase 1 implemented)

ProCare OS code. Phase 0 (foundation) and **Phase 1 (mirror & read / shadow
mode)** are implemented: a working backend (dashboard KPIs, Arabic AI assistant,
expiry/low-stock alerts, drug-interaction lookup, ETL + reconciliation,
automation scheduler) and a real Next.js dashboard — runnable out of the box
against a seeded SQLite shadow DB, and wired to read SQL Server when credentials
exist. Quick start: backend [`backend/README.md`](backend/README.md), frontend
[`frontend/README.md`](frontend/README.md).

## Layout (as built)

```
src/
├── backend/                 # Python + FastAPI (stdlib-first; runs with no SQL Server)
│   ├── app/
│   │   ├── main.py          # FastAPI entrypoint (seeds demo DB + starts scheduler)
│   │   ├── config.py        # loads ../../config/connections.json (secrets stay server-side)
│   │   ├── db.py            # data facade: SQLite demo OR SQL Server (pyodbc) — one query() API
│   │   ├── sql/            # schema_sqlite.sql (clean schema) + views_sqlite.sql (AI whitelist)
│   │   ├── seed.py         # deterministic synthetic data (2 branches, ~90 days of sales)
│   │   ├── queries.py      # dashboard KPIs (branch + date aware)
│   │   ├── alerts.py       # expiry 90/30/7, low-stock reorder drafts, debtors
│   │   ├── ai.py           # PharmacyAI: Arabic NL -> constrained read-only SQL + validator
│   │   ├── drugs.py        # advisory drug interactions (Titan/Drug-Eye stand-in)
│   │   ├── etl.py          # eStock read-only mirror + data-quality rules + reconciliation
│   │   ├── scheduler.py    # PharmacyAutomation jobs (APScheduler)
│   │   └── api/routes.py   # HTTP surface
│   ├── tests/              # pytest: data-quality rules, KPIs, AI SQL guard, ETL, alerts, API
│   └── requirements.txt
│
└── frontend/                # React / Next.js (RTL, i18n ar/en, light/dark)
    └── app/
        ├── page.js          # dashboard composition + branch-scoped loading
        ├── api.js · i18n.js · providers.js
        ├── globals.css      # light/dark tokens + component styles
        └── components/       # Header, KpiCards, SalesChart, Panels, AiChat
```

## Build order (see roadmap)

1. **Phase 0 ✅** — backend skeleton + `config.py` reading `connections.json`; clean schema from
   [`../sql/procare-schema.sql`](../sql/procare-schema.sql); frontend skeleton with language + theme toggles.
2. **Phase 1 ✅ (shadow mode)** — read-only dashboard, Arabic AI assistant, expiry/low-stock alerts,
   drug lookup, ETL data-quality rules + reconciliation harness. Runs against the seeded shadow DB;
   connect the read-only eStock login to mirror live data and enable side-by-side reconciliation.
3. **Phase 2** — POS write path (`sp_create_sale`), pilot on Elsanta.
4. **Phase 3** — both branches on ProCare; eStock retired.

## Principles
- ProCare DB is the system of record; **eStock and Titan are read-only sources** (transition only).
- All strings externalized for ar/en. Arabic + light are defaults; English + dark are toggles.
- Secrets only in `config/connections.json` (git-ignored).
