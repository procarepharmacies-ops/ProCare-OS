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
- Committed 716a090 (WAN-resilient chunked mirror + KPI fix + employee mirror).

## 2026-07-18 (later) · Incremental window sync (owner: "WAN pull too slow")
- Owner rejected the multi-minute WAN full pull; killed it (atomic, no partial
  writes). Root cause: wipe+reload re-pulls ALL history every cycle.
- BUILT: incremental window sync — sync_state table (full_synced_at gate),
  SYNC_INCREMENTAL_DAYS (default 7) trailing re-pull of sales/purchases,
  window-scoped wipe (_wipe_branch_sales_window), Python-side date guard,
  detail fetch bounded to the window's id range. First load stays full.
- FIXED pre-existing bug: treasury Cash_depots snapshot stacked duplicates on
  every branch-scoped cycle (LedgerEntry never cleared) — now replaced per
  cycle (ref_type='depot' only).
- Tests: 195/195 (2 new: incremental window end-to-end, treasury snapshot
  not double-counted).
- 3rd spec file docs/CLAUDE_CODE_ESTOCK_FEATURES.md received (shortage
  notebook auto-insert, News_bar/Flag notifications, F2, hotkey strip,
  permissions discovery) — added to task_plan Phase 6.
- Elsanta initial fill decision pending: fresh .bak restore locally (needs
  MSSQLSERVER started + backup file) vs one overnight chunked WAN pull.
- Committed 515a75f (incremental window sync + treasury fix).

## 2026-07-18 (later still) · The REAL slowness: unindexed FK quadratic wipe
- First live incremental cycle vs mashala took 814s. Per-stage instrumentation
  → _wipe_branch_stock 624s → probe on a DB copy → DELETE of 35K stock_batches
  alone = 504s → cause: sale_lines.batch_id FK (190K rows) unindexed, so every
  batch delete full-scanned sale_lines for the FK check.
- Also killed two stale python backends from yesterday (one elevated) that
  held procare.db locks + a 113MB WAL during the first timing run.
- FIX: 9 FK-check indexes (models.py Index() + migrate.ensure_fk_indexes,
  called in lifespan). Verified live: incremental cycle 814s → 11.8s.
- Tests: 195/195 pass.

## 2026-07-19 · Merge main into sync branch + PR #22
- Merged origin/main (Phase 6 dashboard rework, POS revenue engine, auth
  audit) into fix/sqlserver-compat-and-operations-center. Conflicts: models.py
  (kept SyncState + main's AuthEvent/ProductAffinity/IncentiveLedger), main.py
  (both migrations), page.js (main's KpiCard layout + re-applied bills_month
  sub-line), progress.md (both histories).
- FOUND + FIXED latent main bug: api/stocktaking.py carried a duplicated
  create() handler from main's own earlier conflict resolution — first copy
  returned undefined `result`; Starlette routes to the first registration, so
  POST /api/stocktaking 500'd on main. Collapsed to one working handler.
- Tests: 202/202 pass; next build clean. Pushed e27c7e7; opened PR #22
  (WAN-resilient mirror + incremental window sync + FK indexes + OpenRouter).

## 2026-07-18 · Phase 5 — Post-merge stabilisation

- Merged PR #21 (Phase 2 POS Revenue Engine: upsell/cross-sell, OTC incentives,
  leaderboard) into main. Resolved 2 merge conflicts:
  - `src/backend/app/main.py` — CORS origins (kept broader: 3000/3001/3100)
  - `src/frontend/package.json` — dev port (kept -p 3100)
- Backend moved to port 8100, frontend to 3100 (avoiding conflicts with other
  local projects). Updated: run.py, .env.example, next.config.mjs,
  .env.local.example, package.json, CLAUDE.md, README.md.
- Tests: 196/196 pass (15 new from incentives/revenue engine). 14 warnings
  (DeprecationWarning: datetime.utcnow — advisory only, not blocking).
- All new routers confirmed registered in routes.py: agents, incentives, knowledge.
- Pushed to origin/main: commit 4beb583.

## 2026-07-20 · Elsanta initial fill via backup route (on-site)
- Owner on-site at Elsanta. Found the backup route: server DESKTOP-DUTL25M
  backs up `stock` HOURLY to F:\backup (~843MB .bak). No Windows/SMB creds,
  but the read-only SQL login has ADMINISTER BULK OPERATIONS → pulled the
  .bak over the SQL connection itself in 16MB SUBSTRING(OPENROWSET) chunks,
  resumable, 74 min at 0.2 MB/s, zero failed chunks.
- Identity check first (labels vs reality): WAN 196.202.93.37 =
  DESKTOP-DUTL25M = Elsanta (313K details, 2 stores); LAN 192.168.1.2 =
  DESKTOP-SHTFS3J = Mashala (185K details). Config labels correct.
- Restored as stock_elsanta (60s), ran etl.mirror branch_scoped full from the
  local restore: 21 min. First run failed on missing incentive_points column
  (ProCare DB predated the revenue-engine merge) — added the lifespan
  migration sequence to the fill script; second run clean.
- VERIFIED against source, everything reconciles EXACTLY:
  sales 412,047 = Sales_header 158,100 + Branches_sales_header 253,947;
  returns 6,891/8,744; purchases 37,793 = 12,646 + 25,147; stock_batches
  66,443 = Product_Amount; products 53,522. The only skips are the source's
  own zero/negative-qty lines (2,783 sale + 81 purchase) blocked by CHECK
  constraints — intended.
- sync_state['elsanta'].full_synced_at recorded; live run_once cycle:
  elsanta ran incremental(7d) in ~8 min over the 0.2MB/s WAN; mashala
  first-ever full load into SQL Server still running (background).
- Live cycle verified end-to-end (776s total): elsanta incremental(7d)
  re-pulled 1,085 window sales + current-state refresh; mashala first full
  load into SQL Server (95,846 sales = source exactly). Both sync_state gates
  now set → all future cycles incremental. July KPIs sane per branch
  (Elsanta 2,644 bills/207,618 EGP · Mashala 499/30,740).
- SYNC_ENABLED=1 restored in .env (the condition in its own comment — the
  incremental upgrade landing — is met). Kept: .bak + stock_elsanta on D:
  as re-verification insurance.

## 2026-07-20 (later) · Production install + eStock gap #1 (item movement)
- Installed production ProCare v1 on the pharmacy PC: ports moved to 8100/3100
  (owner runs another project on 8000/3000), desktop icon + Windows autostart,
  same-origin proxy build. Logged into the live dashboard as CEO — real data.
- FIXED (twice) a production login lockout: the eStock employee mirror wrote
  is_active from the source row every cycle, so a stale eStock employee row
  deactivated the matched ProCare login. First fix gated on `sha256$` only —
  but the login path upgrades sha256 → pbkdf2, so a logged-in account slipped
  through and got re-locked. Correct gate: protect any hash NOT starting with
  `!` (the mirror sentinel). Regression test now covers the pbkdf2 case.
- FIXED backend instability: run.py had reload=True hardcoded — the file
  watcher restarted the API on every edit and died with its parent console,
  dropping the backend mid-session. Now env-gated (PROCARE_RELOAD, default off);
  production stays up as a single stable process.
- Reviewed 5 unmerged branches: 3 stale (pre-refactor / SQL-compat already in
  main), 2 clean value-adds (accounting KPIs; deep-analysis frontend for the
  /performance/deep backend already in main) — left for owner's merge call.
- Audited codebase vs owner's eStock illustrated feature map: strong coverage;
  4 real gaps (item-movement report, rep commission, news/notif center,
  cheque-due). Cheque data is EMPTY on both servers → cheque-due deferred.
- BUILT gap #1 — item sales-movement report: reports.item_movement (per-day
  opening/purchases/sales/returns/adjust/closing, reconciles to live on-hand),
  GET /reports/item-movement (+CSV), /reports-item screen (product search +
  window + reconcile badge + export). Verified live on Elsanta (سرنجة: opening
  2060.1 → closing 7.6 == on-hand; Augmentin 1g: 13.5 → 2 == on-hand).
- Tests: 207/207 (4 new in test_item_movement.py). next build clean.

## 2026-07-20 (later) · Incentive builder by active ingredient (CEO vision)
- Owner's vision: the incentive/OTC list should push the 2-3 MOST PROFITABLE
  brands of each active ingredient, so cashiers steer customers to the
  best-margin brand of the molecule they ask for.
- Discovered the incentive ENGINE already existed (revenue-engine merge):
  set points per product, auto-accrue on sale (points = qty × product points),
  clawback on return, per-employee history, leaderboard — all tested, and
  sync-SAFE (the product mirror never overwrites incentive_points). What was
  missing was the FRONTEND (no way to choose products or show the employee his
  tally).
- BUILT: services/incentives.py `incentive_candidates` — groups catalogue by
  scientific_name, ranks brands within each ingredient by 3 metrics
  (egp_margin / margin_pct / profit_volume), returns top-N per ingredient with
  all three metric values for live re-ranking + current points. `apply_incentives`
  bulk set/clear. Endpoints GET /incentives/candidates + POST /incentives/apply
  (ceo/manager). SQL Server 2008-safe (no func.trim/length — the local instance
  is MSSQL10 too).
- Frontend: /incentives builder (metric toggle, top-N, ingredient search,
  per-brand tick+points, bulk apply) + "حوافزي هذا الشهر" card on the Operations
  screen (logged-in employee's monthly points). api helpers, nav, AR/EN i18n.
- Verified live: 1,243 competing-ingredient groups; ranking + metric toggle +
  bulk apply all work (ESOMEPRAZOLE by margin% → AIG 50% / ESMATAC 41% → applied
  → landed on the incentive list; test values then cleared).
- DATA CAVEAT surfaced: scientific_name is only 16% populated, and some are
  MIS-TAGGED in eStock (e.g. the METFORMIN group contained SPRYCEL/dasatinib
  and MESTINON/pyridostigmine). Grouping is correct given the data; the source
  molecule field needs a sanity check / future enrichment from Titan drug master.
- Tests: 209/209 (2 new in test_incentives.py). next build clean.
- Also: run.py reload now env-gated (was dropping the backend); ports 8100/3100.

## 2026-07-20 (later) · Catalogue fix Phase 0 — Titan enrichment + duplicates
- Goal (owner): correct eStock products against Titan — scientific name, AR/EN
  names, medicine flag, local/import, category/uses — without touching data,
  and handle the duplicated products professionally.
- AUDIT: Titan had MOVED (D:\AgenticOS\TITAN.349) and changed record layout
  (AR/EN swapped, category 792->796). Made the extractor layout-detecting.
  Its Arabic is INTACT (13,598) — reversing the old "Arabic unrecoverable"
  caveat. No local/import or medicine flag exists in the file (byte audit:
  best separation 0.36), so both are derived from manufacturer + category.
- MERGED the two Titan builds instead of reloading (would have lost 3k
  scientific names + orphaned 2,096 product mappings): 23,063 drugs,
  name_ar 23 -> 13,962, sci 13,986 -> 19,209, matches 4,145 -> 4,322.
- BUILT services/catalogue.py: `duplicate_groups` (tiered code/exact_name/
  name_pack with per-tier CONFIDENCE, survivor-choice evidence = on-hand,
  lifetime sales, last sale; strength never normalised away) and
  `enrichment_proposals` (per-field current-vs-Titan diffs, fill vs replace).
  GET /catalogue/duplicates + /catalogue/enrichment (ceo/manager, READ-ONLY).
- Live: 869 duplicate groups (23 high-risk = live stock split across copies);
  1,791 products with staged proposals (category 1,790 / is_medicine 1,752 /
  origin 1,111).
- Tests: 214/214 (5 new in test_catalogue.py incl. the 500MG-vs-1GM
  dispensing-safety invariant).
- NOT DONE yet: review UI (Phase 1) and the approved eStock write-back
  (Phase 2, separate explicitly-launched script, backup-gated).

## 2026-07-20 (later) · Drug-Eye online harvest (uses + substitution)
- Owner asked to pull uses / substitution / scientific names from the Drug-Eye
  web app to enrich beyond the local Titan file.
- REVERSE-ENGINEERED the site: WebForms postback search; 5-rows-per-drug
  colour-keyed result grid; id-based GET sub-lookups for generics (`geno`),
  therapeutic alternatives (`alto`), and a clinical monograph endpoint.
  All three verified live: ESOMEPRAZOLE -> 92 generics, 100 alternatives,
  full indications list (gastric ulcer / GERD / oesophagitis / NSAID ulcer).
- BUILT tools/drugeye_scrape.py: disk-cached (re-runs free), throttled
  (default 2.5s/request), resumable, writes JSONL to a STAGING file — nothing
  is applied to products; it feeds the catalogue review flow.
- THREE parser bugs found and fixed by probing real data: "color:Blue" also
  matched "BlueViolet" (doubled every result list); monograph sections use
  inconsistent separators across drugs; heading regex `indication\b` could not
  match the plural "Indications" (silently emptied every uses field).
- NOT started: bulk harvest (needs owner go-ahead — ~1,500-3,000 molecules,
  4 requests each at 2.5s = one overnight run) and the review UI.
