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
- [ ] Shareholders: company_Owner + Gedo_Dividends_paied (new model + screen)
- [ ] Audit/change history: Product_Changes (price log), Product_amount_Change
      (stock log), user_login (session audit) — surface as change-history screen
- [ ] Derived alarms: cheque due (Checks.ch_valid_date), below-cost
      (sell_price < buy_price), News_bar ticker; expiry/low-stock already exist
- [ ] Payroll depth: Employee_salary/cash_advance/commission/deduction tables
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
- [ ] News ticker / notification center: surface expiry/low-stock/shortage
      events (News_bar/Flag parity).
- [~] Cheque-due alert (Checks.ch_valid_date): DEFERRED — both branch servers
      have ZERO rows in `Checks` (pharmacy doesn't use the cheque module), so
      the alert would run against empty data. Build only if they start issuing
      cheques; the mirror + alert can be added then.

### From CLAUDE_CODE_ESTOCK_FEATURES.md (behavioral parity)
- [ ] Mirror `Shortcoming`/`Branches_shortcoming` history into كشكول النواقص
      (ProCare ShortageItem screen already exists); POS auto-insert on unmet
      qty after FEFO allocation (sell what's available, log the rest)
- [ ] Notification center + ribbon: News_bar feed (respect deleted) +
      Flag categories (نقطة البيع/الخزينة/البنك/مصروفات/مورد); post
      expiry/low-stock/shortage events there
- [ ] F2 branch-stock popup at POS (cross-branch data already in
      list_products.other_branches — bind the hotkey + modal)
- [ ] Visible hotkey map strip at POS (search/F2/discount/customer/hold/cash)
- [ ] Permissions discovery screen: all role flags for current user, ON/OFF —
      "hidden features" become visible

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
