/*==============================================================================
  ProCare — fix "transaction log for database 'ProCare' is full" (Error 9002)
  SQL Server 2008-compatible (Elsanta branch instance).

  ⚠️  RUN THIS AGAINST THE **ProCare** DATABASE ONLY.
      NEVER run it against the eStock `stock` database. eStock is the source of
      truth and ProCare is read-only to it; its recovery model is the pharmacy
      owner's decision, not ours.

  WHY THIS HAPPENS
  ----------------
  A database created from the default `model` inherits the FULL recovery model.
  In FULL recovery the transaction log is only truncated by a LOG BACKUP. If no
  log backups are ever taken, the log grows without bound until it hits the disk
  or its MAXSIZE, and every subsequent write fails with error 9002.

  The first full ETL mirror is what surfaces it: Branches_Product_Amount (~121K
  rows), Branch_order_header/details (~70K rows) and the sales/purchase history
  are all written in one pass.

  WHY SIMPLE IS THE RIGHT ANSWER FOR ProCare
  ------------------------------------------
  ProCare's database is a MIRROR of eStock plus ProCare's own operational rows.
  Its disaster-recovery path is "re-run the mirror from eStock", not "replay the
  transaction log to a point in time". SIMPLE recovery truncates the log at every
  checkpoint, which is exactly what a re-syncable mirror wants.

  Run the sections in order. Section 1 is read-only — run it first and read the
  output before changing anything.
==============================================================================*/


/*------------------------------------------------------------------------------
  SECTION 1 — DIAGNOSE (read-only, safe to run any time)
------------------------------------------------------------------------------*/

-- 1a. Recovery model + WHY the log cannot be reused.
--     log_reuse_wait_desc is the single most important value here.
SELECT  name                  AS database_name,
        recovery_model_desc,
        log_reuse_wait_desc,
        state_desc
FROM    sys.databases
WHERE   name = 'ProCare';

/*  Interpret log_reuse_wait_desc:

      LOG_BACKUP         -> FULL/BULK_LOGGED recovery, no log backup taken.
                            THE COMMON CASE. Go to Section 2.

      ACTIVE_TRANSACTION -> An open transaction is pinning the log (usually a
                            crashed/killed ETL run). Go to Section 3 FIRST,
                            then Section 2.

      NOTHING            -> The log is genuinely full: it hit MAXSIZE or the
                            drive is out of space. Go to Section 4.

      CHECKPOINT         -> Rare; a checkpoint has not completed. Run
                            `CHECKPOINT;` in ProCare and re-check.
*/

-- 1b. How full is the log, in percent?  (DBCC SQLPERF is 2008-safe;
--     sys.dm_db_log_space_usage is 2012+ and must NOT be used here.)
DBCC SQLPERF(LOGSPACE);

-- 1c. File sizes, growth settings and physical paths.
--     size/max_size are in 8 KB pages. max_size = -1 means unlimited.
USE ProCare;
GO
SELECT  file_id,
        name                                        AS logical_name,
        type_desc,
        CAST(size     * 8.0 / 1024 AS DECIMAL(18,2)) AS current_mb,
        CASE WHEN max_size = -1 THEN NULL
             ELSE CAST(max_size * 8.0 / 1024 AS DECIMAL(18,2)) END AS max_mb,
        CASE WHEN is_percent_growth = 1 THEN NULL
             ELSE CAST(growth   * 8.0 / 1024 AS DECIMAL(18,2)) END AS growth_mb,
        is_percent_growth,
        physical_name
FROM    sys.database_files
ORDER BY type_desc DESC, file_id;
GO

/*  If current_mb == max_mb on the LOG row, the log hit its ceiling -> Section 4.
    Also check free space on the drive holding the .ldf in physical_name.       */


/*------------------------------------------------------------------------------
  SECTION 2 — THE FIX: switch ProCare to SIMPLE recovery and reclaim the log
  Run this when log_reuse_wait_desc = 'LOG_BACKUP'.
------------------------------------------------------------------------------*/

USE master;
GO

-- Switching to SIMPLE lets every checkpoint truncate the log. This is the
-- correct steady-state setting for ProCare and should be left in place.
ALTER DATABASE ProCare SET RECOVERY SIMPLE;
GO

USE ProCare;
GO

-- Force a checkpoint so the now-truncatable log space is actually released.
CHECKPOINT;
GO

-- Shrink the physical .ldf back to a sane working size (512 MB).
-- Resolved dynamically so this works whatever the logical log file is called.
DECLARE @log_name  SYSNAME,
        @sql       NVARCHAR(500);

SELECT  @log_name = name
FROM    sys.database_files
WHERE   type_desc = 'LOG';

SET @sql = N'DBCC SHRINKFILE (' + QUOTENAME(@log_name) + N', 512)';
PRINT @sql;
EXEC sp_executesql @sql;
GO

-- Give the log a fixed, predictable growth profile: 512 MB start, 256 MB steps,
-- 8 GB ceiling. A bounded ceiling means a runaway transaction fails loudly
-- instead of silently eating the whole drive out from under eStock.
DECLARE @log_name SYSNAME,
        @sql      NVARCHAR(500);

SELECT  @log_name = name
FROM    sys.database_files
WHERE   type_desc = 'LOG';

SET @sql = N'ALTER DATABASE ProCare MODIFY FILE (NAME = ' + QUOTENAME(@log_name)
         + N', SIZE = 512MB, FILEGROWTH = 256MB, MAXSIZE = 8192MB)';
PRINT @sql;
EXEC sp_executesql @sql;
GO

-- Verify: recovery_model_desc should now be SIMPLE and log_reuse_wait_desc
-- should be NOTHING.
SELECT  name, recovery_model_desc, log_reuse_wait_desc
FROM    sys.databases
WHERE   name = 'ProCare';
GO


/*------------------------------------------------------------------------------
  SECTION 3 — Only if log_reuse_wait_desc = 'ACTIVE_TRANSACTION'
  An open transaction is pinning the log. Almost always a crashed ETL mirror.
------------------------------------------------------------------------------*/

USE ProCare;
GO

-- Shows the oldest active transaction and its SPID.
DBCC OPENTRAN;
GO

-- Inspect what that session is actually doing before touching it.
-- Replace <SPID> with the SPID that DBCC OPENTRAN reported.
--   DBCC INPUTBUFFER(<SPID>);

-- Only after confirming it is an abandoned ProCare/ETL session — never a live
-- eStock POS session — end it, then re-run Section 2.
--   KILL <SPID>;


/*------------------------------------------------------------------------------
  SECTION 4 — Only if the log hit MAXSIZE or the drive is full
------------------------------------------------------------------------------*/

/*  a) Drive out of space:
       Free space on the volume holding the .ldf (see physical_name in 1c), or
       relocate the log. Do NOT delete eStock backups to make room without the
       owner's say-so — those are the pharmacy's recovery path.

    b) Log hit a fixed MAXSIZE:
       Raise the ceiling, then run Section 2 to switch to SIMPLE and shrink. */

USE master;
GO
DECLARE @log_name SYSNAME,
        @sql      NVARCHAR(500);

SELECT  @log_name = name
FROM    ProCare.sys.database_files
WHERE   type_desc = 'LOG';

SET @sql = N'ALTER DATABASE ProCare MODIFY FILE (NAME = ' + QUOTENAME(@log_name)
         + N', MAXSIZE = 8192MB, FILEGROWTH = 256MB)';
PRINT @sql;
EXEC sp_executesql @sql;
GO


/*------------------------------------------------------------------------------
  SECTION 5 — Post-fix verification
------------------------------------------------------------------------------*/

-- Recovery model SIMPLE, log_reuse_wait_desc NOTHING.
SELECT  name, recovery_model_desc, log_reuse_wait_desc, state_desc
FROM    sys.databases
WHERE   name = 'ProCare';

-- Log should now be small and mostly empty.
DBCC SQLPERF(LOGSPACE);

-- Confirm eStock was NOT touched by any of the above. Its recovery model should
-- be exactly whatever it was before you started.
SELECT  name, recovery_model_desc, log_reuse_wait_desc
FROM    sys.databases
WHERE   name = 'stock';

-- Data-file size vs the Express 10 GB per-database cap (ProCare's own DB only;
-- ProCare's built-in monitor at GET /api/automation/db-health tracks this too).
USE ProCare;
GO
SELECT  CAST(SUM(size) * 8.0 / 1024 AS DECIMAL(18,2)) AS data_mb
FROM    sys.database_files
WHERE   type_desc = 'ROWS';
GO
