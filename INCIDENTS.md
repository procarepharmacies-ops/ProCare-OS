# ProCare Pilot — Incidents Log

**Purpose:** Track all issues discovered during Weeks 1–12 parallel testing.

**Format:** Each incident gets:
- ID, date, severity, branch affected
- Description, root cause, impact
- Resolution, time-to-fix, learning

---

## Template

```markdown
### INC-001 — [Date] — [Branch] — [Severity]

**Description:**
[What happened]

**Impact:**
- Transactions affected: [count or N/A]
- Revenue affected: [amount or N/A]
- Downtime: [minutes or N/A]

**Root Cause:**
[Why it happened]

**Resolution:**
[How it was fixed]

**Time-to-Fix:**
[Minutes from detection to resolution]

**Prevention:**
[How we prevent this in Phase 3]

**Severity Levels:**
- 🔴 Critical: Data loss, system down, revenue at risk
- 🟡 High: Functional bug, workaround available, no data loss
- 🟢 Medium: Non-critical feature broken, user can continue work
- ⚪ Low: Minor bug, no user impact
```

---

## Issues Log

### INC-001 — [Date] — [Branch] — Severity

**Description:**
[To be filled as incidents occur]

**Impact:**
- Transactions affected: 0
- Revenue affected: $0
- Downtime: 0 min

**Root Cause:**
[TBD]

**Resolution:**
[TBD]

**Time-to-Fix:**
[TBD]

**Prevention:**
[TBD]

---

## Weekly Summary (Update Fridays)

| Week | Total Incidents | Critical | High | Medium | Status |
|------|-----------------|----------|------|--------|--------|
| 1    | 0               | 0        | 0    | 0      | ✅ On track |
| 2    | -               | -        | -    | -      | Pending |
| 3    | -               | -        | -    | -      | Pending |
| ...  | -               | -        | -    | -      | Pending |
| 12   | -               | -        | -    | -      | Pending |

---

## Sign-Off (End of Week 12)

- [ ] Zero critical incidents
- [ ] All high incidents resolved and tested
- [ ] Finance sign-off on data accuracy
- [ ] Operations sign-off on user experience
- [ ] Ready for Phase 3 Main branch cutover

**Approved by:**
- Finance: _________________ Date: _______
- Operations: _________________ Date: _______
- Dev Lead: _________________ Date: _______

---

## Open Incidents — logged 2026-08-29

### INC-2026-0829-A — 2026-08-29 — Elsanta — 🔴 Critical

**Description:**
The hourly SQL Agent job `ProCare_Stock_LogBackup` has failed on every run since
2026-08-28 ~03:00. `backup_watchdog.ps1` has been reporting it correctly
(`C:\ProCareFix\BACKUP_ALERT.txt`, "Log backup file is 1250 minutes old, limit 100");
the alert was being written but nobody was reading it.

**Impact:**
- Transactions affected: none — sales are unaffected, the POS never waits on backups.
- Point-in-time recovery for the live `stock` database: LOST for the whole window.
  Only the nightly FULL backups exist (those still succeed).
- `stock` is in FULL recovery with `log_reuse_wait_desc = LOG_BACKUP`, so the log
  cannot truncate: `stock_Log.LDF` is 1585 MB and **98.5% full** (1561 MB used) and
  will keep autogrowing until a log backup succeeds. E: has 149.9 GB free, so there
  is headroom, but the growth is unbounded.

**Root Cause:**
The job appends (`NOINIT`) every log backup to ONE media file,
`E:\SQLBackups\stock_log.trn`, which has grown to 5.6 GB. That media set's tail is
now malformed, so SQL Server refuses to append:

    The backup data at the end of "E:\SQLBackups\stock_log.trn" is incorrectly
    formatted. Backup sets on the media might be damaged and unusable. (job step 1)

Every subsequent hourly run hits the same damaged tail and fails identically. The
failure is in the *destination media*, not in the database or the log chain.

**Resolution:** APPLIED and verified 2026-08-29 00:17-00:25, operator-approved.
1. `BACKUP LOG stock TO DISK='E:\SQLBackups\stock_log_20260829_001745.trn'` - a NEW
   file, so a clean media set. Succeeded: 200,738 pages in 20 s, 376.7 MB compressed.
   Log went from 1561.2 MB used (98.5%) to 14.4 MB (0.9%), and `log_reuse_wait_desc`
   from `LOG_BACKUP` to `NOTHING`.
2. Job step 1 rewritten to build a timestamped filename per run
   (`stock_log_<yyyymmdd>_<hhmmss>.trn`, COMPRESSION kept) instead of appending to a
   fixed file. Job started manually to verify: SUCCEEDED, 339 pages.
3. The old 5.6 GB `stock_log.trn` was left in place, untouched. Nothing was deleted.

Two follow-on faults were exposed by the fix and also repaired, in
`C:\ProCareFixackup_watchdog.ps1` (original kept as `.bak-20260829`):
- It matched the log backup by the FIXED name `stock_log.trn`, which the fix had just
  frozen forever - it would have alerted every hour on a false positive. It now takes
  the NEWEST file matching `stock_log_*.trn` (the pattern excludes the old file).
- `watchdog_state.json` was all whitespace, so `ConvertFrom-Json` returned `$null`,
  `$state` became `$null`, and the closing `$state.LastHealthy = $healthy` threw on
  every run. No state had ever been persisted, so the anti-spam and once-daily-OK
  logic were both silently dead. Loaded keys are now merged onto the defaults.
  This surfaced only because the healthy branch had never once been reached.
Watchdog now reports `RESULT: ALL CHECKS PASSED`, exits 0, and writes its state file.

**Time-to-Fix:** ~25 min from detection to verified fix.

**NOT done - needs a decision:** the job now writes ~24 files/day with no retention
policy. `ProCare_AppDB_FullBackup` uses 14-day retention; the log backups need an
equivalent or E: accumulates indefinitely (149.5 GB free today and the files are
small after the first, so this is weeks away, not urgent). Deleting backup files was
outside what was approved here.

**Prevention:**
One file per backup, never an unbounded append target. Route `BACKUP_ALERT.txt` to
someone — the watchdog did its job for ~21 hours and was not seen.

---

### INC-2026-0829-B — 2026-08-29 — Elsanta — 🟡 High

**Description:**
The nightly raw-mirror off-peak fill (task `ProCare_RawMirror_OffpeakFill`, daily
03:00) aborts. Its 2026-08-28 run finished `ran=False` after 1.4 min having mirrored
0 rows. The raw mirror is therefore stuck at 64 of 86 tables and ~879K of the
expected ~2.01M rows, and has grown by 2 rows in 24 hours.

**Impact:**
- Sales/POS: none. The dedicated 5-minute loaders keep running and the POS mirror is
  current (newest mirrored sale was minutes old at the time of checking).
- The raw tier stays incomplete, so any promotion of a raw table to a dedicated
  loader is blocked on data that was never mirrored.

**Root Cause:** CONFIRMED 2026-08-29 (mechanism; no fix applied yet).

Two processes run a FULL mirror cycle against the same branch at the same time, and
there is nothing to stop them:

- The backend runs `sync.run_once()` every 300 s (`SYNC_ENABLED=1`).
- `C:\ProCareFixaw_mirror_offpeak_fill.py` at 03:00 also calls `sync.run_once()`
  -- the whole cycle, not just the raw pass -- in a SEPARATE python.exe process.

`sync.py` guards cycles with `_lock = threading.Lock()`, an **in-process thread lock**.
It cannot see another process, so it does not serialise these two at all. The
application lock the fill script's docstring describes covers only the raw pass; the
dedicated loaders "keep running" in both processes by design.

Both cycles then execute `_wipe_branch_sales_window()` (DELETE the trailing sales
window for the branch) followed by `_load_sales()` for the same branch. `_load_sales`
inserts sale HEADERS with `dst.flush()` only, records `sale_id_map`, and inserts the
LINES later via `_bulk_insert`, which commits per chunk. So between one process
recording a parent `sale_id` and inserting the child rows that point at it, the other
process's wipe can delete that parent -- and the child insert then fails exactly as
observed:

    FK__sale_line__sale___1D7B6025 ... table "dbo.sales", column 'sale_id' (547)

The earlier guess (both stores mapping to one branch via `store_branch_map`) was
WRONG and is ruled out: `_wipe_branch_rows` is called once, up front, with the union
of all branches -- not once per store.

The cycle aborts before the raw pass ever runs, which is why the fill reports
`ran=False` and mirrors 0 rows while the mirror stays at 64/86 tables.

**Resolution:** NOT APPLIED -- investigation only, by agreement. `etl.py` also carries
417 uncommitted lines of in-flight work, so it should not be edited blind.

Proposed, in preference order:
1. Make the mutual exclusion cross-process: take a SQL Server application lock
   (`sp_getapplock` on the ProCare DB) around the whole cycle in `sync.run_once()`,
   not a `threading.Lock`. A second cycle then skips rather than races.
2. Cheap interim mitigation, no code change: have the 03:00 task stop the backend's
   sync for the duration, or move the fill to a window where it cannot overlap.
3. Independently worth doing: `_load_sales` should insert headers and their lines
   inside ONE transaction rather than flushing headers and committing lines in
   separate chunks, so a partially-written sale can never be left referencing a
   parent that is gone.

**Time-to-Fix:** root cause 25 min; fix pending.

**Prevention:**
A test that runs a full mirror with two source stores mapped to a single branch.
