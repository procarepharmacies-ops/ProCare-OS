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

## Data-quality rules
- "Available" stock = amount > 0 AND not expired (`available_stock_filter`).
- Posting a جرد uses counted minus LIVE batch amount at post time (not the
  snapshot) so sales during the count never corrupt the final quantity.
