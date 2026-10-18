-- diagnose-replication-stall.sql  (READ-ONLY, SQL Server 2008-safe)
-- Why did eStock replication Mashala -> Elsanta stop? The monitor says only
-- Mashala `purchase_details` is stalled (last row 2026-09-20 17:03) while the
-- branch heartbeat keeps moving, so look for ONE blocked stream, not a dead link.
-- Run PART A on ELSANTA and PART B on MASHALA, both on database `stock`.
-- Send every grid back (Copy with Headers). No writes anywhere. ProCare never
-- edits eStock's rep_* watermarks or Branches_* tables.

USE stock;   -- the eStock database is named `stock` (NOT ProCare)

DECLARE @since DATETIME = '2026-09-20 17:00:00';   -- just before the last replicated row

------------------------------------------------------------------------------
-- PART A  (run on ELSANTA)
------------------------------------------------------------------------------
-- A1) What Elsanta last received from each branch, per stream.
SELECT branch_id, COUNT(*) AS lines, MAX(details_id) AS last_details_id,
       MAX(purchase_id) AS last_purchase_id, MAX(insert_date) AS last_insert
FROM Branches_purchase_details GROUP BY branch_id ORDER BY branch_id;

SELECT branch_id, COUNT(*) AS bills, MAX(purchase_id) AS last_purchase_id,
       MAX(insert_date) AS last_insert
FROM Branches_purchase_header GROUP BY branch_id ORDER BY branch_id;

-- A2) The watermarks eStock keeps for the replication, and the IPs it connects to.
--     branch_ip1/ip2 must still be Mashala's real address (a changed router /
--     static IP stops replication silently).
SELECT branch_id, branch_name, active, branch_ip1, branch_ip2,
       rep_last_purchase_id, rep_purchase_date, rep_last_pa_id, rep_last_pa_date
FROM Branches;

------------------------------------------------------------------------------
-- PART B  (run on MASHALA)
------------------------------------------------------------------------------
-- B1) Newest purchases at Mashala itself: is it still recording them?
SELECT TOP 10 purchase_id, bill_date, insert_date FROM Purchase_header ORDER BY purchase_id DESC;
SELECT TOP 10 details_id, purchase_id, product_id, insert_date FROM Purchase_details ORDER BY details_id DESC;

-- B2) Lines recorded at Mashala after the last row Elsanta has: these are the
--     ones that never arrived. A "poison row" (bad product, NULL/negative or
--     absurd amount/price, orphan purchase_id) usually sits right at the start.
SELECT COUNT(*) AS pending_lines, MIN(insert_date) AS first_pending, MAX(insert_date) AS last_pending
FROM Purchase_details WHERE insert_date >= @since;

SELECT TOP 30 d.details_id, d.purchase_id, d.product_id, d.counter_id, d.amount,
       d.buy_price, d.sell_price, d.exp_date, d.insert_uid, d.insert_date
FROM Purchase_details d
WHERE d.insert_date >= @since
ORDER BY d.insert_date, d.details_id;

-- B3) Pending lines whose product or header is missing (breaks any key check).
SELECT d.details_id, d.purchase_id, d.product_id
FROM Purchase_details d
WHERE d.insert_date >= @since
  AND (NOT EXISTS (SELECT 1 FROM Products p WHERE p.product_id = d.product_id)
       OR NOT EXISTS (SELECT 1 FROM Purchase_header h WHERE h.purchase_id = d.purchase_id));

-- B4) Odd values among pending lines.
SELECT d.details_id, d.purchase_id, d.product_id, d.amount, d.buy_price, d.sell_price
FROM Purchase_details d
WHERE d.insert_date >= @since
  AND (d.amount IS NULL OR d.amount < 0 OR d.amount > 100000
       OR d.buy_price IS NULL OR d.buy_price < 0 OR d.sell_price IS NULL OR d.sell_price < 0);

------------------------------------------------------------------------------
-- BOTH SERVERS: disk and log health (a full disk or log stops writes silently)
------------------------------------------------------------------------------
EXEC master..xp_fixeddrives;                      -- free MB per drive
DBCC SQLPERF(LOGSPACE);                           -- log size / % used per database

SELECT name, recovery_model_desc, log_reuse_wait_desc, state_desc
FROM sys.databases;

SELECT DB_NAME(database_id) AS db, type_desc, size * 8 / 1024 AS size_mb
FROM sys.master_files
ORDER BY size_mb DESC;
