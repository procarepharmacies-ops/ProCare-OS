-- find-product-delete-in-log.sql   (READ-ONLY, SQL Server 2008)
-- RUN ON: the server where Panadol vanished, database `stock`, OFF-PEAK (it scans
-- the ~17 GB transaction log; can take minutes and load the server).
-- Why this works: `stock` is FULL recovery and its log has never been truncated
-- (log_reuse_wait = LOG_BACKUP), so every DELETE/UPDATE on Products is still in it.
--
-- !! DO NOT take a log backup, shrink the log, or switch `stock` to SIMPLE until
-- !! Panadol is recovered — that throws this evidence away.
-- Send every grid back. Changes nothing.

USE stock;

-- 0) First: is the Panadol row really gone, or only flagged? (deleted='0' = removed
--    in eStock's inverted convention; active='0' = inactive). Empty = row is gone.
SELECT product_id, product_code, product_name_ar, product_name_en, deleted, active, up_date, up_uid
FROM Products
WHERE product_name_ar LIKE N'%بانادول%' OR product_name_ar LIKE N'%بنادول%'
   OR product_name_en LIKE N'%panadol%';

-- 1) Every transaction that physically DELETED rows from Products: when, by which
--    SQL login, the application/transaction name, and how many rows.
SELECT b.[Begin Time]                  AS began,
       SUSER_SNAME(b.[Transaction SID]) AS sql_login,
       b.[Transaction Name]             AS tran_name,
       d.[Transaction ID]               AS tran_id,
       COUNT(*)                         AS rows_deleted
FROM fn_dblog(NULL, NULL) d
JOIN fn_dblog(NULL, NULL) b
  ON b.[Transaction ID] = d.[Transaction ID] AND b.Operation = 'LOP_BEGIN_XACT'
WHERE d.Operation = 'LOP_DELETE_ROWS'
  AND d.AllocUnitName LIKE 'dbo.Products%'
GROUP BY b.[Begin Time], b.[Transaction SID], b.[Transaction Name], d.[Transaction ID]
ORDER BY b.[Begin Time] DESC;

-- 2) If 0 says the row still exists but is flagged: the edit log has the change.
SELECT TOP 50 e.product_edit_id, e.product_id, e.insert_type, e.product_name_ar,
       e.deleted, e.active, e.up_date, e.up_uid, e.insert_date, e.insert_uid, e.notes
FROM Branches_products_edit e
WHERE e.product_name_ar LIKE N'%بانادول%' OR e.product_name_ar LIKE N'%بنادول%'
   OR e.product_name_en LIKE N'%panadol%'
ORDER BY e.product_edit_id DESC;

-- 3) Which backups exist (to restore a copy from BEFORE the delete time in grid 1).
SELECT TOP 30 b.backup_start_date, b.backup_finish_date, b.type, b.is_copy_only,
       m.physical_device_name
FROM msdb.dbo.backupset b
JOIN msdb.dbo.backupmediafamily m ON m.media_set_id = b.media_set_id
WHERE b.database_name = 'stock'
ORDER BY b.backup_finish_date DESC;
