-- diagnose-capacity.sql   (READ-ONLY, SQL Server 2008-safe)
-- RUN ON: the server that hosts BOTH `stock` and `ProCare` (Elsanta). Send every
-- result grid back (Copy with Headers). Changes nothing.
-- Why: stock LOG = 17 GB for a 1.2 GB data file, ProCare data = 18 GB. A log far
-- bigger than its data means it is not being truncated; a full disk or log stops
-- eStock writes (replication writes into Branches_*) silently.

-- 1) Why can each log not be reused, and what recovery model is it in?
--    LOG_BACKUP = FULL recovery without log backups (the usual case).
--    ACTIVE_TRANSACTION = an open transaction pins it. REPLICATION = a reader is behind.
SELECT name, recovery_model_desc, log_reuse_wait_desc, state_desc FROM sys.databases;

-- 2) Log size and % used for every database.
DBCC SQLPERF(LOGSPACE);

-- 3) Free space per drive (MB) and the files' max size / growth (is a limit near?).
EXEC master..xp_fixeddrives;

SELECT DB_NAME(database_id) AS db, name AS logical_file, type_desc,
       size * 8 / 1024 AS size_mb,
       CASE WHEN max_size = -1 THEN -1 WHEN max_size = 268435456 THEN -1
            ELSE max_size * 8 / 1024 END AS max_mb,   -- -1 = unlimited
       physical_name
FROM sys.master_files
WHERE DB_NAME(database_id) IN ('stock', 'ProCare')
ORDER BY db, type_desc;

-- 4) Open transactions in `stock` (an old open transaction pins the log).
DBCC OPENTRAN('stock');

-- 5) Which ProCare tables hold the 18 GB? branch_order_* should be small
--    (eStock has ~8,204 headers / ~61,872 lines); millions of rows = the
--    duplicate-per-sync bug fixed in commit f6a9d81 (not yet deployed here).
USE ProCare;

SELECT TOP 15 OBJECT_NAME(ps.object_id) AS table_name,
       SUM(CASE WHEN ps.index_id IN (0, 1) THEN ps.row_count ELSE 0 END) AS row_count,
       SUM(ps.reserved_page_count) * 8 / 1024 AS reserved_mb
FROM sys.dm_db_partition_stats ps
GROUP BY ps.object_id
ORDER BY reserved_mb DESC;

SELECT 'branch_order_headers' AS tbl, COUNT(*) AS rows_now,
       COUNT(DISTINCT source_order_id) AS distinct_source_orders
FROM branch_order_headers;
