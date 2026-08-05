# Task for Claude Code — Implement eStock Mirror in ProCare-OS

You are working in `C:\Users\ahmed\ProCare-OS` (the ProCare-OS pharmacy app: FastAPI backend `src/backend`, Next.js frontend `src/frontend`). The repo is on branch `fix/sqlserver-compat-and-operations-center`. Your job: make the **eStock → ProCare read-only mirror** fully work, end-to-end, the way it was proven to work in the sibling project "ProCare System Intelligence" (`D:\procare_system_intelligence`, the eStock Web app). Below is everything that was discovered, fixed, and proven — implement accordingly and do NOT regress any of it.

---

## 1. What "mirroring eStock" means here

ProCare-OS is an **independent system of record**. eStock (the legacy ModernSoft pharmacy SQL Server) is a **read-only SOURCE** reached only by `app/services/etl.py` (Phase-1 mirror). ProCare NEVER writes to eStock. The mirror pulls live data from two branch SQL Servers configured in `config/connections.json` (git-ignored, do not commit):

- **elsanta** — WAN `196.202.93.37`, DB `stock`, eStock branch store_id 1 → ProCare branch `ELSANTA`
- **mashala** — LAN `192.168.1.2`, DB `stock`, eStock branch store_id 2 → ProCare branch `MASHALA`

The mirror maps eStock tables → ProCare tables (see `etl.MIRROR_PLAN`):
Products→products, Customer→customers, Vendor→vendors, Product_Amount→stock_batches, Sales_header/Sales_details/Back_*/Branches_*→sales/sale_lines, Purchase_*→purchases/purchase_lines, Cash_depots→ledger_entries (treasury).

The frontend dashboard/reports read from ProCare's OWN DB (SQLite in dev, SQL Server in prod). So "mirroring" = getting eStock's data INTO ProCare's DB so the UI shows real pharmacy numbers.

---

## 2. CRITICAL: this environment reaches BOTH branches fine

Do NOT assume the old "procaredev can't reach elsanta" blocker applies. From this machine, BOTH sources connect and return live data (verified by direct `SELECT`):
- elsanta: 53,507 products, 157,935 Sales_header, 313,119 Sales_details, 253,706 Branches_sales_header, 12,631 Purchase_header
- mashala: 53,506 products, 95,768 Sales_header, 185,181 Sales_details, 707 Purchase_header, 87 Vendors

So connectivity is NOT the problem. The problems are (a) SQLite dev-mode crashes, (b) the flaky WAN dropping big pulls, and (c) a dashboard KPI mislabel.

---

## 3. Bugs ALREADY FIXED (do not break these)

### FIX A — `src/backend/app/services/etl.py` (Decimal crash, 0% mirroring on SQLite)
**Cause:** `_load_products` inserted `unit_big`/`unit_small` as raw `r.get(unit_big)` values. These arrive from pyodbc as `decimal.Decimal`. SQL Server binds `Decimal` natively (so prod never failed), but **SQLite's SQLAlchemy dialect cannot bind `Decimal` into the `String(50)` columns** → `type 'decimal.Decimal' is not supported` → the ENTIRE products load aborted → 0 rows mirrored in dev/CI.
**Fix applied:** added a `_str(value)` coercer (`None→None`, else `str(value)`) and used it for `unit_big`/`unit_small` in BOTH the create path (`m.Product(unit_big=_str(...))`) and the update path (`bindparam("b_unit_big": _str(...))`). All OTHER numeric columns already go through `_num()`/`_price()`/`_as_date()`/`_as_dt()` — keep them.
**Verify:** after your changes, `sync.run_once()` must load products on SQLite without `Decimal` errors.

### FIX B — `src/backend/app/db/base.py` (SQLite "database is locked")
**Cause:** default SQLite (rollback-journal, single-writer) deadlocks when the lifespan seeding session + the background sync thread + concurrent HTTP requests share the file → `OperationalError: database is locked`.
**Fix applied:** on SQLite, the connect event now also runs `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`. Keep this. Do not remove the `connect_args={"check_same_thread": False}` for SQLite.

### FIX C — `.gitignore` (stray DirectX files)
Added `*.cab`, `APR2007_*/`, `DEC2006_*/`, `vcredist_*.exe`, `*.msi`, `DSETUP*.dll`, `dsetup*.dll` so Windows SDK installers don't get committed. Keep.

These three fixes are already committed & pushed on branch `fix/sqlserver-compat-and-operations-center` (commit `ba4fae5`). Rebase on top, don't revert.

---

## 4. KNOWN LIMITATION — elsanta WAN drops big pulls (10054)

The elsanta WAN is flaky. Small queries (e.g. reading 157,935 `Sales_header` rows) work. But the full `Sales_details` (313,119 rows) + `Branches_sales_header` (253,706) pull **drops the TCP connection at ~6 minutes** with `pyodbc.OperationalError 10054 — Communication link failure (TCP Provider: An existing connection was forcibly closed by the remote host)`.

**This is why a full elsanta mirror currently FAILS from this environment.** mashala (LAN) mirrors fully and fast (65s, 100,145 sales). elsanta does NOT complete.

**What to implement to fix this (the main ask):**
1. **Chunked / paginated fetching** in `etl._load_sales` (and `_load_purchases`): instead of `src.execute(text(f"SELECT * FROM {tbl}")).mappings().all()` (loads the whole 313K table into memory over a dying WAN), page by `sales_id` ranges (e.g. `WHERE sales_id BETWEEN ? AND ?` in batches of ~10K–20K) so each query is small enough to finish before the WAN drops it.
2. **Per-batch reconnect + retry**: on `10054`/communication-link-failure, close and recreate the source engine and re-run the failed batch (idempotent — `etl.mirror` matches by key, so re-inserting a batch is safe). Use a small retry budget (e.g. 3 attempts) with backoff.
3. **Keep `branch_scoped=True` semantics**: each source refreshes ONLY its own branches; the other branch's rows survive. (`run_once` already iterates sources and calls `etl.mirror(..., branch_scoped=True)`.)
4. **Do NOT block the pharmacy**: sync already runs in a background thread (soft-fail per source). Preserve that — a failing elsanta pull must NOT crash the app or block mashala.
5. Respect the data-quality rules already in `etl.py`: `sale_date = COALESCE(bill_date, insert_date)`, `back='Y' → is_return`, FEFO by `exp_date`, walk-in `customer_id=0 → NULL`.

Test the chunked loader against elsanta specifically (it's the one that breaks). A SQLite eStock-shaped fixture + `tests/test_sync.py` already exists — extend it or add a test that simulates a flaky source (raise 10054 mid-stream) and confirms the batch is retried and eventually completes.

---

## 5. DASHBOARD KPI MISLABEL (separate, also fix)

`app/services/dashboard.py` `summary()` computes `sales_month = func.sum(m.Sale.total_net)` (REVELATION = revenue) but the returned dict labels it `sales_month` and the UI shows it as if it were a **count of sales**. The actual July-2026 values (mashala-only, because elsanta isn't mirrored yet):
- `sales_month` = **26261.25** ← this is REVENUE, not a count
- real July bill COUNT = 422
- DB has 100,145 Sale rows total (all mashala)

The code computes the count too (`func.count()` at line 31) but **discards it** — `bills_month` is calculated then never returned. **Fix:** return `bills_month` (count) AND keep `sales_month` as revenue, and make the frontend label them distinctly (e.g. "إيراد الشهر" = revenue vs "فواتير الشهر" = bills). Do not present revenue as a sales count.

---

## 6. How to run / verify (from this environment)

```bash
cd src/backend
export PROCARE_DB_URL="sqlite:///$(pwd)/data/procare.db"   # dev SQLite mode
PYTHONPATH=. .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 --reload
# frontend:
cd src/frontend && npm run dev   # :3000
```
- Health: `GET /api/health` → `procare_db:"sqlite (dev)"`, `estock_source:true`.
- Trigger mirror: `curl -X POST http://localhost:8000/api/sync/run` OR `PYTHONPATH=. .venv/Scripts/python.exe -c "from app.services import sync; print(sync.run_once())"`.
- Per-source with WAN timeout: build the engine with `?timeout=600` connect arg (already used by the standalone `run_elsanta.py` script).

**Success criteria:**
1. `sync.run_once()` loads products on SQLite with NO `Decimal` error (FIX A intact).
2. mashala mirrors fully (already proven: 53,506 products, 95,768 sales, 184,854 sale_lines, 1,198 customers, 87 vendors).
3. **elsanta mirrors fully** via chunked retry despite the WAN 10054 drops (the new work).
4. `GET /api/dashboard/summary` returns `bills_month` (real count) separately from revenue; UI labels them correctly.
5. No `database is locked` under concurrent load (FIX B intact).
6. Direct branch check still passes: both `196.202.93.37` and `192.168.1.2` return live tables.

---

## 7. Coordination / repo policy (IMPORTANT)

- This repo's `CLAUDE.md` is explicit: **never push `main` directly — always PR, always test on a feature branch. Run `pytest app/tests/` before pushing.** Follow it.
- Hermes Agent is working in parallel on the SAME repo/branch. We both touch `etl.py`/`base.py`/`dashboard.py`. **Coordinate:** whoever merges last must rebase on the other's `main` changes and resolve conflicts. Your chunked-fetch change to `etl._load_sales` should apply cleanly on top of the existing `_str`/`_num` coercers — keep those.
- Do NOT commit `config/connections.json` (has live plaintext prod creds: `procare_reader`, `ahmedpharm22`, `ahmedibrahim`, `sa`). It is git-ignored. Recommend rotating those creds.
- Keep `data/` git-ignored (it is). The SQLite `procare.db` is local-only.

---

## 8. Reference numbers (verified this session)

| Source | Products | Sales_header | Sales_details | Branches_sales | Purchase_header |
|--------|---------|--------------|---------------|----------------|-----------------|
| elsanta (WAN) | 53,507 | 157,935 | 313,119 | 253,706 | 12,631 |
| mashala (LAN) | 53,506 | 95,768 | 185,181 | 0 | 707 |

mashala fully mirrored = 100,145 sales in ProCare DB. elsanta = 0 (WAN fails). Target after your fix: **both branches present**, consolidated dashboard reflects ~257K+ sales.

Write the code, add/extend the tests, verify against both live branches, and report what you changed. Do not mark done until elsanta actually mirrors through the flaky WAN via chunked retry.
