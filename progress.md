# Progress Log (B.L.A.S.T.)

## 2026-07-10 → 07-11 · Phase 0 (merged)
- 7 feature areas built, tested, merged to main (PRs #13–#15): Windows 500 fix,
  LLM registry, WhatsApp automation, substitutions+transfers, prescriptions
  flow, daily ops tasks, dashboard drill-down, eStock connector script.
- pytest suite green; `next build` clean at merge time.
- CLAUDE.md merged with operating charter (owner-approved, conflict resolved
  with --theirs on the pharmacy PC).

## 2026-07-11 · Phase 1 (in flight)
- Owner feedback after first real use: search weak (wants prefix suggestions),
  drill-down "not working" on pharmacy PC, and جرد screens missing (full count,
  periodic count, item adjustment) — wants eStock-style screens with reports.
- DONE (uncommitted, on claude/arabic-display-data-sync-ukdieq):
  - Prefix-first search ranking in `services/inventory.py::list_products`.
  - POS: Enter-to-add-top-match + live match-count hint.
  - Models `StockCount`/`StockCountLine` appended to `db/models.py`.
  - `services/stocktaking.py` (create/list/get/record/post/cancel/top_movers).
  - `api/stocktaking.py` + registration in `api/routes.py`.
- Blueprint approved (owner said continue; recommended defaults adopted:
  table-entry count sheet, manager/CEO-only posting, fail-soft keys).
- ERROR + FIX (self-annealing): test_sync failed — the eStock mirror wipes
  products/stock_batches every cycle, and جرد FKs onto them blocked the wipe
  and would lose history in production. Fix: no FKs from count lines onto
  mirror-wiped tables; snapshot name_ar; outer-join sheet; posting skips
  vanished batches. Rule recorded in findings.md.
- Tests: 160/160 pass (5 new جرد tests incl. API flow + search ranking).
- Frontend: /stocktaking page (sessions → count sheet → variance → post),
  nav + 30 i18n keys (AR/EN); `next build` clean.
- Runtime smoke test: health ok · insight payload ok · Arabic prefix search
  ("ف" → فاركولين/فلاجيل/فولتارين first) · periodic جرد created 47 lines.
- Drill-down verdict: backend + UI fine in this build — pharmacy PC needs
  `git pull` + `npm run build` (stale build), not a code fix.

## 2026-07-11 (later) · Phase 2 — eStock parity round 2 (owner feedback)
- Owner: "مش زي eStock بالظبط" — named gaps: أصناف راكدة, cross-branch
  availability during sale, unit hierarchy (علبة/شريط/أمبول, كبرى/صغرى).
- BUILT:
  - Units: products.unit_big/unit_small/unit_factor + dialect-aware migration;
    ETL maps product_unit1/unit2/no2per1 (graceful when absent); demo + eStock
    test seeds carry units; POS per-line unit toggle (sell بالعلبة أو بالشريط,
    stock stays in big units, small qty = qty/factor); inventory shows الوحدة.
  - Stagnant (الراكدة): GET /inventory/stagnant?days= (on-hand, tied-up value,
    last sale, idle days + totals); inventory "الراكد فقط" view; جرد الراكدة
    scope on count creation.
  - Cross-branch: list_products?branch_id= adds other_branches per product;
    POS out-of-stock rows show "متوفر في <فرع>: <كمية>".
- ERROR + FIX (self-annealing #2): full suite exposed pre-existing prod bug —
  branch-scoped sync wipe FK-failed on pending transfer requests (NULL-batch
  lines). Fixed in etl._wipe_branch_rows (delete lines by parent transfer too).
- Tests: 170/170 pass (5 new in test_units_stagnant.py). next build clean.

## 2026-07-11 (night) · Phase 3 — round 3 (owner's full eStock list)
- Surveyed first: treasury/cashdesk/performance/accounting/parties largely
  cover الخزينة والدرج وكشوف الحساب والأداء السنوي — did NOT rebuild.
- BUILT: backups (auto+manual+pre-wipe), product classification + add-product
  + screen filters, POS invoice profit, كشكول النواقص بأولوية الشراء +
  transfer-first + consolidated 80% order, vendor statement/avg-discount/pay,
  grouped رئيسي/فرعي nav, Settings backup card.
- Tests: 174/174 (4 new in test_estock_parity3.py). next build clean.
- Honest gaps queued in task_plan Phase 3 "Next".

## 2026-07-11 (late) · Phase 4 — round 4 (finish owner's list)
- BUILT the 4 queued gaps: two-phase transfer (ship+receive with expiry/qty
  confirm), vendor statement+pay UI, customer 360 screen (+address column,
  migration, seed), chart of accounts tab.
- ERROR + FIX (self-annealing #3): parties.customer_profile used func without
  importing it — NameError. Added `func` to the sqlalchemy import. Caught by
  test_estock_parity4.
- Tests: 181/181 (7 new across test_transfer_receive.py + test_estock_parity4.py).
  next build clean.

## 2026-07-18 · eStock mirror end-to-end (flaky-WAN resilience + KPI fix)
- Context: elsanta (WAN) full mirror always died at ~6 min (10054 mid-pull of
  the 313K-row Sales_details); mashala (LAN) mirrored fine. Decimal/WAL fixes
  from ba4fae5 verified intact (etl._str, base.py WAL+busy_timeout).
- BUILT (branch fix/sqlserver-compat-and-operations-center):
  - etl.py: `_ResilientSource` (eager fetch inside retry; reconnect + engine
    dispose on 10054/08S01; 3 attempts, backoff) + `_iter_rows` key-range
    chunking (SYNC_CHUNK_ROWS, default 20K) wired into _load_sales and
    _load_purchases (headers + details). branch_scoped soft-fail per source
    preserved in sync.run_once.
  - dashboard.py: kpis now include `bills_month` (count) alongside
    `sales_month` (revenue); frontend labels: "إيراد الشهر" + bill-count sub,
    i18n keys ar/en.
- Tests: 192/192 pass (3 new in test_sync.py: comm-error classification,
  flaky-WAN retry completes with identical counts, exhausted retries soft-fail
  per source). Live elsanta verified: all big tables carry sales_id/purchase_id
  chunk keys; Branches_back_sales_* absent (skipped).
