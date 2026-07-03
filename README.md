# ProCare OS — نظام بروكير لإدارة الصيدليات

**The complete, independent operating system for Procare Pharmacies.**
Arabic-first (RTL) · Multi-branch (Main + Elsanta) · POS · Inventory · Purchasing · Accounting · HR · AI assistant · Installable as an app.

> مش مجرد صيدلية… عيلة لكل احتياجاتك

---

## What it is

ProCare OS is a full-stack pharmacy management system with its **own clean database** (real foreign keys, indexes, audited stock movements). It mirrors the legacy eStock system read-only during the transition, runs in parallel, then replaces it entirely — covering **100% of every eStock feature that was actually used**, plus a modern layer eStock never had: AI assistant, clinical drug advisory, smart reorder, analytics, and a glassmorphism Arabic-first UI.

| | |
|---|---|
| **Backend** | Python · FastAPI · SQLAlchemy — SQLite in dev, SQL Server in production |
| **Frontend** | Next.js (React) · RTL Arabic default, English toggle · light/dark themes · PWA |
| **AI** | Arabic assistant (Claude or Gemini, offline keyword router fallback) |
| **Tests** | 78 backend tests (`pytest`) |

## Screens (18)

Dashboard · POS (sales **+ returns + cash-desk shifts**) · Inventory (batches, expiry, **shelf places**) · Purchasing (invoices, **receive goods**, AI reorder drafts) · Stock Transfers · Customers (**account statements**, credit control) · Vendors · Employees (**PMP / development plans**) · Tasks (**auto weekly ops checklist**) · Accounting (ledger, trial balance, **manual journal**) · Reports (daily, sales, **P&L**, **by customer**, by cashier, stock & expiry, productivity) · Alerts (expiry / low stock) · Clinical drug advisory · AI Assistant · Settings · Login

## Quick start

### Option A — One click, no Docker (recommended for the pharmacy PC)

Requires Python 3.11+ and Node.js 18+ installed once.

- **Windows:** double-click `deploy/ProCare-Autostart-Install.bat` **once**. It puts a **ProCare AI icon on the Desktop** (one click opens the system) and makes the server **start automatically with Windows and stay always on**.
- **Linux / WSL / macOS:** `./deploy/procare-local.sh` — for boot autostart install `deploy/procare-local.service` (instructions inside the file).

First run installs dependencies and builds the UI, then every launch starts the backend + frontend and opens **http://localhost:3000**. Data lives in a local SQLite file until you point it at SQL Server.

### Option B — Docker (full production stack with SQL Server)

```bash
docker compose up -d --build     # UI on :3000, API on :7000, SQL Server on :1433
```

`deploy/procare.sh` is the control center (start/stop/update/logs/health). Put a Cloudflare `TUNNEL_TOKEN` in `.env` to publish it on the internet.

### Option C — Development

```bash
cd src/backend  && pip install -r requirements.txt && python run.py   # API :8000
cd src/frontend && npm install && npm run dev                          # UI  :3000
```

## Logins

Real staff accounts are created automatically at startup (initial password must be changed on first login — roster in `src/backend/app/db/migrate.py`):

| Role | What they can do |
|---|---|
| **CEO** | Everything — accounting, employees, salaries, insights |
| **Manager** | Branch-scoped operations + insights, no salaries |
| **Assistant** | POS and inventory |

A demo `admin` account is seeded for development — **disable it in production**.

## Install as an app

ProCare is a PWA: open it in Chrome/Edge (desktop or Android) or Safari (iOS) over HTTPS and choose **Install / Add to Home Screen**. It gets the ProCare icon, its own window, app shortcuts (POS / Inventory / Reports) and an offline shell. Live data is never cached.

## Architecture

```
Browser ──► Next.js (UI, :3000) ──/api proxy──► FastAPI (:8000/:7000) ──► ProCare DB (SQL Server / SQLite)
                                                      │  read-only ETL (Phase 1–2 only)
                                                      └─► eStock `stock` DB  +  Titan/Drug-Eye (clinical)
```

- **eStock is never written to** — a read-only login mirrors it on a timer until cut-over (mirror → parallel → replace; see [`docs/06-roadmap.md`](docs/06-roadmap.md)).
- Every hot path eStock kept locked in its `.exe` is re-implemented as tested, atomic service code: FEFO stock deduction, credit-limit checks, sale/return invoices, cash-desk shifts, transfers. Stock can never go negative, expired stock can't be sold, and every movement is audited.
- Clinical / interaction output is **advisory** — shown to the pharmacist, never silently blocks a sale.

## Repository map

| Path | Contents |
|---|---|
| `src/backend/` | FastAPI app — API routes, services (POS, returns, cash desk, purchasing, accounting, tasks, PMP, AI, clinical, ETL/sync), models, 78 tests |
| `src/frontend/` | Next.js app — 18 screens, bilingual i18n, PWA manifest + service worker |
| `deploy/` | Local launchers (no Docker), Docker control center, Dockerfiles, Cloudflare Tunnel |
| `docs/` | Architecture, eStock database reference, roadmap, data-quality rules, multi-branch model |
| `sql/` | ProCare clean schema, stored procedures, ready dashboard queries |
| `config/` | Connection template (`connections.example.json` — real credentials are git-ignored) |

## Security

- This repo is **private** — it documents internal topology and schema.
- **No credentials are committed.** Copy `config/connections.example.json` → `config/connections.json` (git-ignored) and use a **dedicated read-only** SQL login for the eStock mirror.
- Full non-negotiable guardrails: [`docs/01-architecture.md`](docs/01-architecture.md).

## License & ownership

Proprietary — built for **Procare Pharmacies** (Main الرئيسي + Elsanta السنتا). All rights reserved.
