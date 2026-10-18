-- stock-log-maintenance.sql   (SQL Server 2008-safe)
-- RUN ON: the Elsanta instance, database `stock` (the eStock database).
-- WHY: `stock` is in FULL recovery with log_reuse_wait_desc = LOG_BACKUP, so the
-- log is never truncated and grew to ~17 GB for 1.2 GB of data.
--
-- !! `stock` is the pharmacy's source of truth. Its recovery model and log backups
-- !! are the OWNER's decision. SECTION 1 only reads. Every statement that changes
-- !! something in SECTIONS 2-4 is COMMENTED OUT; uncomment ONE option on purpose,
-- !! after a verified full backup. ProCare never writes to `stock`; this file is
-- !! an operator runbook, not something the application runs.
-- !! Do NOT use sql/fix-transaction-log-full.sql here: it is for ProCare ONLY.

USE stock;

------------------------------------------------------------------------------
-- SECTION 1 — READ ONLY: do we have backups, and what is the log called?
------------------------------------------------------------------------------
-- 1a) Last backups of `stock` by type (D = full, I = differential, L = log).
--     No recent D means do NOT start log backups or change anything yet.
SELECT type AS backup_type, MAX(backup_finish_date) AS last_backup
FROM msdb.dbo.backupset
WHERE database_name = 'stock'
GROUP BY type
ORDER BY type;

-- 1b) Logical + physical name of the log file (needed for the shrink in section 3).
SELECT name AS logical_name, physical_name, size * 8 / 1024 AS size_mb
FROM sys.database_files WHERE type_desc = 'LOG';

-- 1c) Anything pinning the log right now? (must say LOG_BACKUP, not ACTIVE_TRANSACTION)
SELECT name, recovery_model_desc, log_reuse_wait_desc FROM sys.databases WHERE name = 'stock';
DBCC OPENTRAN('stock');

------------------------------------------------------------------------------
-- SECTION 2 — OPTION A (recommended): keep FULL recovery, start taking log backups.
-- Needs a recent FULL backup (1a). Replace the path with a folder that has room.
------------------------------------------------------------------------------
-- BACKUP LOG stock TO DISK = N'D:\Backups\stock_log_first.trn' WITH INIT, CHECKSUM;

-- Then schedule the same statement (with a timestamped file name) every 60 minutes
-- from Windows Task Scheduler + sqlcmd (Express has no SQL Server Agent), and keep
-- at least 7 days of .trn files with the last full backup.

------------------------------------------------------------------------------
-- SECTION 3 — after a successful log backup: shrink the log file ONCE.
-- Use the logical name from 1b. 2048 = target size in MB. Do not schedule a shrink.
------------------------------------------------------------------------------
-- DBCC SHRINKFILE (N'stock_log', 2048);

------------------------------------------------------------------------------
-- SECTION 4 — OPTION B (owner decision): SIMPLE recovery instead.
-- Simpler, but you lose point-in-time restore for `stock` (only restore to the last
-- full/differential backup). Choose A OR B, never both.
------------------------------------------------------------------------------
-- ALTER DATABASE stock SET RECOVERY SIMPLE;
-- CHECKPOINT;
-- DBCC SHRINKFILE (N'stock_log', 2048);
