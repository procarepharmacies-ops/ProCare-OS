# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

ProCare OS — a standalone pharmacy management system for Procare Pharmacies (two branches: Main/مسهله and Elsanta/السنطه). Arabic-first (RTL) UI with English toggle. It is replacing the legacy **eStock** system in three phases: mirror (read-only ETL) → parallel pilot → cutover. During transition, eStock is a read-only source only.

**This is production software running a real pharmacy.** Data loss, crashes, or silent failures cost money and can harm patients. Quality is not optional.

## Commands

### Backend (FastAPI, Python 3.12) — from `src/backend/`

```bash
pip install -r requirements.txt
python run.py                          # dev server on :8000, docs at /docs
python -m pytest                       # full test suite (~89 tests)
python -m pytest app/tests/test_pos.py                 # one file
python -m pytest app/tests/test_pos.py -k credit       # one test by keyword
python -m app.db.seed                  # force a clean demo reseed
python -m app.services.etl --status    # eStock mirror: offline vs live + mapping plan
python -m app.services.etl --check     # verify the eStock login is truly READ-ONLY
python -m app.services.etl --run       # run the full read-only mirror
```

First backend start auto-creates the schema and seeds demo data into `src/backend/data/procare.db` (SQLite, git-ignored). No database setup needed for dev.

### Frontend (Next.js 15 / React 19) — from `src/frontend/`

```bash
npm install
npm run dev        # :3000
npm run build
npm run lint
```

### Full stack

- Docker: `docker compose up -d --build` — UI :3000, API :7000, SQL Server :1433. `deploy/procare.sh` is the start/stop/update/logs/health control center.
- Windows one-click launchers live in `deploy/` (`ProCare-Desktop-Icon.bat`, `ProCare-Autostart-Install.bat`); `deploy/ProCare-Connect-eStock.bat` is the user-facing eStock connector (config → test → sync → auto-enable).
- `.claude/launch.json` defines `procare-backend` and `procare-frontend` run configurations.
- Local-run logs: `.local-run/backend.log` and `.local-run/frontend.log`.

## Architecture

```
Browser → Next.js (:3000) —/api proxy→ FastAPI (:8000 dev / :7000 docker) → ProCare DB
                                            │ read-only sync/ETL (transition only)
                                            └→ eStock `stock` DB + Titan/Drug-Eye (clinical)
```

### Backend layering (`src/backend/app/`)

- `api/` — thin FastAPI routers only; all business logic lives in `services/`.
- `services/` — one module per domain (pos, purchasing, cashdesk, loyalty, accounting, transfers, etl, sync, ai, llm, clinical, whatsapp, scheduler, tasks…). This is where guardrails are enforced.
- `db/models.py` — ORM mirroring `sql/procare-schema.sql` (real FKs, checks, `branch_id` on every row). `db/base.py` picks SQLite (dev) vs SQL Server (prod). `db/migrate.py` holds the real staff roster created at startup plus idempotent column-add migrations; `db/seed.py` seeds demo data when no live eStock source is configured, so everything runs offline.
- `config.py` — loads `config/connections.json` (git-ignored), falling back to `config/connections.example.json`. Placeholder markers (`REPLACE_ME`, etc.) count as "not configured" and trigger the SQLite/demo fallback. The API never exposes secrets — `/api/health` only reports *whether* a source is configured.
- `run.py` — dev launcher; sets `sys.path`/`PYTHONPATH` and loads `.env` (backend dir, then repo root) so it works from any cwd. `python-dotenv` is an optional import — a missing package must never take the backend down.
- Startup lifespan: ensure tables → idempotent migrations → seed (idempotent) → create today's ops tasks → spawn background sync thread if `SYNC_ENABLED=1`.

### eStock sync (`services/sync.py`, `services/etl.py`)

- **Read-only to eStock — SELECT only, ProCare never writes.** ETL uses a dedicated read-only SQL login; the preflight (`etl.py --check`) verifies a write is *blocked* before any run.
- Continuous background sync, interval via `SYNC_INTERVAL_SECONDS` (default 30s), enabled via `SYNC_ENABLED=1` in `.env`. Status at `GET /api/sync/status`.
- Sync failures must **never block pharmacy operations** — fail soft: log the full error, create an alert, continue. No silent failures.
- Each sync run is atomic per table — all-or-nothing, no partial updates.
- Demo/seed data must never corrupt synced production data.

### Non-negotiable guardrails (enforced in `services/`, tested in `app/tests/`)

- POS write-path (`services/pos.py`): FEFO batch deduction (always deduct by earliest expiry — pharma requirement), stock can never go negative, expired stock can't be sold, credit-limit block (override requires `can_sale_credit`), all-or-nothing transactions, every stock movement audited.
- **Fail-soft architecture** — no single feature crash may bring down the app. LLM features fall back to the offline keyword router when no API key is configured (`services/llm.py` provider registry: anthropic, gemini, ollama, claude-cli).
- Clinical/interaction output is **advisory only** — shown to the pharmacist, never silently blocks a sale.
- Loyalty points are audited; returns claw points back automatically.
- Role-based access: cashier ≠ manager ≠ CEO — new endpoints must respect roles.
- Multi-step DB changes always wrapped in a transaction/session; no orphaned records (FKs enforced).
- Idempotency everywhere: `seed.py`, migrations in `migrate.py`, scheduled tasks, and sync runs must all tolerate re-runs (same input = same safe state, no duplicates, no errors).
- Schema changes: back up the DB first and make migrations reversible; test on a copy before running against real data.

### Frontend (`src/frontend/app/`)

- One directory per screen (pos, inventory, purchasing, customers, accounting, reports, tasks, transfers, prescriptions…). `layout.js` sets `<html dir/lang>` with a no-flash theme script; `providers.js` holds language + theme context persisted in `localStorage`; `i18n.js` has ar (default) / en strings; `globals.css` defines light/dark tokens as CSS variables. `api.js` is the backend client. PWA (manifest + service worker) — live data is never cached.
- **Arabic/RTL and Light are the defaults**; English and Dark are toggles. Every screen and every new string must be fully bilingual — no English-only flows. Test that Arabic text doesn't break layout.
- `/api` is proxied server-side to the backend via `next.config.mjs` — keep that intact; no CORS setup should be needed.

## Development practices

- **Never push to `main` directly** — branch + PR, tests green first.
- Commit format: `<type>: <subject (≤50 chars)>` + wrapped body; types: fix, feat, refactor, test, docs, perf. No vague "fix stuff".
- New features require a `test_*.py` covering the happy path + edge cases.
- Type hints (`-> ReturnType`) on Python functions.
- No TODOs committed to main — fix it or file an issue.
- Error messages are user-facing (Arabic/English) and actionable; log the full context server-side, never surface a bare "Internal Server Error".
- Windows is a first-class target: `.bat` scripts need backslash paths, clear success/failure output, and correct exit codes; test on real Windows before declaring Windows support.

### Pre-push checklist

- Backend starts clean: `python run.py` → Uvicorn running; `/api/health` returns ok.
- `python -m pytest` passes; `npm run build` succeeds (no hydration mismatches).
- Bilingual UI checked (RTL layout intact).
- If `SYNC_ENABLED`, `GET /api/sync/status` shows `"running": true` with a recent timestamp.
- No secrets in code, logs, or config; DB backed up if the schema changed.

### If something breaks

1. Logs first: `.local-run/backend.log`, browser console, `GET /api/sync/status`.
2. If DB corrupted: restore from backup (SQL Server `RESTORE DATABASE`, or the backed-up `.db` file).
3. Don't hide errors — log fully, alert (WhatsApp) if critical.
4. Commit a fix, not a workaround.

## Reference material

- `docs/01-architecture.md` — full architecture + security guardrails; `docs/02-eStock-database-reference.md` — legacy schema audit; `docs/06-roadmap.md` — phase plan.
- `sql/` — canonical clean schema, stored procedures, dashboard queries that the services implement.
