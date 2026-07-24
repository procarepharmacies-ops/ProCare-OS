# ProCare OS — Task Plan (B.L.A.S.T.)

> Working memory: phases, goals, checklists. `CLAUDE.md` is the constitution;
> `findings.md` holds research; `progress.md` holds the run log.

## North Star
eStock-parity pharmacy operating system: the pharmacy runs its whole day
(sales, inventory, جرد, prescriptions, approvals, reports) from ProCare on the
pharmacy Windows PC, continuously mirroring the real eStock database, fully
bilingual (Arabic RTL first).

---

## Phase 0 — Foundation ✅ (merged to main, PRs #13–#15)
- [x] Windows 500 fix (safe seed + optional dotenv)
- [x] Multi-provider LLM registry (anthropic/gemini/ollama/claude-cli, fail-soft)
- [x] WhatsApp automation (invoices, returns, manager alerts)
- [x] Out-of-stock substitution → transfer request → approval workflow
- [x] Prescription capture → review → POS sale
- [x] Professional daily ops tasks (priority/category/auto-assign)
- [x] Dashboard drill-down (product insight modal, clickable rows)
- [x] eStock connector batch script (`deploy/ProCare-Connect-eStock.bat`)

## Phase 1 — eStock parity: الجرد + search (BUILT — pending PR + pharmacy-PC verify)
**B — Blueprint**
- [x] Data schema for stocktaking defined (see CLAUDE.md → Data Schemas)
- [x] Discovery answers confirmed by owner (defaults approved via continue)
- [x] Blueprint approved

**A — Architect**
- [x] `stock_counts` + `stock_count_lines` models (create_all-safe, no column migrations needed)
- [x] Service `services/stocktaking.py`: create (full/periodic/partial), count sheet,
      record counts, post adjustments (atomic, audit trail), cancel, variance report,
      top-movers scope for periodic counts
- [x] API `api/stocktaking.py` registered under `/api/stocktaking`
- [x] Search: prefix-first ranking in `inventory.list_products` (one letter → all
      products starting with it, AR/EN/code, then contains-matches)
- [x] POS: Enter adds top match to cart; match-count hint under search box
- [x] Tests: `test_stocktaking.py` (create→count→post→stock adjusted; idempotency;
      closed-session guard; variance math), search-ranking test
- [x] Frontend: `/stocktaking` page (sessions list, count sheet, variance report,
      post/cancel), nav entry, i18n keys (AR/EN)
- [x] Verify dashboard second-click drill-down end-to-end (works in this build;
      pharmacy PC needs pull + rebuild)

**S — Stylize**
- [x] Count sheet printable (window.print on the sheet view) (A4, RTL) like eStock's count report
- [x] Variance report totals styled (shortage red / overage green)

**T — Trigger**
- [x] pytest green (160/160) + `next build` clean
- [x] Commit per feature, push branch, PR to main (PR #22, 2026-07-19)
- [ ] Owner pulls on pharmacy PC, restarts, verifies with real data

## Phase 2 — eStock parity round 2 (BUILT — same PR #17)
- [x] Units وحدة كبرى/صغرى: model + migration + ETL + POS unit selling + inventory display
- [x] Stagnant items الأصناف الراكدة: report endpoint + inventory view + جرد scope
- [x] Cross-branch availability in POS (out-of-stock rows show other branch's stock)
- [x] fix: branch-scoped sync wipe vs pending transfer requests (NULL-batch lines)

## Phase 3 — eStock parity round 3 (owner's full list, 2026-07-11)
**BUILT this round:**
- [x] P0 Backups: service (SQLite copy / SQL Server BACKUP), auto on startup (24h)
      + before any full sync wipe (6h throttle) + POST /api/backup + Settings UI
- [x] P1 Product classification: dosage_form/is_otc/uses columns + migration,
      filters on items screen (form/OTC/place/price-sort) + إضافة صنف جديد form
- [x] P2 POS invoice profit (مكسب الفاتورة) — manager/CEO only
- [x] P3 كشكول النواقص وخطة الشراء: priority (رصيد صفر ← طلب عميل ← تحت الحد),
      transfer-first rule with حوّل الآن button, consolidated multi-branch order
      under the 80% budget (GET /purchasing/plan, /plan/consolidated)
- [x] P5 Vendor account: متوسط الخصم في التفاصيل, كشف حساب مورد (bills+payments,
      running balance), صرف لمورد from branch treasury (atomic, balance drops)
- [x] P6 Grouped رئيسي/فرعي sidebar (6 sections)

**Already existed (verified, no rebuild):** treasury vouchers صرف/توريد + تحويل
نقدي بين الفروع + أرصدة الفروع; تقفيل درج الكاشير (cash shifts); كشف حساب عميل;
أداء الفروع بالسنوات (performance.overview); ميزان مراجعة + قائمة دخل
(accounting); قاعدة 80% (autopurchase.daily_budget).

## Phase 4 — round 4 (BUILT — same PR #17)
- [x] P4 Two-phase transfer: request → ship (in_transit, stock leaves source) →
      receive with per-line expiry+qty confirm (stock enters destination; short
      receipt = shrinkage); receive task for destination manager; UI review modal
- [x] Vendor page UI: avg discount, كشف حساب (statement), صرف/سداد form
- [x] Customer 360 screen (👤 الملف): points+redeem, editable address, WhatsApp
      message, medicines-they-take, full purchase history; customers.address
      column + migration + seed; GET /customers/{id}/profile, POST /customers/{id}
- [x] Chart of accounts (شجرة الحسابات) tab: grouped by type with resolved
      customer/vendor/branch names, collapsible, balanced check; GET /accounting/chart

## Phase 5 — eStock mirror end-to-end (2026-07-18, branch fix/sqlserver-compat-…)
- [x] Verify FIX A/B/C from ba4fae5 intact (etl._str Decimal coercion; SQLite
      WAL+busy_timeout; .gitignore DirectX)
- [x] Flaky-WAN resilience: `_ResilientSource` (eager fetch in retry boundary,
      reconnect+dispose on 10054/08S01, 3 attempts) + `_iter_rows` key-range
      chunking (SYNC_CHUNK_ROWS default 20K) in _load_sales/_load_purchases
- [x] Dashboard KPI: bills_month returned; UI "إيراد الشهر" + bill-count sub
- [x] Employee mirror: eStock Employee → ProCare employees (permission flags
      1:1, username match, plaintext passwords NEVER imported, roster
      password/role untouched) — cashier attribution now covers all cashiers
- [x] Elsanta full mirror — via backup route, not WAN pull: hourly .bak found
      at F:\backup on the server, pulled 843MB over SQL (chunked OPENROWSET),
      restored locally, filled via etl.mirror in 21 min. ALL counts reconciled
      exactly (sales 412,047 = 158,100 + 253,947 branch-sales; purchases
      37,793; skips = source's zero-qty lines only). full_synced_at recorded
      → WAN cycles now incremental. (2026-07-20)

## Phase 6 — eStock domain completion (blueprint from CLAUDE_CODE_ESTOCK_STRUCTURE.md)
- [~] Accounting mirror: Account_Tree → chart accounts (chart_of_accounts
      exists); Gedo_Financial journal → ledger_entries (LedgerEntry kept — sale/
      return/depot postings already mirror in). DONE this round: **كشف حساب
      account statement** (opening balance + running balance + closing per
      account) and **Tuning_accounts تسويات named reasons** (bilingual reason
      catalog, `ledger_entries.reason_code`, adjustments tagged `ref_type=
      'adjust'`, per-reason adjustments report). REMAINING: mirror the raw
      Gedo_Financial journal rows verbatim (needs live eStock column audit —
      "column audit pending" in etl.py). (2026-07-21)
- [x] Shareholders: company_Owner + Gedo_Dividends_paied — `Shareholder` +
      `DividendPayment` models, ETL `_load_shareholders` (upsert by source id,
      graceful-absent, skips deleted owners + orphan dividends), `services/
      shareholders.py` (register w/ share_pct + dividend totals; per-owner
      annual history), `GET /api/shareholders[/{id}]` (CEO), `/shareholders`
      screen. Columns from docs/CLAUDE_CODE_ESTOCK_STRUCTURE.md §3. 7 tests.
      (2026-07-21)
- [x] Audit/change history: `product_changes` price/min-stock log (new model +
      `inventory.update_product_pricing` logs who/from/to/when),
      `stock_changes` over StockMovement (Product_amount_Change), and login
      history over AuthEvent (user_login). `GET /api/audit/product-changes`
      + `/stock-changes` (+ existing `/auth-events`); `POST /inventory/
      products/{id}/pricing`; `/history` screen (3 tabs). ProductChange added
      to etl `_WIPE_ORDER` (FK-safe full sync). 7 tests. (2026-07-21)
      [Mirroring the raw eStock change tables verbatim still needs their
      column audit; ProCare-side logging is live now.]
- [ ] Derived alarms: cheque due (Checks.ch_valid_date), below-cost
      (sell_price < buy_price), News_bar ticker; expiry/low-stock already exist
- [x] Payroll depth: `Employee_salary` mirrored → `payroll_records` (base,
      commission+over, deduction+absence, advance, net recomputed). ETL
      `_load_payroll` resolves emp_id→username→ProCare employee, upserts by
      salary_id, graceful-absent. `GET /api/employees/{id}/payroll` (CEO) +
      payroll panel (base/commission/deductions/advances/net + monthly history)
      on the employees screen. Columns from CLAUDE_CODE_ESTOCK_STRUCTURE.md §2.
      5 tests. NOTE: owner's docs/ESTOCK_SCHEMA_AND_MIRROR_TASK.md was NOT in
      the repo (local-only) — built from the committed structure doc. (2026-07-21)
- [x] Salary advances ledger: `Employee_cash_advance` → `salary_advances`
      (own sub-table). ETL `_load_salary_advances` (shared emp_id→ProCare
      resolver, upsert by cash_advance_id, graceful-absent). Advances ledger +
      total added to the payroll panel. 2 tests. (2026-07-21)
- [ ] EMP_CONTROL full matrix mapping (beyond the Employee-row flags)
- [ ] Jobs master mirror + employee.job_id linkage

### eStock tutorial feature-map gaps (from owner's illustrated report, 2026-07-20)
- [x] Item sales-movement report (تقرير حركة مبيعات صنف في فترة): per-day
      opening/in/out/returns/adjust/closing for one item; reconciles to live
      on-hand; CSV/Excel/print; `/reports-item` screen. Verified live (Augmentin
      1g: opening 13.5 → closing 2 == on-hand). 4 tests.
- [x] Employee incentive builder by active ingredient (CEO vision): group by
      scientific_name, rank top 2-3 brands per molecule by margin/margin%/
      profit-volume (live toggle), tick + set points, bulk apply → incentive
      list; "حوافزي هذا الشهر" panel on Operations for the logged-in employee.
      Engine (accrue/clawback/leaderboard) already existed + sync-safe; built
      the missing UI. CAVEAT: scientific_name 16% populated + some mis-tagged
      in source → needs sanity check / Titan enrichment later.
- [x] Sales-rep commission calculator (حاسبة عمولة مندوب البيع): per-rep NET
      sales × % (per-rep overrides), preview + post + void. `commission_runs`/
      `commission_run_lines` (idempotent `ensure_commission_tables`);
      `services/commissions.py` (net = sales − returns in one dialect-portable
      `case` scan, NULL-cashier excluded, post recomputes live + atomic, void
      keeps audit row); `/api/commissions/*` (CEO/manager); `/commissions`
      screen (date range + rate + presets, editable per-rep rate, runs list +
      detail/void). 9 tests. Full suite 317 passed. (2026-07-21)
- [x] News ticker / notification center: surface expiry/low-stock/shortage
      events (News_bar/Flag parity). Live-computed feed grouped by category
      (الصلاحية/نواقص المخزون/كشكول النواقص) with stable per-event keys +
      persistent dismissal (`notification_dismissals`, respects "deleted" like
      News_bar). `/api/notifications` (center), `/ticker` (ribbon), `/dismiss`.
      `/notifications` screen + a topbar ticker (bell + unread badge + top
      headline, 60s refresh, fail-soft) on every page. 5 tests. (2026-07-21)
- [~] Cheque-due alert (Checks.ch_valid_date): DEFERRED — both branch servers
      have ZERO rows in `Checks` (pharmacy doesn't use the cheque module), so
      the alert would run against empty data. Build only if they start issuing
      cheques; the mirror + alert can be added then.

### From CLAUDE_CODE_ESTOCK_FEATURES.md (behavioral parity)
- [x] POS auto-insert on unmet qty after FEFO allocation (sell what's
      available, log the rest): `create_sale(allow_partial=True)` caps each
      line to sellable qty, sells it FEFO, and auto-inserts the unmet remainder
      as an open `ShortageItem` (atomic). Default off — normal sales stay
      all-or-nothing. POS toggle + response echoes filled lines. 4 tests.
      (2026-07-21) [Mirroring the raw Shortcoming/Branches_shortcoming HISTORY
      is separate and still needs the eStock table audit.]
- [x] Notification center + ribbon: News_bar feed (respect deleted) +
      Flag categories; posts expiry/low-stock/shortage events there. (Built
      with the news-ticker item above — categories are inventory-focused
      expiry/low_stock/shortage; the POS/treasury/bank/expense/supplier Flag
      buckets can be added as those event sources land.)
- [x] F2 branch-stock popup at POS (binds F2 → modal of the top match's
      on-hand at this branch + other_branches; Esc closes). (2026-07-21)
- [x] Visible hotkey map strip at POS (Enter/F2/Esc chips under the search;
      grows as more keys are wired). (2026-07-21)
- [x] Permissions discovery screen: `services/permissions.py` + `GET
      /api/permissions/me` (resolves employee from Bearer token, else
      ?employee_id) + `/permissions` screen — EMP_CONTROL flag matrix ON/OFF
      with bilingual descriptions, max-discount limit, and the role-access
      superset (assistant ⊂ manager ⊂ ceo). 7 tests. (2026-07-21)

## Phase 7 — production hardening + POS depth (owner review 2026-07-23)
Owner is deploying on the Elsanta SQL Server 2008 (co-hosting ProCare's own DB)
and reviewed against real eStock usage. Three PRs, executed 3 → 1 → 2.

- [x] **PR 3 — SQL Server 2008 production readiness** (this branch):
      * Fixed 8 hardcoded `ALTER TABLE … ADD COLUMN` in migrate.py → dialect-
        aware `ADD`/`ADD COLUMN` (would have failed on SQL Server).
      * `db/base.py`: `IS_MSSQL` + `fast_executemany=True` for the bulk mirror.
      * `sql/performance-analysis.sql`: removed DATEFROMPARTS + LAG (2012+) →
        2008-safe literal cast + self-join.
      * CLAUDE.md: SQL Server 2008 guard-rail block (no `.offset()` / TRIM /
        LENGTH / NULLS LAST / DATEFROMPARTS / LAG; dialect-aware column adds).
      * `deploy/SQL-SERVER-2008-ELSANTA.md`: full co-host deployment guide
        (edition check, ProCare DB + read-only eStock login, restore-from-.bak
        first sync, incremental cutover, watchdog with REQUIRE_SQLSERVER=1).
      * 359 tests green (no regressions). (2026-07-23)
- [x] **PR 1 — POS invoice depth** (1a/1b/1c all merged):
  - [x] **PR 1a — invoice line details**: `Sale.note` (col+migration, threads to
        receipt); manual batch pick (`SaleLineInput.batch_id`/`LineIn.batch_id`,
        `deduct_stock_fefo(pin_batch_id=)` pinned-first-then-spill-FEFO, bad/
        expired pin → `bad_batch`); `nearest_expiry` on product list; POS batch
        picker with "older batch exists" reminder + expiry chips; receipt
        print-options (dosage/uses line, profit gated to mgr/ceo) + note printed;
        `sale_detail` gains note+dosage+uses. 8 tests. (2026-07-23)
  - [x] **PR 1b — hold/park invoice**: `HeldInvoice` (cart JSON, expires_at) +
        `ensure_held_invoice_table`; `services/held.py` (hold — no stock/credit
        touch; list w/ lazy expired-purge; resume re-resolves prices + flags
        missing/price_changed; discard idempotent); `/api/sales/hold|held|
        held/{id}/resume|discard`; `HOLD_EXPIRE_DAYS` (default 3); POS Hold
        button + held-drawer (resume re-prices to current). 6 tests. (2026-07-23)
  - [x] **PR 1c — per-line purchase discount**: `PurchaseLine.disc_money` +
        `ensure_purchase_line_discount_column`; `create_purchase` validates
        (0..line value) + folds line discounts into invoice total_discount so
        net = gross − total_discount + tax; `PurchaseLineIn.disc_money`;
        purchase detail exposes per-line disc_money + total_net; receive-goods
        UI discount column. 2 tests. (2026-07-23) — POS cluster (PR1) complete.
- [~] **PR 2 — coverage**:
  - [x] **PR 2a — schema-dump / coverage tool**: `etl.COVERED_SOURCE_TABLES`
        (the 22 source tables the ETL reads) + `tools/estock_schema_dump.py`
        (READ-ONLY, dialect-agnostic via SQLAlchemy Inspector — SQL 2008 + SQLite):
        dumps every table+columns(+optional COUNT), flags the coverage gap, writes
        docs/estock-schema-dump.md + .json. Owner runs once on Elsanta → commit →
        real column data for the mirrors + closes the ~11 undocumented-tables blind
        spot. 3 tests. (2026-07-23)
  - [ ] **PR 2b — high-value mirrors** (needs the dump's confirmed columns):
        Branches_Product_Amount (per-branch stock), Cash_disk_close, Branch_order_*;
        then Gedo_* GL verbatim.
      HONEST BASELINE: ETL reads 22 source tables (not 48 — that's ProCare's own
      table count); ~25 uncovered tables are empty/temp/config; Employee_daily_time
      (2.8M) deferred.

## Backlog (not started)
- [ ] Purchase entry extra fields (تسوية/خصم نقدي) — purchases come from eStock sync
- [ ] Barcode-scanner count sheet; small-unit price override; Gemini/ollama keys

---

## Operations (P0) — watchdog · digest · monitoring ✅ (branch claude/operations-watchdog-digest-monitoring-mn5kxa)
- [x] Watchdog `deploy/procare-watchdog.{sh,bat}` — /api/health poll, 3-strike
      restart (via `procare.sh restart`), 200-but-not-sqlserver guard, OOM check,
      `--once` mode, in-process 5-min `SELECT 1` self-ping job.
- [x] 8am CEO digest — `dashboard.ceo_digest()` + `whatsapp.ceo_digest_message()`
      + `scheduler._run_ceo_digest` on a timezone-aware (`BRANCH_TIMEZONE`) 08:00
      cron; reuses extracted `_revenue_between` + `top_products(start,end)`.
- [x] Disk + DB-size monitor — `services/db_health.py` (pure `evaluate` grader,
      `sys.database_files` size, `shutil.disk_usage`, `ping`), hourly
      `_run_db_health` (alerts only on severity rise), `GET /api/automation/db-health`.
- [x] Config `BRANCH_TIMEZONE`; dep `tzdata`; tests test_db_health.py (11) +
      test_ceo_digest.py (5) green; DEPLOYMENT.md watchdog section.
- [x] FOLLOW-UP (fixed): forecast + decision-card latent bugs.
      * forecast.compute_nightly_forecasts deleted today's rows by the BUSINESS
        clock (common.today()) while inserts stamp date.today() — mismatch left
        the prior run's rows, so the re-insert tripped the (product,branch,date)
        UNIQUE constraint. Fixed the delete to use date.today() (matches inserts
        + the tests). Also fixed test_forecast_demand_with_history's schema drift
        (string batch_id into an int PK; Sale(total=…) → total_net; SaleLine
        missing buy_price/total_sell). Full suite now 308 passed / 0 failed.
      * scheduler._alert_job_failure was referenced in _run_decision_card_
        generation's error path but never defined (latent NameError) — added a
        fail-soft helper (log + self-gating whatsapp.notify_manager).
