-- diagnose-replication-elsanta.sql   (READ-ONLY, SQL Server 2008-safe)
-- RUN ON: the ELSANTA server (head / is_server), database `stock`.
-- Question: why did replication Mashala -> Elsanta stop (monitor: Mashala
-- purchase_details last row 2026-09-20 17:03) and why does Elsanta's F2 show a
-- stale Mashala stock? Send every result grid back (Copy with Headers).
-- No writes anywhere. ProCare never edits rep_* watermarks or Branches_* tables.
-- Pair with diagnose-replication-mashala.sql run on the Mashala server.

USE stock;   -- the eStock database is named `stock` (NOT ProCare)

-- 1) eStock's own replication watermarks per branch + the IPs it connects to.
--    A stream stuck at 2026-09-20 = that stream stopped. branch_ip1/ip2 must
--    still be Mashala's real address.
SELECT * FROM Branches;

-- 2) Replicated stock Elsanta holds per branch/store (what Elsanta's F2 reads
--    for Mashala). MAX(update_date) = how stale it is.
SELECT branch_id, store_id, COUNT(*) AS batches, SUM(amount) AS total_amount,
       MAX(insert_date) AS last_insert, MAX(update_date) AS last_update
FROM Branches_Product_Amount
GROUP BY branch_id, store_id
ORDER BY branch_id, store_id;

-- 3) Elsanta's OWN live stock per store (compare with 2 for overlap / double count).
SELECT store_id, COUNT(*) AS batches, SUM(amount) AS total_amount,
       MAX(insert_date) AS last_insert, MAX(update_date) AS last_update
FROM Product_Amount
GROUP BY store_id
ORDER BY store_id;

-- 4) Last replicated purchase lines / bills received per branch (the stalled stream).
SELECT branch_id, COUNT(*) AS lines, MAX(details_id) AS last_details_id,
       MAX(purchase_id) AS last_purchase_id, MAX(insert_date) AS last_insert
FROM Branches_purchase_details GROUP BY branch_id ORDER BY branch_id;

SELECT branch_id, COUNT(*) AS bills, MAX(purchase_id) AS last_purchase_id,
       MAX(insert_date) AS last_insert
FROM Branches_purchase_header GROUP BY branch_id ORDER BY branch_id;

-- 5) The sales-screen product (51293) as Elsanta sees it per branch.
SELECT bpa.branch_id, bpa.store_id, bpa.counter_id, bpa.amount, bpa.exp_date, bpa.update_date
FROM Branches_Product_Amount bpa
JOIN Products p ON p.product_id = bpa.product_id
WHERE p.product_code = N'51293'
ORDER BY bpa.branch_id, bpa.store_id, bpa.exp_date;

-- 6) Disk and log health (a full disk or log stops writes silently).
EXEC master..xp_fixeddrives;                      -- free MB per drive
DBCC SQLPERF(LOGSPACE);                           -- log size / % used per database
SELECT name, recovery_model_desc, log_reuse_wait_desc, state_desc FROM sys.databases;
SELECT DB_NAME(database_id) AS db, type_desc, size * 8 / 1024 AS size_mb
FROM sys.master_files ORDER BY size_mb DESC;
