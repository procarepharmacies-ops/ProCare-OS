-- restore-product-from-backup.sql   (operator runbook, SQL Server 2008)
-- Bring a deleted Panadol row back into `stock` WITHOUT touching anything else.
-- Every statement that writes is COMMENTED OUT. Uncomment one step at a time,
-- with the owner's approval, after reading find-product-delete-in-log.sql output.
--
-- Plan: restore a backup taken BEFORE the delete (grid 1 time) as a SEPARATE
-- database `stock_recover` (the live `stock` is not touched), compare, then copy
-- back ONLY the missing Products row(s). Stock quantities are NOT copied: count the
-- shelf and enter them through eStock, so today's real amounts are not overwritten.

-- STEP 1 (read-only): logical file names inside the chosen .bak (path from grid 3).
-- RESTORE FILELISTONLY FROM DISK = N'F:\backup\stock_backup_XXXX.bak';

-- STEP 2: restore that backup as a NEW database (use the logical names from step 1;
-- pick new physical file names; the live stock files must not be reused).
-- RESTORE DATABASE stock_recover
--   FROM DISK = N'F:\backup\stock_backup_XXXX.bak'
--   WITH MOVE N'stock'     TO N'F:\recover\stock_recover.mdf',
--        MOVE N'stock_log' TO N'F:\recover\stock_recover.ldf',
--        RECOVERY, STATS = 10;

-- STEP 3 (read-only): the Panadol rows in the copy that are missing from live stock.
-- SELECT r.*
-- FROM stock_recover.dbo.Products r
-- WHERE (r.product_name_ar LIKE N'%بانادول%' OR r.product_name_ar LIKE N'%بنادول%'
--        OR r.product_name_en LIKE N'%panadol%')
--   AND NOT EXISTS (SELECT 1 FROM stock.dbo.Products p WHERE p.product_id = r.product_id);

-- STEP 4: fresh, verified backup of live stock BEFORE writing anything.
-- BACKUP DATABASE stock TO DISK = N'F:\backup\stock_before_panadol_fix.bak' WITH INIT, CHECKSUM;
-- RESTORE VERIFYONLY FROM DISK = N'F:\backup\stock_before_panadol_fix.bak' WITH CHECKSUM;

-- STEP 5: copy the missing row(s) back with the SAME product_id (sales history and
-- other tables refer to it). Run inside a transaction; check the row count first.
-- If SQL says the table has an IDENTITY column: add SET IDENTITY_INSERT stock.dbo.Products ON;
-- before the INSERT (and OFF after), and list the columns explicitly instead of SELECT *.
-- BEGIN TRAN;
-- INSERT INTO stock.dbo.Products
-- SELECT r.*
-- FROM stock_recover.dbo.Products r
-- WHERE (r.product_name_ar LIKE N'%بانادول%' OR r.product_name_ar LIKE N'%بنادول%'
--        OR r.product_name_en LIKE N'%panadol%')
--   AND NOT EXISTS (SELECT 1 FROM stock.dbo.Products p WHERE p.product_id = r.product_id);
-- SELECT @@ROWCOUNT AS inserted;   -- must equal the step 3 count
-- COMMIT;                          -- or ROLLBACK if the count is wrong

-- If the row EXISTS but is only flagged (deleted='0' / active='0'): do not use SQL.
-- Re-activate it from the eStock program's item screen, so eStock writes its own log.

-- STEP 6: when finished, drop the temporary copy.
-- DROP DATABASE stock_recover;
