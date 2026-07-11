# ProCare OS

> **This is a real pharmacy management system.** Quality is not optional. Data loss, crashes, or silent failures cost money and harm patients.

## Quick Start

**Local development (Windows/Mac/Linux):**
```bash
cd src/backend && pip install -r requirements.txt && python run.py   # :8000
cd src/frontend && npm install && npm run dev                        # :3000
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

[Runtime: Backend (run.py on :8000)]
  ├─ Startup: load .env, ensure DB tables, seed demo data (idempotent), create today's daily ops tasks
  ├─ Lifespan: spawn background ETL thread if SYNC_ENABLED=1
  ├─ Sync Thread: every SYNC_INTERVAL_SECONDS (default 30), query eStock, transform, insert into ProCare DB (atomic per table)
  └─ Routes: /api/* (REST), /docs (Swagger), /health, /sync/status

[Runtime: Frontend (Next.js on :3000)]
  ├─ Startup: load i18n, build SSR pages
  ├─ Proxy: all /api/* → backend:8000 (server-side; users never see backend URL)
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
