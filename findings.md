# Findings (B.L.A.S.T. research memory)

## Environment & delivery
- Owner runs ProCare on a Windows pharmacy PC at `C:\Users\ahmed\ProCare-OS`;
  develops via this cloud session + local Claude Code CLI. PowerShell is the
  default shell there — `&&` fails; use `;` or CMD. (2026-07-11)
- Windows file locks linger on `.local-run/backend.log` after crashes; deleting
  requires killing python.exe or a reboot.
- eStock source: SQL Server at 192.168.1.2, database `stock`, read-only login;
  store_id 1 = Elsanta (owner-confirmed); unmapped store_ids auto-create
  `STORE<id>` branches.

## Codebase seams (verified)
- Stock is batch-level (`stock_batches`), FEFO by `exp_date`; adjustments write
  `stock_movements` with reason `adjust` (CHECK constraint list includes it).
- `inventory.adjust_stock` already existed for single-batch corrections — the
  جرد module wraps the same movement pattern in count sessions.
- Weekly task template "جرد أسبوعي للمخزون" already references a stock-count
  screen; the /stocktaking module is what it points to now.
- `api/routes.py` is the single router registry; new domains follow the
  import + include_router pattern.
- Tests live in `src/backend/app/tests/` with a shared session-scoped DB via
  `conftest.py` — idempotency tests must compare before/after counts, not
  absolute numbers (lifespan may have pre-created data).
- Frontend: all strings in `app/i18n.js` (ar + en dicts, same keys); nav in
  `components/Shell.js` NAV array with role gating; API client in `app/api.js`.
- `useSearchParams` in Next pages must be wrapped in Suspense (POS ?rx= lesson).

## Search behavior (user complaint → root cause)
- Old search: `LIKE %term%` ordered by name — contains-matches drowned out
  prefix matches, so typing "ب" felt broken. Fix: rank prefix (name_ar/name_en/
  code) first, then scientific-name prefix, then contains. (2026-07-11)

## Self-annealing log
- 2026-07-11 · `test_sync` failed after جرد models landed: the eStock mirror
  WIPES AND RELOADS products/stock_batches every sync cycle (etl `_WIPE_ORDER`),
  so any ProCare-native table with FKs onto them (a) blocks the wipe with an
  IntegrityError and (b) would lose its rows' referents every 30s in production.
  Fix: `stock_count_lines.batch_id/product_id` are plain indexed ints, the
  product name is snapshotted onto the line (`name_ar`), the sheet outer-joins,
  and posting skips vanished batches (`skipped_missing_batch` in the result).
  RULE for future features: never FK onto mirror-wiped tables (products,
  stock_batches, sales, purchases, vendors, customers…) from tables that must
  survive sync — snapshot the display fields instead.

- 2026-07-11 · Branch-scoped sync wipe (`etl._wipe_branch_rows`) failed with a
  FK IntegrityError whenever a *requested* (unapproved) transfer existed: its
  lines carry NULL batch ids, so the batch-based line delete missed them and
  the parent-transfer delete failed — this would kill every production sync
  cycle while a transfer request is pending. Fix: also delete lines by parent
  transfer_id. Caught by running the full suite in order (test_transfer_requests
  leaves a pending request, then test_units_stagnant syncs).

- 2026-07-11 · Two-phase transfer added alongside the one-step approve (kept
  for the quick POS order-from-branch flow): request → ship (in_transit) →
  receive. Ship moves stock OUT only (transfer_out); receive creates the
  destination batch from the confirmed qty+expiry (transfer_in). A short
  receipt is real shrinkage (out > in, visible in the ledger). Status CHECK
  already allowed 'in_transit', so no migration needed.

- 2026-07-18 · Elsanta WAN drops long pulls: one `SELECT * FROM Sales_details`
  (313K rows) dies at ~6 min with pyodbc 10054 / 08S01 "Communication link
  failure" — so a full elsanta mirror could never complete, while mashala (LAN)
  finished in ~65s. Fix in etl.py: (1) `_iter_rows` pages the big sales/purchase
  tables by key range (`WHERE sales_id BETWEEN lo AND hi`, `SYNC_CHUNK_ROWS`
  env, default 20K) so each query finishes before the WAN kills it; (2)
  `_ResilientSource.execute` fetches eagerly (`Result.freeze`) INSIDE a retry
  loop — on a comm error it disposes the engine pool, reconnects fresh, and
  re-runs the chunk (3 attempts, linear backoff). Retry is safe: source is
  SELECT-only and a chunk is only transformed/inserted after its fetch fully
  succeeds. Non-network errors are never retried. Live elsanta tables all carry
  the chunk keys (sales_id/purchase_id); `Branches_back_sales_*` don't exist
  there (skipped by has_table).
- 2026-07-18 · Full wipe+reload can't be the continuous-sync shape: even
  chunked, every cycle drags ~1.1M elsanta rows over the WAN. Fix: incremental
  window sync — once a source completes ONE full load (recorded in the new
  `sync_state` table, so demo data or a restart can never suppress the initial
  history pull), each cycle re-pulls only the last `SYNC_INCREMENTAL_DAYS`
  (default 7) of sales/purchases + the small live-state tables. A trailing
  WINDOW, not append: returns/edits mutate recent source rows. Window delete
  and window fetch use the same COALESCE(bill_date,insert_date) boundary; a
  Python-side date guard stops a dateless fallback fetch from re-inserting
  history. Stock/catalogue/customers/vendors/employees still refresh fully
  (current-state, small). RULE: sales older than the window are treated as
  immutable — backdated source entries need a manual full resync.
- 2026-07-18 · Unindexed FK columns made the sync wipe QUADRATIC: deleting 35K
  stock_batches FK-checked 190K unindexed sale_lines.batch_id rows per delete
  (~6.8 billion row visits, 504s measured; 0.11s after indexing). The 814s
  "slow incremental cycle" was 77% this one DELETE. Fix: FK-check indexes on
  sale_lines.batch_id, purchase_lines.purchase_id/batch_id,
  loyalty_transactions.sale_id, stock_movements.batch_id,
  stock_transfer_lines.transfer_id/from/to_batch_id, sales.original_sale_id —
  declared in models AND migrate.ensure_fk_indexes (create_all never touches
  existing tables). Live incremental cycle vs mashala: 814s → 11.8s.
  RULE: every FK column on a table the sync wipes/deletes from MUST be indexed.
- 2026-07-18 · Stale-process trap (bit us again): python backends from
  yesterday (one elevated, unreadable CommandLine) held procare.db write locks
  and bloated the WAL to 113MB, making a timing run look 10× slower. Check
  `Get-Process python*` start times BEFORE benchmarking; kill stale pairs
  (parent + child spawned ~2s apart).
- 2026-07-18 · Treasury double-count bug (pre-existing): _load_treasury
  appended Cash_depots snapshot entries every cycle but _wipe_branch_rows
  never cleared LedgerEntry — branch-scoped sync stacked another copy of every
  depot balance each cycle. Fix: delete ref_type='depot' rows for the branch
  before re-adding; ProCare-native vouchers (other ref_types) untouched.
- 2026-07-18 · Dashboard KPI mislabel: `summary()` computed the month bill
  count but discarded it, and the UI showed `sales_month` (REVENUE, sum of
  total_net — 26,261.25 EGP for July) under a label that read as a sales count.
  Fix: `bills_month` now returned in kpis; frontend labels revenue as
  "إيراد الشهر" with "N فواتير" in the sub-line.

- 2026-07-19 · Duplicate-route trap: a bad conflict resolution on main left TWO
  `@router.post("")` create() handlers in api/stocktaking.py; Starlette routes
  to the FIRST registration, so the broken copy (undefined `result`) shadowed
  the working one and POST /api/stocktaking 500'd on main while the suite
  still read "196/196" there. RULE: after resolving any conflict in an api/
  module, grep for duplicated `def`/decorator pairs and run that module's
  tests — route shadowing fails silently at import time.

- 2026-07-19 · Backup route + server identities (on-site at Elsanta):
  - WAN 196.202.93.37 = `DESKTOP-DUTL25M` = **Elsanta** (313K Sales_details,
    2 stores incl. مخزن منتهي الصلاحيه, history from 2020-07-28).
  - LAN 192.168.1.2 = `DESKTOP-SHTFS3J` = **Mashala** (185K details, 1 store,
    history from 2021-04-05 — seeded from the stock_Elsnta_2021_04_04 snapshot;
    identical 53,521-product catalogue on both).
  - Elsanta backs up `stock` HOURLY to `F:\backup\stock_backup_*.bak` (~843MB);
    Mashala every 30 min to `H:\backup\` (~528MB). Both SQL Server 2008 RTM
    (10.0.1600) — no backup compression.
  - SMB/RDP ports open on Elsanta WAN but Windows creds unknown (SQL creds are
    NOT Windows creds). The read-only SQL login has ADMINISTER BULK OPERATIONS,
    so the .bak is fetchable over the SQL connection itself:
    `SUBSTRING(BulkColumn, offset, n) FROM OPENROWSET(BULK '<path>', SINGLE_BLOB)`
    — 16MB chunks, per-chunk retry+reconnect, append-resume by file size.
    ~20s fixed server-side cost per query (whole-file materialization), so
    bigger chunks amortize better. TAPE magic header validates the format.
  - Initial-fill pipeline: `.local-run/elsanta_restore_and_fill.py` (restore
    D:\ProCareBackups\*.bak → stock_elsanta on localhost → etl.mirror
    branch_scoped full → sync._record_cycle('elsanta') flips the incremental
    gate). Needs MSSQLSERVER started by admin.

## Data-quality rules
- "Available" stock = amount > 0 AND not expired (`available_stock_filter`).
- Posting a جرد uses counted minus LIVE batch amount at post time (not the
  snapshot) so sales during the count never corrupt the final quantity.
