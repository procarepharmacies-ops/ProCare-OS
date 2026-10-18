-- diagnose-replication-mashala.sql   (READ-ONLY, SQL Server 2008-safe)
-- RUN ON: the MASHALA server, database `stock`.
-- Question: which purchase lines recorded at Mashala never reached Elsanta, and
-- is one of them a "poison row" blocking the replication stream? Send every
-- result grid back (Copy with Headers). No writes anywhere.
-- Pair with diagnose-replication-elsanta.sql run on the Elsanta server.

USE stock;   -- the eStock database is named `stock` (NOT ProCare)

DECLARE @since DATETIME = '2026-09-20 17:00:00';   -- just before the last replicated row

-- 1) Is Mashala still recording purchases itself?
SELECT TOP 10 purchase_id, bill_date, insert_date FROM Purchase_header ORDER BY purchase_id DESC;
SELECT TOP 10 details_id, purchase_id, product_id, insert_date FROM Purchase_details ORDER BY details_id DESC;

-- 2) Lines recorded after the last row Elsanta has: these never arrived. A bad
--    row usually sits right at the start of this list.
SELECT COUNT(*) AS pending_lines, MIN(insert_date) AS first_pending, MAX(insert_date) AS last_pending
FROM Purchase_details WHERE insert_date >= @since;

SELECT TOP 30 d.details_id, d.purchase_id, d.product_id, d.counter_id, d.amount,
       d.buy_price, d.sell_price, d.exp_date, d.insert_uid, d.insert_date
FROM Purchase_details d
WHERE d.insert_date >= @since
ORDER BY d.insert_date, d.details_id;

-- 3) Pending lines whose product or purchase header is missing.
SELECT d.details_id, d.purchase_id, d.product_id
FROM Purchase_details d
WHERE d.insert_date >= @since
  AND (NOT EXISTS (SELECT 1 FROM Products p WHERE p.product_id = d.product_id)
       OR NOT EXISTS (SELECT 1 FROM Purchase_header h WHERE h.purchase_id = d.purchase_id));

-- 4) Odd values among pending lines (NULL / negative / absurd).
SELECT d.details_id, d.purchase_id, d.product_id, d.amount, d.buy_price, d.sell_price
FROM Purchase_details d
WHERE d.insert_date >= @since
  AND (d.amount IS NULL OR d.amount < 0 OR d.amount > 100000
       OR d.buy_price IS NULL OR d.buy_price < 0 OR d.sell_price IS NULL OR d.sell_price < 0);

-- 5) Mashala's own live stock per store, and the sales-screen product (51293).
--    Compare with Elsanta's grid 2/5: the difference is the stale replicated copy.
SELECT store_id, COUNT(*) AS batches, SUM(amount) AS total_amount, MAX(update_date) AS last_update
FROM Product_Amount GROUP BY store_id ORDER BY store_id;

SELECT pa.store_id, pa.counter_id, pa.amount, pa.exp_date, pa.update_date
FROM Product_Amount pa
JOIN Products p ON p.product_id = pa.product_id
WHERE p.product_code = N'51293'
ORDER BY pa.store_id, pa.exp_date;

-- 6) Disk and log health (a full disk or log stops writes silently).
EXEC master..xp_fixeddrives;                      -- free MB per drive
DBCC SQLPERF(LOGSPACE);                           -- log size / % used per database
SELECT name, recovery_model_desc, log_reuse_wait_desc, state_desc FROM sys.databases;
SELECT DB_NAME(database_id) AS db, type_desc, size * 8 / 1024 AS size_mb
FROM sys.master_files ORDER BY size_mb DESC;
