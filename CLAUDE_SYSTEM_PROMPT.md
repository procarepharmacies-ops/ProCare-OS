# ProCare OS — Claude Fable 5 Professional System Prompt

## Project Overview
You are maintaining **ProCare OS**, a professional pharmacy management system serving real pharmacies in Arabic/English with live eStock database synchronization. This is production software handling real inventory, sales, customers, and medical workflows.

## Core Principles (NON-NEGOTIABLE)

### 1. Server Health & Uptime
- **Always monitor backend logs** for crashes, errors, memory leaks
- Check `/api/health` endpoint before and after every deployment
- Ensure database connection pool is stable (no connection leaks)
- Sync status at `GET /api/sync/status` must show `"running": true` with recent timestamp
- Alert immediately if any service drops or hangs for >5 seconds

### 2. Database Integrity & Quality
- **Zero data loss** — migrations must be reversible; test on a copy first
- **FEFO compliance** — stock movements always FIFO by expiry date (non-negotiable for pharma)
- **Idempotent operations** — all tasks, syncs, and batch jobs must tolerate re-runs (same input = same safe state)
- **Foreign key constraints** enforced — no orphaned records
- **Backup before any schema change** — `PRAGMA table_info(table_name)` before ALTER
- **Transaction safety** — all multi-step changes wrapped in `begin/commit` or SQLAlchemy sessions
- **No silent failures** — if a sync fails, create an alert task + log the full error

### 3. Sync Reliability (eStock ↔ ProCare)
- Read-only to eStock (SELECT only; ProCare never writes)
- Continuous sync (default 30s interval, configurable `SYNC_INTERVAL_SECONDS`)
- Sync failures do NOT block pharmacy operations (soft failure: log + alert, continue)
- Preflight check validates connection, read-only status, store_id mapping
- Each sync run is atomic — all-or-nothing per table (no partial updates)
- Monitor: products, customers, vendors, stock, sales, purchases

### 4. Feature Quality Standards
- **Fail-soft architecture** — no feature crash should bring down the pharmacy app
- **No hardcoded provider assumptions** — LLM fallback to keyword router if key missing
- **Role-based access** — operations respect user roles (cashier ≠ manager ≠ CEO)
- **Accessibility** — all UI fully bilingual (Arabic RTL + English LTR), high contrast, keyboard navigable
- **PWA-ready** — frontend installable on mobile, works offline-first where possible
- **API response time <500ms** for dashboard, <2s for sync-heavy endpoints

### 5. Development Practices
- **Commit message format:**
  ```
  <Type>: <subject (50 chars max)>

  <Description (wrap at 72 chars)>
  
  <Breaking changes, related issues, testing notes>
  ```
  Types: fix, feat, refactor, test, docs, perf
  
- **Never** push to `main` directly — always PR, always test
- **Test coverage** — new features require `test_*.py` that covers happy path + edge cases
- **Code review** — check for SQL injection, XSS, CORS misconfig, credential leaks before merge
- **Type hints** — all Python functions should have `-> ReturnType` annotations
- **No TODOs in main** — either fix it now or file an issue; don't commit future work

### 6. Windows PC Compatibility
- Backend must tolerate `python-dotenv` missing (optional import, graceful fallback)
- Seed.py must be idempotent — running twice on same DB = no errors, no duplicates
- Batch scripts (.bat) must have clear success/failure indicators and exit codes
- Paths use backslashes (`\`) not forward slashes in .bat files
- Always test on actual Windows before declaring Windows support

## Architecture Reference

```
[Windows Pharmacy PC]
  ├─ .env (git-ignored, user sets ANTHROPIC_API_KEY, SYNC_ENABLED, etc.)
  ├─ src/backend/
  │  ├─ run.py (FastAPI, lifespan: ensure_seeded, ensure_daily_ops_tasks)
  │  ├─ app/db/models.py (SQLAlchemy: Product, Customer, Sale, Prescription, EmployeeTask, StockTransfer, etc.)
  │  ├─ app/db/migrate.py (idempotent column adds: ensure_role_column, ensure_priority_column, etc.)
  │  ├─ app/services/
  │  │  ├─ llm.py (provider registry: anthropic, gemini, ollama, claude-cli)
  │  │  ├─ etl.py (eStock read, transform, validate, insert)
  │  │  ├─ prescriptions.py (capture → review → dispensed)
  │  │  ├─ transfers.py (stock transfer requests + approval workflow)
  │  │  ├─ pos.py (point-of-sale: cart, substitutions, out-of-stock triggers)
  │  │  ├─ tasks.py (daily/weekly ops templates, auto-assign by role)
  │  │  ├─ whatsapp.py (manager alerts, invoice messages, return confirmations)
  │  │  ├─ scheduler.py (background jobs: reports, expiry alerts, auto-purchase-orders)
  │  │  └─ inventory.py (forecasts, stock levels, product insights)
  │  └─ api/ (endpoints: /sales, /prescriptions, /transfers, /dashboard, /sync/status, etc.)
  ├─ src/frontend/
  │  ├─ app/page.js (dashboard: top-products drill-down, cashier list, by-branch breakdown)
  │  ├─ app/pos/page.js (cart, substitutions panel, out-of-stock → transfer request, ?rx= seeding)
  │  ├─ app/prescriptions/page.js (capture, analyze, review, resolve products, hand-off to POS)
  │  ├─ app/tasks/page.js (daily ops, grouped by Overdue/Today/Week, priority badges, category chips)
  │  ├─ app/transfers/page.js (pending requests, approve/reject buttons)
  │  ├─ app/i18n.js (Arabic/English all strings, RTL logic)
  │  └─ components/ (DetailModal, charts, forms — all bilingual)
  ├─ config/
  │  └─ connections.example.json (template for eStock read-only login)
  └─ deploy/
     ├─ ProCare-Connect-eStock.bat (user-facing one-click: config → test → sync → auto-enable)
     ├─ docker-compose.yml (optional: full stack in Docker)
     └─ README.md (deployment guide)

[Backend Process (run.py on :8000)]
  ├─ Startup: load .env, ensure DB tables, seed demo data (idempotent), create today's tasks
  ├─ Lifespan: spawn background sync thread (if SYNC_ENABLED=1)
  └─ Routes: /api/* (REST endpoints) + /docs (FastAPI Swagger)

[Frontend Process (Next.js on :3000)]
  ├─ Startup: load i18n, build SSR pages, start dev server
  ├─ Proxy: /api/* → backend:8000 (server-side, no CORS)
  └─ Routes: / (dashboard), /pos, /prescriptions, /tasks, /transfers, /reports, etc.

[SQLite (local) or SQL Server (production)]
  ├─ Tables: products, customers, sales, purchases, stock, transfers, prescriptions, employee_tasks, ...
  ├─ Triggers: none (app handles logic)
  └─ Backup: .db file or SQL Server backup before sync runs
```

## Key Files to Keep Eye On

| File | Why | Monitor For |
|------|-----|------------|
| `src/backend/app/db/seed.py` | Demo data seeding | Idempotency: running twice = no dupes, no errors |
| `src/backend/app/services/etl.py` | eStock sync engine | Connection failures, partial syncs, data quality after import |
| `src/backend/run.py` | Backend startup | Missing dotenv gracefully, lifespan errors, port binding |
| `src/backend/requirements.txt` | Dependencies | Keep `sqlalchemy`, `fastapi`, `python-dotenv` pinned to known-good versions |
| `src/frontend/next.config.js` | Build config | Proxy setup for /api routes stays intact; no accidental CORS |
| `config/connections.json` | eStock credentials | Git-ignored; user must create; read-only login validation on startup |
| `.env` (repo root) | Runtime config | Git-ignored; user sets ANTHROPIC_API_KEY, SYNC_ENABLED, SYNC_INTERVAL_SECONDS |
| `deploy/ProCare-Connect-eStock.bat` | User workflow | Exit codes are correct; Notepad closes properly; sync logs are readable |

## Monitoring Checklist

**Before pushing any change:**
- [ ] Backend starts without errors: `python run.py` → `Uvicorn running`
- [ ] `/api/health` returns `{"status": "ok"}` + sync status
- [ ] Database backup exists (if schema changed)
- [ ] All tests pass: `pytest app/tests/`
- [ ] Frontend builds: `npm run build` (no hydration mismatches, no errors)
- [ ] Bilingual UI tested (Arabic text doesn't break layout, RTL works)
- [ ] Sync status accessible at `GET /api/sync/status` (if SYNC_ENABLED)
- [ ] No hardcoded secrets in logs or config

**After deployment on real pharmacy PC:**
- [ ] Dashboard loads in <3s
- [ ] Demo data visible (products, sales, cashiers)
- [ ] Click a product → drill-down modal opens (forecast, by-branch)
- [ ] Click cashier row → employee details load
- [ ] Tasks page shows today's tasks (opening checklist, etc.)
- [ ] Sync runs every 30s (check `.local-run/backend.log` for "Sync complete" messages)
- [ ] eStock connector batch script walks through config → test → sync without errors

## If Something Breaks

1. **Check logs first:**
   - Backend: `.local-run/backend.log` (or docker logs)
   - Frontend: browser dev console + terminal output
   - Sync: `GET /api/sync/status` response

2. **Restore from backup** (if DB corrupted):
   ```sql
   -- If using SQL Server
   RESTORE DATABASE ProCare FROM DISK='...\backup.bak'
   ```

3. **Don't hide errors** — log fully, alert the user via WhatsApp if critical

4. **Post-mortem** — commit a fix, not a workaround

## Communication Standards

- **Commit messages:** Clear, specific, tied to features or bugs (no vague "fix stuff")
- **PR descriptions:** Summarize what changed, why, and what to test
- **Code comments:** Only for non-obvious WHY (not what), max 1-2 lines
- **Error messages:** User-facing (Arabic/English), actionable, never "Internal Server Error" without context logs
- **Live feedback:** Dashboard, API responses, WhatsApp alerts — users always know system state

## Success Criteria

✅ **Pharmacy can operate all day without manual intervention or server restarts**
✅ **Real eStock data syncs continuously; demo data never corrupts production**
✅ **All features accessible via Arabic UI; no English-only flows**
✅ **Every failed operation leaves a traceable log + user-facing alert**
✅ **Database stays consistent; no orphaned or duplicate records**
✅ **Backup exists before every breaking change; rollback is possible**
✅ **Code is clear enough that the next developer (or you in 6 months) understands it**

---

**Remember:** This system runs a real pharmacy. Data loss, crashes, or silent failures cost money and harm patients. Quality is not optional.
