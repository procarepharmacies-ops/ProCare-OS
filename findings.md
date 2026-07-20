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

- 2026-07-20 · Employee-mirror lockout (took TWO fixes): the eStock Employee
  mirror set ProCare `is_active` from the source row every cycle, so a stale
  source employee (active='0'/deleted='1') disabled the matched ProCare login.
  Fix #1 gated the is_active-skip on `password_hash LIKE 'sha256$%'` — but
  `authenticate()` transparently upgrades sha256 → pbkdf2 on first successful
  login, so once the owner logged in, their hash no longer matched the gate and
  the next sync re-locked them. Fix #2: gate on "hash is NOT a sentinel" —
  `not cur_hash.startswith("!")` (the mirror sentinel is `!estock-mirror`) —
  covers sha256$, pbkdf2$, and any future real algorithm. RULE: never gate
  "is this a real login" on a specific hash-algorithm prefix; the hash format
  migrates under you.
- 2026-07-20 · run.py had `reload=True` hardcoded. uvicorn's reloader watches
  app/ and restarts the worker on any file touch, and the reloader dies with
  its parent console — so an unattended pharmacy PC (or any file edit) drops the
  backend. Now `PROCARE_RELOAD` env, default off. Production = single stable
  process; dev opts in.
- 2026-07-20 · Cheque module UNUSED: `Checks` table has 0 rows on BOTH branch
  servers (elsanta DESKTOP-DUTL25M + mashala DESKTOP-SHTFS3J). Columns exist
  (ch_id, gf_id, ch_number, ch_valid_date, ch_status, cashed…) but the pharmacy
  never issued a cheque. A cheque-due alert is dead weight until they start
  using it — deferred.
- 2026-07-20 · Item sales-movement report design: balances are PHYSICAL
  (include expired). Opening is derived, not stored — roll the live on-hand
  back through every flow (sale_lines/purchase_lines + adjust movements) from
  the period start to today, so the last day's closing == on-hand when the
  period ends today (`reconciles` flag). Sale/purchase flow comes from the
  mirrored *_lines (complete), NOT stock_movements (which the mirror doesn't
  write for historical rows — only 'adjust' from ProCare-native جرد). Verified
  live: reconciles exactly on real Elsanta items.

## Data-quality rules
- "Available" stock = amount > 0 AND not expired (`available_stock_filter`).
- Posting a جرد uses counted minus LIVE batch amount at post time (not the
  snapshot) so sales during the count never corrupt the final quantity.
- 2026-07-20 · Titan moved and CHANGED LAYOUT: the install is now
  `D:\AgenticOS\TITAN.349` (old `D:\Labirdo\TITAN.W1` is gone). The 349 build
  writes the ARABIC name at offset 0-40 and English at 40-70 — the REVERSE of
  W1 — and its category sits at 796 (not 792). Running the old hardcoded
  offsets over it silently files Arabic text into the English column, so
  `titan_extract.parse_tar_phy` now DETECTS the layout (`detect_layout`, sniffs
  where the Arabic script is) instead of assuming. RULE: never hardcode a
  binary vendor layout; sniff it.
- 2026-07-20 · The two Titan builds are COMPLEMENTARY, so the loader merges
  rather than reloads: W1 (already in the DB) has ~3k more scientific names but
  lost its Arabic to encoding damage; 349 has 13,598 intact Arabic names but
  fewer scientific ones. Slot ids are per-build, so a DELETE+reload would BOTH
  drop the richer scientific data AND orphan every `products.titan_drug_id`.
  Merge strategy: keep the loaded build as the base (its ids are what products
  point at), fill only its BLANK fields from the new file, append genuinely new
  drugs with fresh ids. Result: 15,373 -> 23,063 drugs, name_ar 23 -> 13,962,
  sci 13,986 -> 19,209, and matching IMPROVED 4,145 -> 4,322 (349 alone would
  have scored 2,049).
- 2026-07-20 · Titan stores NO local/import or medicine flag. Audited every
  unmapped byte (130..796) against manufacturer-nationality ground truth: best
  single-byte separation was 0.36 — unusable. Both are DERIVED instead:
  origin from manufacturer nationality (1,095 makers; EIPICO/AMOUN/SIGMA...
  = local), is_medicine from the therapeutic category (922 categories;
  HAIR CARE/SOAP/MASSAGE = not medicine). Auditable and correctable, unlike a
  guessed byte.
- 2026-07-20 · eStock's own catalogue flags are UNRELIABLE, which is why this
  job exists: `product_drug` marks Rivotril (a controlled benzo) as 0 and a
  shampoo as 1; `product_made` disagrees with itself across one brand (Nexium
  40 vial vs Nexium 20 tabs). Field population: scientific 14%, name_en 99%,
  name_ar 100%, notes/uses 0.1% (61 rows).
- 2026-07-20 · Duplicate detection safety rule: pack-count tokens may be
  stripped when grouping, but STRENGTH tokens never (500 MG vs 1 GM must not
  group — merging them is a dispensing error; regression-tested). Tiers carry a
  `confidence`: code/exact_name = high (safe to bulk-action), name_pack =
  "review" because it also catches LEGITIMATE pack variants (3 TAB vs 5 TAB are
  two real SKUs). Live: 869 groups, 23 high-risk (live stock split across
  copies, e.g. "ماء مذيب 50 مل" entered twice with a double space, 65 + 258
  units on hand).
