# ProCare OS — Standard Operating Procedures (SOP)
### دليل التشغيل المعياري لكل عملية

> Production deployment on **SQL Server** (`localhost` / database `ProCare`), 2
> branches (Elsanta السنطه + Mas-hala مسهله). Generated 2026-07-13 after a full
> operational check (67/78 endpoints passing — see §9).

---

## 0. System startup / shutdown — تشغيل وإيقاف النظام

**Start the whole stack (SQL Server backing):**
1. Ensure SQL Server is running (admin): `deploy/Start-SqlServer.bat` → *Run as administrator*, or `Start-Service MSSQLSERVER` in an elevated PowerShell.
2. Backend: from `src/backend`, run `python run.py` → serves `http://localhost:8000`.
   - Uses `config/connections.json` (SQL Server) automatically. **Do not** set `PROCARE_DB_URL` — that forces the SQLite dev file.
3. Frontend: from `src/frontend`, `npm run dev` → `http://localhost:3001` (proxies `/api` to :8000).
4. Verify: `GET /api/health` must return `{"status":"ok","procare_db":"sqlserver"}`.

**Health gate before opening the pharmacy each day:**
- `GET /api/health` → `status: ok`, `procare_db: sqlserver`.
- Dashboard loads in < 1s (`GET /api/dashboard/summary`).

**Windows gotcha (important):** `uvicorn --reload` can leave an orphaned worker
holding port 8000 with stale code; some backend `python.exe` even become
elevated and survive a normal kill. For a clean restart: `Get-Process python |
Stop-Process -Force` (elevate if "Access denied"), then `python run.py`.

**Shutdown:** stop the frontend, then the backend (Ctrl-C or kill python). SQL
Server can stay running.

---

## 1. Point of Sale (POS) — نقطة البيع

**Purpose:** ring up a sale, FEFO-picked, credit-checked, expiry-locked.

1. Open **نقطة البيع**; select branch.
2. Search item (one Arabic letter lists every product starting with it).
3. Add to cart in **big units**; the unit selector is display-only (stock is stored in big units, `unit_factor` converts small units).
4. Out-of-stock rows show **other-branch availability**; raise a transfer request if needed.
5. Credit sales over the customer limit require an authorised override (`can_sale_credit`).
6. Confirm → one atomic transaction writes the invoice, lines, stock movements (FEFO, oldest expiry first), and ledger.

**Invariant:** stock never goes negative; expired-only product cannot be sold.
FEFO ordering is now SQL-Server-safe (see §10, `fefo_order`).

---

## 2. Prescriptions — قارئ الروشتات

1. Open **قارئ الروشتات**; capture a photo (phone camera / PWA) or upload.
2. AI (Gemini 2.5-Flash) extracts drugs → **review** step; resolve each line to a catalogue product.
3. Approve → hand off to POS (`?rx=` seeds the cart). Status flows capture → review → dispensed.
4. Doctor prescribing habits accumulate under **doctor-habits**.

**Fail-soft:** if the AI key is missing the keyword router still runs; a WhatsApp/AI outage never blocks dispensing.

---

## 3. Operations Center — مركز العمليات  *(new)*

**Purpose:** run the day — daily tasks + staff performance in one screen (CEO/Manager).

1. Open **مركز العمليات**.
2. **Today's pulse:** open tasks, overdue, sales/bills today, low-stock, expiring, team active.
3. **Task board:** grouped Overdue / Today / Upcoming / Done. Each task shows assignee, priority, category. Click **إنجاز** to complete, **إعادة فتح** to reopen.
4. **Team performance (30d):** per-cashier bills, revenue, avg bill, peak hour.
5. **AI agents strip:** live online/offline for Hermes / Claude / Gemini / Antigravity (see §8).

Built on fast endpoints only, so it never hangs on heavy analytics.

---

## 4. Daily & weekly tasks — المهام اليومية

- Templates auto-create **once per day** and **once per ISO week** per branch (opening/closing, cold-chain check, expiry sweep, reorder review, weekly stocktake).
- Assign by role; complete from **المهام** or the Operations Center.
- Idempotent: re-running the generator never duplicates a day's tasks.

---

## 5. Inventory & Stocktaking — المخزون والجرد

**Inventory (المخزون):** search/filter by dosage form, OTC, scientific name, shelf location. On-hand is live available stock (positive, not expired).

**Stocktaking (الجرد):**
1. **جرد جديد** → choose type: full / periodic / partial (or scope `stagnant` = الأصناف الراكدة).
2. Enter counted quantities per batch; variance is computed live.
3. **Post** → sets each batch to its physical quantity (delta vs the LIVE amount at post time), writes an `adjust` stock movement per non-zero delta, atomic.

**Stagnant items:** `inventory/stagnant?days=90` lists on-hand items with no sale in N days → open a partial count scoped to them.

> Fixed 2026-07-13: the stocktaking list query used a SQLite-only `GROUP BY` and
> 500'd on SQL Server — now a dialect-portable subquery (§10).

---

## 6. Transfers, Shortages, Purchasing — التحويلات والنواقص والمشتريات

- **Transfers (التحويلات):** request → manager approve/reject → stock moves atomically (FEFO). Requested (NULL-batch) lines are honoured by the sync wipe rule.
- **Shortages (النواقص):** items below `min_stock`.
- **Purchasing (المشتريات):** auto-proposal / budget / drafts / consolidated plan (CEO/Manager).
  - ⚠ `purchasing/plan/consolidated` is a heavy query (>10s) — see §9.

---

## 7. Money & Reports — المال والتقارير

Treasury (balances/movements/transfers), Accounting (chart, ledger, P&L, trial balance — CEO), Audit (cash report), Reports (stock, batches, movements, valuation). All read-only.

> Fixed 2026-07-13: `reports/stock/batches` used `NULLS LAST` (invalid on SQL
> Server) — now portable FEFO ordering (§10).

---

## 8. AI agents — الوكلاء الأذكياء

The agents feature works; each agent's availability depends on its backing tool:

| Agent | الحالة | Needs to go online |
|-------|--------|--------------------|
| **Claude Code** | ✅ online | `claude` CLI installed (it is) |
| **Gemini** | ✅ online | `GEMINI_API_KEY` set (it is); non-sensitive tasks only |
| **Hermes Ops** (هيرمس) | ⚠ offline | a server responding on `HERMES_URL` (`:5000`). Ollama is installed but serves `:11434` and is a *different* thing (LLM provider, not the ops agent). |
| **Antigravity** (أنتي جرافيتي) | ⚠ offline | Google **Antigravity CLI** installed on PATH (`antigravity`). Not a code bug — install the CLI. |

**SOP:** dispatch only to agents showing **online/dispatchable**. Sensitive tasks
never go to Gemini (data leaves to Google). Offline agents fail-soft — they never
block the app.

---

## 9. Full operational check — نتيجة الفحص الشامل (2026-07-13)

**67 / 78 GET endpoints pass.** The 11 non-200 break down as:

**Expected (not failures) — require a query param / auth:**
`accounting/account-balance` (needs `account_type`), `cashdesk/current` (`branch_id`),
`dashboard/range` (dates), `knowledge/search` (`q`), `purchasing/plan` (`branch_id`),
`auth/me` (bearer token), `transfers/summary` (probe artifact).

**Real issues fixed this session:**
- `stocktaking` 500 → **fixed** (§10).
- `reports/stock/batches` 500 → **fixed** (§10).

**Known heavy queries (timeout > 10s) — optimization backlog:**
- `performance/overview` — runs 3× full 5-year scans (consolidated + per-branch) accumulating in Python.
- `performance/deep`
- `purchasing/plan/consolidated`

  *Mitigation:* the Operations Center avoids these; use `insights/productivity`
  (fast) for staff performance. Fix = push aggregation into SQL / add date-window
  indexes / cache.

---

## 10. Database & reliability invariants — ثوابت قاعدة البيانات

- **SQL Server only in production.** SQLite fallback triggers *only* when `connections.json` has no real credentials. The dev SQLite files were removed 2026-07-13.
- **RCSI enabled** (`READ_COMMITTED_SNAPSHOT ON`) so dashboard reads never block on a writer.
- **Connection pool:** `pool_pre_ping` + `pool_recycle=1800` so a dropped/KILLed SQL connection auto-recovers instead of `08S01`.
- **Dialect portability (this is the #1 source of SQL-Server-only bugs):**
  - Date part: use `sql_day(col)` (not SQLite `date()`).
  - "Today": use `today()` (live clock when eStock configured, demo anchor offline).
  - `GROUP BY`: SQL Server requires every non-aggregated selected column in the GROUP BY — aggregate in a subquery instead.
  - FEFO "NULLS LAST": use `common.fefo_order()` — `NULLS LAST` is a syntax error on SQL Server. **Never** write `.nulls_last()`.
- **Sync (eStock mirror) is OFF** (`SYNC_ENABLED=0`): the full wipe+reload holds
  table locks for minutes on 264k sales and cycles stack up. Data is already
  mirrored. Re-enable only after the watermark/CDC incremental (docs/06).

---

## 11. If something breaks — عند حدوث خطأ

1. **Logs first:** backend stdout / `.local-run/backend.log`; browser console (F12); `GET /api/sync/status`.
2. **A screen 500s:** check the traceback for a dialect error (`8120` GROUP BY, `102 near 'NULLS'`, `CAST`), apply the §10 pattern.
3. **A screen hangs:** check SQL Server blocking — an orphaned Python transaction holding locks. `KILL` the session (see project memory), then clean-restart the backend.
4. **Never hide errors:** log with context; alert via dashboard banner + WhatsApp if critical. Commit a fix, not a workaround; add a regression test.
