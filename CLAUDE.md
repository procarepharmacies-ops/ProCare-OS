# ProCare OS

> **This is a real pharmacy management system.** Quality is not optional. Data loss, crashes, or silent failures cost money and harm patients.

## Quick Start

**Local development (Windows/Mac/Linux):**
```bash
cd src/backend && pip install -r requirements.txt && python run.py   # :8100
cd src/frontend && npm install && npm run dev                        # :3100
```

**Production (Docker):**
```bash
docker compose up -d --build
# UI http://localhost:3000 · API http://localhost:3000/api (proxied)
```

**Connect real eStock database:**
```bash
deploy/ProCare-Connect-eStock.bat  # Windows pharmacy PC only
```

---

## Production-Grade Standards

### Server Health & Uptime
- Always monitor backend logs (`.local-run/backend.log`) for crashes, errors, memory leaks
- Check `/api/health` endpoint before and after every deployment — must return `{"status": "ok"}`
- Ensure database connection pool is stable (no connection leaks)
- Sync status at `GET /api/sync/status` must show `"running": true` with recent timestamp
- Alert immediately if any service drops or fails to respond

### Database Integrity & Quality (CRITICAL FOR PHARMACY)

**FEFO Compliance (non-negotiable):**
- Stock movements always sorted by expiry date (First-Expiry-First-Out)
- When picking stock for a sale, eldest-expiry items reserved first
- Transfers between branches respect FEFO automatically (see `services/pos.py:transfer_stock`)

**Idempotent Operations:**
- `src/backend/app/db/seed.py` — running twice on same DB = no errors, no duplicates
- `src/backend/app/db/migrate.py` — all column adds use `ensure_*` pattern, safe to re-run
- ETL sync (`services/etl.py`) — each run is all-or-nothing per table (atomic)
- Tasks (`services/tasks.py:ensure_daily_ops_tasks`) — called daily, creates today's tasks once
- Backup before any schema change; test migrations on a copy first

**Transaction Safety:**
- All multi-step changes wrapped in SQLAlchemy sessions or SQL transactions
- Foreign key constraints enforced — no orphaned records
- No silent failures — if sync fails, create alert task + log full error

### eStock Sync Reliability

**Read-Only to eStock:**
- ProCare performs SELECT-only queries on eStock (never writes)
- Preflight check (`GET /api/sync/preflight`) validates read-only login before each sync

**Continuous Sync (Configurable):**
- Controlled by `.env` flags: `SYNC_ENABLED=1` (default 0) and `SYNC_INTERVAL_SECONDS` (default 30)
- Runs in background thread spawned on backend startup (see `run.py` lifespan)
- Monitors: products, customers, vendors, stock, sales, purchases

**Sync Failures Do NOT Block Pharmacy:**
- Soft failure: log the error, create an alert task, continue accepting sales
- Dashboard shows sync status but doesn't wait on it (async in background)
- Status endpoint `GET /api/sync/status` reveals health without blocking operations

### Feature Quality Standards

**Fail-Soft Architecture:**
- No single feature crash should bring down the pharmacy app
- LLM calls fall back to keyword router if API key missing (see `services/llm.py`)
- WhatsApp outage never blocks a sale or prescription workflow
- Expired transfer requests don't prevent cashier operations

**Role-Based Access:**
- Cashier: sales, returns, view-only inventory
- Manager: approvals (transfers, POs), reports, scheduling
- CEO: full access including settings, user management, backups

**Accessibility:**
- All UI fully bilingual (Arabic RTL + English LTR)
- Arabic text never breaks layout; RTL mode tested
- High contrast, keyboard navigable, mobile-friendly (PWA-installable)

**API Response Times:**
- Dashboard: <500ms (KPI cards, charts, top products)
- Sync-heavy endpoints: <2s
- Monitor with `GET /api/health` timing

### Development Practices

**Commit Message Format:**
```
<Type>: <subject (50 chars max)>

<Description (wrap at 72 chars)>

<Breaking changes, related issues, testing notes>
```

Types: `fix`, `feat`, `refactor`, `test`, `docs`, `perf`

**Never push to main directly** — always PR, always test on a feature branch.

**Test Coverage:**
- New features require `test_*.py` covering happy path + edge cases
- Run `pytest app/tests/` before pushing
- No test = no merge

**Code Quality:**
- Type hints on all Python functions: `def foo(x: str) -> dict:`
- Check for SQL injection, XSS, CORS misconfig, credential leaks before merge
- No `TODO`s in main — either fix it now or file an issue

**Windows PC Compatibility:**
- Backend must gracefully handle missing `python-dotenv` (optional import in `run.py`)
- Seed must be idempotent — running twice = no errors, no duplicates
- Batch scripts (`.bat`) use backslashes (`\`), not forward slashes
- Clear success/failure messages and exit codes in `.bat` files
- Always test on actual Windows PC before declaring support

---

## Architecture & File Map

```
[Pharmacy Windows PC or Linux/Mac Dev]
  ├─ .env (git-ignored: ANTHROPIC_API_KEY, SYNC_ENABLED, SYNC_INTERVAL_SECONDS, etc.)
  ├─ config/
  │  ├─ connections.example.json (template for eStock credentials)
  │  └─ connections.json (git-ignored; user fills in read-only eStock login)
  ├─ src/backend/
  │  ├─ run.py (FastAPI startup; lifespan: ensure_seeded, spawn sync thread, create daily tasks)
  │  ├─ app/
  │  │  ├─ main.py (route registration)
  │  │  ├─ db/
  │  │  │  ├─ models.py (SQLAlchemy: 20+ tables including Product, Customer, Sale, Prescription, EmployeeTask, StockTransfer, etc.)
  │  │  │  ├─ seed.py (demo data, idempotent: safe to run twice)
  │  │  │  └─ migrate.py (idempotent column adds via ensure_* pattern)
  │  │  ├─ services/
  │  │  │  ├─ llm.py (provider registry: anthropic, gemini, ollama/hermes, claude-cli; fail-soft)
  │  │  │  ├─ etl.py (eStock→ProCare sync: read, validate, insert atomically per table)
  │  │  │  ├─ prescriptions.py (capture → review → dispensed workflow)
  │  │  │  ├─ transfers.py (stock transfer requests + approval + auto-task creation)
  │  │  │  ├─ pos.py (cart, substitutions, out-of-stock → transfer, FEFO picker)
  │  │  │  ├─ tasks.py (daily/weekly ops templates, auto-assign by role, priority/category)
  │  │  │  ├─ whatsapp.py (manager alerts, invoice messages, return confirmations; swallow on fail)
  │  │  │  ├─ scheduler.py (background jobs: reports, expiry alerts, PO drafts)
  │  │  │  └─ inventory.py (forecasts, stock levels, product insights for dashboard)
  │  │  ├─ api/
  │  │  │  ├─ routes.py (all endpoints: /sales, /prescriptions, /transfers, /tasks, /inventory, /sync/status, /health)
  │  │  │  └─ (structured by domain)
  │  │  └─ tests/
  │  │     ├─ test_daily_tasks.py (idempotency, priority, role assignment)
  │  │     ├─ test_product_insight.py (dashboard drill-down data)
  │  │     ├─ test_prescriptions_flow.py (capture → review → cart → dispensed)
  │  │     ├─ test_transfer_requests.py (request → approve → stock moved)
  │  │     └─ (pytest suite)
  │  └─ requirements.txt (sqlalchemy, fastapi, python-dotenv, pyodbc for SQL Server, etc.; pinned versions)
  ├─ src/frontend/
  │  ├─ next.config.mjs (Proxy /api/* to backend:8000 server-side, no CORS)
  │  ├─ app/
  │  │  ├─ page.js (Dashboard: KPI cards, top-products drill-down modal, cashier list, branch breakdown)
  │  │  ├─ pos/page.js (Cart, substitutions, out-of-stock → transfer request, ?rx= prescription seeding)
  │  │  ├─ prescriptions/page.js (Capture, analyze, review step, product resolution, hand-off to POS)
  │  │  ├─ tasks/page.js (Daily ops, grouped Overdue/Today/Week/Later, priority+category badges)
  │  │  ├─ transfers/page.js (Pending transfer requests, approve/reject buttons)
  │  │  ├─ i18n.js (Arabic/English strings, RTL logic)
  │  │  ├─ api.js (HTTP client wrapping backend calls)
  │  │  └─ components/DetailModal.js (Reusable product insight modal)
  │  └─ public/manifest.json (PWA installable on mobile)
  ├─ deploy/
  │  ├─ ProCare-Connect-eStock.bat (User-facing: config → test connection → full sync → auto-enable continuous)
  │  ├─ Dockerfile.backend (Python 3.11 + FastAPI)
  │  ├─ Dockerfile.frontend (Node 22 + Next.js)
  │  ├─ docker-compose.yml (full stack: backend, frontend, SQL Server, eStock seed)
  │  └─ README.md (deployment guide: Multipass, Docker, Windows PC)
  └─ CLAUDE_SYSTEM_PROMPT.md (long-form standards; CLAUDE.md is the working guide)

[Runtime: Backend (run.py on :8100)]
  ├─ Startup: load .env, ensure DB tables, seed demo data (idempotent), create today's daily ops tasks
  ├─ Lifespan: spawn background ETL thread if SYNC_ENABLED=1
  ├─ Sync Thread: every SYNC_INTERVAL_SECONDS (default 30), query eStock, transform, insert into ProCare DB (atomic per table)
  └─ Routes: /api/* (REST), /docs (Swagger), /health, /sync/status

[Runtime: Frontend (Next.js on :3100)]
  ├─ Startup: load i18n, build SSR pages
  ├─ Proxy: all /api/* → backend:8100 (server-side; users never see backend URL)
  └─ Routes: / (dashboard), /pos, /prescriptions, /tasks, /transfers, /reports (all bilingual)

[Database: SQLite (dev) or SQL Server (production)]
  ├─ Tables: ~20 (products, customers, sales, purchases, stock, transfers, prescriptions, employee_tasks, vendors, etc.)
  ├─ Constraints: foreign keys enforced, no orphans, FEFO sorting on stock dates
  ├─ Triggers: none (app handles business logic)
  └─ Backup: .db file or RESTORE DATABASE before sync runs
```

---

## Pre-Push Checklist

Before committing and pushing to main:

- [ ] Backend starts cleanly: `python run.py` → `Uvicorn running on http://0.0.0.0:8000`
- [ ] Frontend builds: `npm run build` (no hydration mismatches)
- [ ] `/api/health` returns `{"status": "ok"}`
- [ ] All tests pass: `pytest app/tests/` (green lights)
- [ ] No hardcoded secrets, API keys, or credentials in code
- [ ] Database integrity: no orphaned records, foreign keys intact
- [ ] Bilingual UI tested (Arabic text rendering, RTL layout)
- [ ] Sync status accessible at `GET /api/sync/status` (if SYNC_ENABLED)
- [ ] Commit message follows format (Type: subject + description)

---

## If Something Breaks

**1. Check logs first:**
   - Backend: `.local-run/backend.log` or `docker logs <container>`
   - Frontend: browser console (F12), terminal output
   - Sync: `GET /api/sync/status` response shows error

**2. Restore from backup (if DB corrupted):**
   ```bash
   # SQLite: restore from .db backup
   cp backup.db procare.db
   
   # SQL Server: restore database
   RESTORE DATABASE ProCare FROM DISK='\\path\to\backup.bak'
   ```

**3. Never hide errors:**
   - Log fully with context, stack trace, user input
   - Alert users via dashboard error banner + WhatsApp if critical

**4. Post-mortem:**
   - Commit a fix, not a workaround
   - Document the root cause in the commit message
   - Add a test to prevent regression

---

## Key Files to Monitor

| File | Why | What to Watch |
|------|-----|---------------|
| `src/backend/app/db/seed.py` | Demo data | Running twice = no dupes, no errors |
| `src/backend/app/services/etl.py` | eStock sync | Connection errors, partial syncs, data quality |
| `src/backend/run.py` | Startup | Handles missing dotenv gracefully, lifespan errors |
| `src/backend/requirements.txt` | Dependencies | Pin versions; keep sqlalchemy, fastapi, python-dotenv |
| `src/frontend/next.config.mjs` | Build/proxy | /api proxy to backend, no accidental CORS |
| `config/connections.json` | eStock creds | Git-ignored; read-only login validation on startup |
| `.env` (repo root) | Runtime config | Git-ignored; ANTHROPIC_API_KEY, SYNC_ENABLED, SYNC_INTERVAL_SECONDS |
| `deploy/ProCare-Connect-eStock.bat` | User workflow | Exit codes, Notepad close, sync logs readable |

---

## Context for Claude Instances

When Claude works on this repo:
- **This is production pharmacy software.** Every feature must handle failure gracefully.
- **FEFO is non-negotiable.** Stock always picked by oldest expiry date first.
- **Idempotency matters.** Seed, migrations, syncs, tasks must tolerate re-runs safely.
- **Pharmacy never waits on sync.** Sync failures log + alert but don't block sales.
- **Bilingual from day one.** Arabic RTL + English LTR, all strings in `i18n.js`.
- **Windows PC deployment.** Backend handles missing python-dotenv; seeds are idempotent; batch scripts have clear exit codes.
- **Read-only to eStock.** ProCare never writes to the source database, only reads.

---

## Project Memory (B.L.A.S.T. protocol)

This repo is run under the B.L.A.S.T. protocol (Blueprint → Link → Architect →
Stylize → Trigger). CLAUDE.md is the **constitution** (schemas, rules,
invariants — law). Working memory lives in:

| File | Role |
|------|------|
| `task_plan.md` | Phases, goals, checklists (the approved Blueprint) |
| `findings.md` | Research, discoveries, constraints |
| `progress.md` | Run log: what was done, errors, test results |

Rules: define the data schema here **before** coding a feature; update the
plan/progress files after every meaningful task; amend CLAUDE.md only when a
schema, rule, or architectural invariant changes. On tool failure: analyze the
real stack trace, patch, re-test, then record the learning in `findings.md`.

## Data Schemas

### Stocktaking (الجرد) — `stock_counts` / `stock_count_lines`

Count session (`POST /api/stocktaking` → `GET /api/stocktaking/{id}`):

```json
{
  "count_id": 1,
  "branch_id": 1,
  "count_type": "full | periodic | partial",
  "status": "open | posted | cancelled",
  "note": "string?",
  "created_at": "ISO", "posted_at": "ISO?",
  "lines": [{
    "line_id": 1, "batch_id": 10, "product_id": 5,
    "name_ar": "…", "name_en": "…", "shelf_location": "A3?",
    "exp_date": "2027-01-31?", "buy_price": 10.0, "sell_price": 15.0,
    "expected_qty": 12.0,
    "counted_qty": 11.0,
    "variance": -1.0,
    "variance_value": -10.0,
    "posted_delta": -1.0
  }],
  "summary": {
    "total_lines": 0, "counted_lines": 0, "variance_lines": 0,
    "shortage_qty": 0, "shortage_value": 0,
    "overage_qty": 0, "overage_value": 0
  }
}
```

Invariants: posting sets each counted batch to its **physical** quantity
(delta computed against the LIVE amount at post time, not the snapshot); every
non-zero delta writes a `stock_movements` row (`reason='adjust'`,
`ref_id=count_id`); posting is atomic; `periodic` with no explicit product list
scopes to the branch's 30-day top movers; sessions never block sales.

### Units (وحدة كبرى/صغرى) — on `products`

`unit_big` (علبة), `unit_small` (شريط/أمبول/كبسولة), `unit_factor` (small per
big, >= 1). **Stock amounts are ALWAYS stored in big units**; selling n small
units deducts n/`unit_factor`. POS sends cart amounts in big units — the unit
selector is a display/entry convenience only. ETL maps eStock's
product_unit1/product_unit2/product_no2per1 (graceful when absent → factor 1).

### Stagnant items (الأصناف الراكدة)

`GET /api/inventory/stagnant?days=90&branch_id=` → stocked items (on-hand > 0)
with no sale in `days` days: on_hand, value (buy price), last_sale, idle_days +
totals. `POST /api/stocktaking {scope:"stagnant"}` opens a partial count scoped
to that list.

### Cross-branch availability

`list_products` with `branch_id` returns `other_branches: [{branch_id, branch,
on_hand}]` per product (live, available stock only) — the POS shows it on
out-of-stock rows so the cashier knows the other branch has it.

### Sync wipe rule

`etl._wipe_branch_rows` must delete children by BOTH batch linkage and parent
transfer linkage — requested transfers have NULL-batch lines.

### Product search

`GET /api/inventory/products?search=<q>` ranks **prefix** matches on
name_ar/name_en/code first, then scientific-name prefix, then contains-anywhere
— one typed letter must list every product beginning with that letter.

### Forecasting (Phase 5) — `forecasts` table

Nightly pre-computed demand forecasts per product×branch, cached for <500ms dashboard load:

```json
{
  "forecast_id": 1,
  "product_id": 5, "branch_id": 2,
  "forecast_date": "2026-07-20",
  "forecast_horizon": 30,
  "daily_avg": 2.5,
  "trend_per_day": 0.05,
  "seasonality_factor": 1.15,
  "projected_demand": 85.3,
  "stockout_date": "2026-08-15?",
  "days_of_cover": 12.4,
  "method": "exp_smoothing",
  "computed_at": "ISO"
}
```

Invariants: forecast runs nightly (scheduler) per product×branch; day-of-week seasonality applied (weekends often higher for OTC); Holt-style double exponential smoothing (α=0.2, β=0.1); stockout_date = null if trend flat/negative; safe to re-run (idempotent by truncating daily and re-populating).

### Decision Cards (Phase 5) — `decision_cards` table

Daily briefing items: actionable insights requiring manager approval or review:

```json
{
  "card_id": 1,
  "branch_id": 1, "created_at": "ISO",
  "card_type": "stockout_risk | below_min | expiry_warning | overstocked | out_of_bounds",
  "severity": "critical | warning | info",
  "title_ar": "…", "title_en": "…",
  "body_ar": "…", "body_en": "…",
  "action_type": "create_po | create_transfer | promote | adjust_min | review",
  "ref_product_id": 5?, "ref_purchase_id": null?,
  "status": "open | dismissed | actioned",
  "actioned_at": "ISO?", "actioned_by": "employee_id?"
}
```

Invariants: cards created daily (nightly job) from forecast/inventory state; action buttons in UI trigger the actual operation; manager can dismiss without action (audit trail); cards auto-archive after 7 days of no interaction.

### Sales-rep commissions (Phase 6) — `commission_runs` / `commission_run_lines`

حاسبة عمولة مندوب البيع: total each rep's **net** sales in a period, apply a
percentage, then post the payout as an auditable run.

```json
{
  "run_id": 1,
  "branch_id": 0,                     // 0/NULL = consolidated (all branches)
  "period_start": "2026-06-01", "period_end": "2026-06-30",
  "default_rate_pct": 5.0,
  "total_sales": 0.0, "total_commission": 0.0,
  "status": "posted | void",
  "note": "string?", "created_at": "ISO", "posted_by": "employee_id?",
  "voided_at": "ISO?",
  "lines": [{
    "line_id": 1, "employee_id": 2, "name_ar": "…", "name_en": "…",
    "sales_value": 0.0,               // NET: non-return invoices − return invoices
    "bills_count": 0,                 // non-return invoices only
    "rate_pct": 5.0,
    "commission": 0.0                 // sales_value × rate_pct / 100
  }]
}
```

Endpoints (CEO/manager): `GET /api/commissions/preview?period_start&period_end&
branch_id&default_rate_pct` (read-only), `POST /api/commissions/runs` (persist),
`GET /api/commissions/runs`, `GET /api/commissions/runs/{id}`,
`POST /api/commissions/runs/{id}/void`.

Invariants: sales attributed to a rep via `sales.cashier_id` (ETL-mirrored);
`sales_value` nets returns in a single grouped scan (dialect-portable `case`,
no SQL Server `TRIM`/`LENGTH`); NULL-cashier sales are excluded (no rep to pay);
preview is read-only, posting **recomputes** from live sales inside the txn
(never trusts a client preview) and is atomic; re-posting the same window is
allowed (new run — history preserved, no silent dedupe); voiding keeps the row +
lines (`status='void'`, audit trail) and is idempotent; commission math never
blocks sales. Tables added idempotently via `ensure_commission_tables`.

### Shareholders (Phase 6) — `shareholders` / `dividend_payments`

Mirror of eStock `company_Owner` + `Gedo_Dividends_paied` (owner's register):
each shareholder's capital (starting → current) and dividends paid per year.

Invariants: ETL `_load_shareholders` is `has_table`-guarded (absent source →
skipped, never an error); shareholders **upsert by `source_id`** (eStock
`coow_id`) so re-syncing from either branch server keeps ONE owners register —
they are deliberately NOT in the destructive `_WIPE_ORDER`; deleted owners
(`company_Owner.deleted`) are skipped; dividends upsert by `source_id` and any
dividend whose owner is unknown/deleted is dropped. `GET /api/shareholders`
(register + ownership `share_pct` + dividend totals) and `/{id}` (annual
dividend history) are **CEO-only**, read-only. Tables added idempotently via
`ensure_shareholder_tables`.

### Payroll depth (Phase 6) — `payroll_records`

Mirror of eStock `Employee_salary` (monthly payroll). One row per source
payroll record: `basic_salary`, `commission`, `over_commission`, `deduction`,
`absence_money`, `cash_advance`, `source_total`, and a recomputed `net`.

Invariants: `net = basic + commission + over_commission − deduction −
absence_money − cash_advance` (recomputed in ETL + on any read, independent of
the source's own `total`); ETL `_load_payroll` is `has_table`-guarded and
resolves `Employee_salary.emp_id` → username (via the source `Employee` master)
→ ProCare `employee_id` because ProCare employees carry no source id — rows for
unknown employees are skipped; **upsert by `source_id`** (`salary_id`), NOT in
the destructive `_WIPE_ORDER` (employees are never wiped). `GET /api/employees/
{id}/payroll` (CEO-only, via the employees router) returns the latest record's
panel (base / commission[+over] / deductions[deduction+absence] / advances /
net) + full monthly history, with a `base_salary_on_file` fallback when no
record is mirrored yet. Table added idempotently via `ensure_payroll_table`.

Salary advances (سلف) are a **separate** ledger — `salary_advances` (mirror of
`Employee_cash_advance`: `source_id`=`cash_advance_id`, `employee_id`, `amount`,
`advance_type`) — distinct from the monthly `payroll_records.cash_advance`
roll-up. ETL `_load_salary_advances` shares the `_estock_empid_to_pk`
(emp_id→username→employee) resolver, upserts by `cash_advance_id`, and is
`has_table`-guarded. The `/payroll` panel returns the advances ledger (newest
first) + `advances_total` alongside the monthly panel. Idempotent
`ensure_salary_advance_table`.

---

## Operations Monitoring (SRE) — watchdog · digest · db_health

**Watchdog (external, no DB):** `deploy/procare-watchdog.{sh,bat}` polls
`GET /api/health` every `INTERVAL` (60s); after `FAIL_THRESHOLD` (3) consecutive
failures — a non-200, or (when `REQUIRE_SQLSERVER=1`) a 200 whose `procare_db`
is not `sqlserver` (silent SQLite fallback) — it restarts the stack via
`deploy/procare.sh restart` and sleeps `COOLDOWN`. Also restarts on
`docker inspect .State.OOMKilled`. `--once` exits 0 (healthy) / 1 (unhealthy)
for cron/systemd/Task Scheduler. Belt-and-suspenders in-process check:
`scheduler._run_health_selfping` (`db_health.ping()`, every 5 min).

**8am CEO digest** — `dashboard.ceo_digest(session, branch_id=None)`:

```json
{
  "as_of": "2026-06-25", "branch_id": 0,
  "revenue_yesterday": 0.0, "bills_yesterday": 0,
  "top_sellers": [{"product_id": 5, "name_ar": "…", "name_en": "…", "units": 0.0, "revenue": 0.0}],
  "low_stock": 0, "expiring_7d": 0,
  "debtors_count": 0, "debtors_over_limit_total": 0.0
}
```

Reports on **yesterday** (a closed trading day), reuses `dashboard._revenue_between`
+ `dashboard.top_products(start=yday, end=yday, limit=3)`. Sent by
`scheduler._run_ceo_digest` on a **branch-local** 08:00 cron
(`CronTrigger(timezone=ZoneInfo(BRANCH_TIMEZONE))`, empty → server-local) via
`whatsapp.ceo_digest_message`. Gated on `AUTOMATION_ENABLED` + APScheduler;
`notify_manager` self-gates on `manager_phone` + WhatsApp creds.

**Disk + DB-size monitor** — `services/db_health.py`, `db_health.check()`:

```json
{
  "severity": "ok | info | warning | critical",
  "alerts": ["…"],
  "db": {"engine": "sqlite|sqlserver", "data_mb": 0.0, "log_mb": 0.0,
         "total_mb": 0.0, "cap_mb": 10240.0, "pct_of_cap": 0.0},
  "disk": {"path": "…", "total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0, "free_pct": 0.0},
  "checked_at": "ISO"
}
```

Invariants: DB size vs the SQL Server Express **10 GB cap** (`DB_SIZE_CAP_MB`,
default 10240) at 80/90/95 %; disk free at <20/10/5 %; grading lives in the
**pure** `evaluate()` (unit-testable, no I/O); `sys.database_files` path is
`IS_SQLITE`-guarded; hourly `scheduler._run_db_health` alerts only when severity
**rises** (`alert_if_worse`, no hourly spam); all I/O fail-soft (never raises
into a request/scheduler). Exposed at `GET /api/automation/db-health` (CEO/manager).
Env: `BRANCH_TIMEZONE` (IANA name), `DB_SIZE_CAP_MB`.

---

## Success Criteria

✅ Pharmacy operates all day without manual intervention or restarts  
✅ Real eStock data syncs continuously; demo data never corrupts production  
✅ All features accessible via Arabic UI; no English-only flows  
✅ Every failed operation leaves traceable logs + user-facing alert  
✅ Database stays consistent; no orphaned or duplicate records  
✅ Backup exists before every breaking change; rollback is possible  
✅ Code is clear enough that future developers (or you in 6 months) understand it  

---

**This system runs a real pharmacy. Quality is not optional.**
