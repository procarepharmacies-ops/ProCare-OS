# Raw mirror: the first fill

ProCare mirrors **all 114 eStock tables**. 28 are read into real ProCare models
by dedicated loaders; the other 86 are held verbatim, row for row, in
`estock_raw_mirror`. This page is about filling that second group the first time.

Everything here is **read-only against eStock**. ProCare never writes to the
pharmacy's live database.

## Why it needs a plan

The 86 tables hold **~2.01M rows**, and ~1.6M of them sit in three append-only
change logs:

| table | rows | how it is read |
|---|---:|---|
| `Branches_Product_amount_Change` | 1,052,238 | watermark on `ch_id` |
| `Product_amount_Change` | 533,130 | watermark on `id` |
| `Gedo_customers` | 118,460 | watermark on `gc_id` |
| `Branches_convert_details` | 62,177 | full scan + anti-join |
| the other 82 tables | ~49,500 | refreshed wholesale each cycle |

The read lands on the SQL Server instance that also serves the POS, and the write
adds roughly **1 GB** to ProCare's own database — which matters on SQL Server
Express with its 10 GB cap (`DB_SIZE_CAP_MB` in `.env` tracks it).

So: **run the first fill off-peak.** Once it is done, every later cycle only
pulls rows above the stored watermark, which is cheap enough for the normal
5-minute cadence.

## Controls

| env var | default | what it does |
|---|---|---|
| `RAW_MIRROR` | `1` | `0` switches the whole pass off |
| `RAW_MIRROR_SKIP_ABOVE_ROWS` | `0` (no cap) | skip any source table with more than N rows this cycle |
| `RAW_MIRROR_REFRESH_MAX_ROWS` | `50000` | at or below this, a table is refreshed wholesale instead of read incrementally |

Skipped tables are listed in the sync result as `raw_skipped` and are **not**
counted as covered, so `raw_coverage_pct` never overstates what is held.

## Staged fill (recommended)

Take the 82 small tables during the day, the heavy three at night.

**1. Daytime — everything under 20,000 rows (~50K rows, seconds):**

```bat
set RAW_MIRROR_SKIP_ABOVE_ROWS=20000
python -m app.services.etl --run
```

**2. Off-peak — lift the cap and let the change logs fill:**

```bat
set RAW_MIRROR_SKIP_ABOVE_ROWS=0
python -m app.services.etl --run
```

Run both from `src/backend`. The pass is resumable by construction: it is
idempotent, so an interrupted fill is fixed by running it again — already-held
rows are anti-joined away, not duplicated.

**3. Confirm coverage:**

```bat
python -m tools.estock_schema_dump --counts --out docs/estock-schema-dump.md
```

The header should read `Coverage: 100.0%` with `Not mirrored: 0`.

## Checking what is held

```sql
SELECT source_table, COUNT(*) AS rows_held
FROM estock_raw_mirror
GROUP BY source_table
ORDER BY rows_held DESC;

SELECT * FROM estock_raw_watermark ORDER BY source_table;
```

A sync run reports the same thing in its counts: `raw_tables_total`,
`raw_tables_dedicated`, `raw_tables_mirrored`, `raw_skipped`, `raw_failed`,
`raw_total_rows`, `raw_coverage_pct`.

## Reading a raw table

Rows are stored as JSON in `raw`, keyed by `(source_table, source_id)`, with
`branch_id` filled in for tables that carry a `store_id`:

```sql
SELECT TOP 20 source_id, branch_id, raw
FROM estock_raw_mirror
WHERE source_table = 'Gedo_customers'
ORDER BY source_id;
```

That is enough to settle the question the GL sub-ledger work was blocked on —
what the `gc_type` party-type codes actually contain — against real rows instead
of a guess. When a table earns a real ProCare model, promote it to a dedicated
loader in `app/services/etl.py` and add it to `COVERED_SOURCE_TABLES`; the rows
are already local, so that no longer costs a trip to the pharmacy server.

## What the raw mirror does not do

- **It does not refresh in-place edits to a large table.** Small tables (≤50K
  rows) are re-read wholesale every cycle, so edits land. Large tables are
  append-only change logs and are read forward from a watermark; if eStock ever
  edited an old row in one of them, the mirror would keep the original. To force
  a re-read of one table, delete its rows and its watermark:

  ```sql
  DELETE FROM estock_raw_mirror   WHERE source_table = 'Product_amount_Change';
  DELETE FROM estock_raw_watermark WHERE source_table = 'Product_amount_Change';
  ```

- **It is not a query layer.** The rows are exact but they are JSON. Anything the
  app shows a pharmacist should go through a dedicated loader and a real model.
