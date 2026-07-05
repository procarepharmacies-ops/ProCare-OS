# Folding in the old branch backups (Mashala + pre-merge Elsanta)

You have point-in-time eStock backups from before the branches were merged —
**Mashala** (the branch that opened *before* Elsanta) and **Elsanta** — on
`D:\old\`:

```
D:\old\7-4-2021(old)\                         # 2021-04-07 snapshot (folder)
D:\old\18-3-2023\                             # 2023-03-18 snapshot (folder)
D:\old\stock_backup_2021_04_04_135823_3423913\
        stock_backup_2021_04_04_135823_3423913.bak   # 2021-04-04 full backup
```

This guide restores them into the **new SQL Server Express** and folds their
history into ProCare **keyed by branch**, so the 5-year / deep analysis includes
Mashala and the pre-merge Elsanta era. ProCare only ever reads these — the
read-only mirror never writes back.

> Key fact: the mirror **auto-creates a ProCare branch for every `store_id`** it
> finds in a source (`app/services/etl.py`), so a restored database that already
> carries Mashala/Elsanta/Main store ids lands as three distinct branches in one
> pass — no branch is merged into another.

## 1. Restore the `.bak` into SQL Server Express (SSMS)

First read what's inside the backup (logical file names + which databases):

```sql
RESTORE FILELISTONLY
  FROM DISK = N'D:\old\stock_backup_2021_04_04_135823_3423913\stock_backup_2021_04_04_135823_3423913.bak';
```

Then restore it under a **distinct name** (so it sits next to the live `ProCare`
db without clobbering it). Use the logical names from the step above:

```sql
RESTORE DATABASE stock_hist_2021
  FROM DISK = N'D:\old\stock_backup_2021_04_04_135823_3423913\stock_backup_2021_04_04_135823_3423913.bak'
  WITH MOVE 'stock'     TO 'C:\SQLData\stock_hist_2021.mdf',    -- data logical name
       MOVE 'stock_log' TO 'C:\SQLData\stock_hist_2021_ldf.ldf',-- log  logical name
       REPLACE, RECOVERY;
```

If `D:\old\7-4-2021(old)\` and `D:\old\18-3-2023\` are **detached data files**
(`.mdf` + `.ldf`) rather than `.bak`, attach them instead:

```sql
CREATE DATABASE stock_hist_2023 ON
  (FILENAME = N'D:\old\18-3-2023\stock.mdf'),
  (FILENAME = N'D:\old\18-3-2023\stock_log.ldf')
FOR ATTACH;
```

Give a **read-only login** access to each restored db (never `db_owner`):

```sql
USE stock_hist_2021;
CREATE USER procare_ro FOR LOGIN procare_ro;   -- login created once, server-wide
ALTER ROLE db_datareader ADD MEMBER procare_ro;
```

## 2. See which branches each backup contains

Point ProCare's `estock_source` at the restored db and run the preflight — it
reports every `store_id` present so you can name them before importing:

```jsonc
// config/connections.json  → estock_source
{ "driver": "ODBC Driver 18 for SQL Server", "server": "localhost", "port": 1433,
  "database": "stock_hist_2021", "username": "procare_ro", "password": "…",
  "encrypt": "yes", "trust_server_certificate": "yes" }
```

```
GET /api/sync/preflight
→ { "read_only": true, "store_ids_found": [1, 2, 3], ... }
```

Map each `store_id` to a branch code via `ESTOCK_STORE_BRANCH_MAP` (env or the
`estock_source.store_branch_map` config key) — e.g. Mashala = store 3:

```
ESTOCK_STORE_BRANCH_MAP={"1":"ELSANTA","2":"MAIN","3":"MASHALA"}
```

Any `store_id` you don't map still auto-creates a `STORE<id>` branch, so nothing
is lost if a number is unknown — confirm it from the preflight, then rename.

## 3. Import the history

- **One backup already holds every branch** (the usual case — eStock kept all
  branches in one `stock` db): point `estock_source` at that restored db and run
  the mirror (`POST /api/etl/run`). Mashala, Elsanta and Main all import as
  separate branches; the deep analysis and the by-branch report then cover them.

- **Branches were split across separate databases**: the mirror is a **full
  refresh** (it reloads ProCare from a single source each run), so importing a
  second historical db on its own would replace the first. To *combine* several
  historical databases into one ProCare history, either (a) restore/attach them
  and run the analysis against each separately for archival comparison, or
  (b) ask for the **append/merge importer** — a small addition that loads a
  source *without* wiping, deduping by branch + business date — and we wire it in.

## 4. What you get

Once imported, everything already built reads the extra branch automatically:

- **Reports → Performance over time → By branch** lists Mashala alongside Main
  and Elsanta, with each branch's 5-year revenue, profit, invoices and stock.
- **`/api/performance/deep`** folds every branch into the whole-pharmacy
  diagnostic (growth, margins, supplier concentration, inventory, cash…).
- **`sql/performance-analysis.sql`** sections A2 / D4 break the numbers out per
  branch directly in SSMS.

> Tip: keep the restored `stock_hist_*` databases **read-only**
> (`ALTER DATABASE stock_hist_2021 SET READ_ONLY;`) so an accidental write can
> never touch the historical record.
