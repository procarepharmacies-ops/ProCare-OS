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
- 2026-07-18 · Dashboard KPI mislabel: `summary()` computed the month bill
  count but discarded it, and the UI showed `sales_month` (REVENUE, sum of
  total_net — 26,261.25 EGP for July) under a label that read as a sales count.
  Fix: `bills_month` now returned in kpis; frontend labels revenue as
  "إيراد الشهر" with "N فواتير" in the sub-line.

## Data-quality rules
- "Available" stock = amount > 0 AND not expired (`available_stock_filter`).
- Posting a جرد uses counted minus LIVE batch amount at post time (not the
  snapshot) so sales during the count never corrupt the final quantity.
