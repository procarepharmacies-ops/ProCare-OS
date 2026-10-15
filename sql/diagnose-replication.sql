-- diagnose-replication.sql  (READ-ONLY, SQL Server 2008-safe)
-- Run on the ELSANTA (head / is_server) server, database `stock`.
-- Why does F2 on Elsanta show a stale Mashala stock while F2 on Mashala is exact,
-- and why is Mashala purchase_details "stalled 552h" (last row 2026-09-20 17:03)?
-- Send ALL result grids back (Copy with Headers). No writes anywhere.

-- 1) eStock's own replication watermarks per branch: when each stream last
--    arrived from each branch. A stream stuck at 2026-09-20 = replication stopped.
SELECT * FROM Branches;   -- 2 rows; read the rep_*_date columns

-- 2) What the replicated stock table holds, per branch/store. This is the table
--    Elsanta's F2 reads for Mashala. MAX(update_date) = how stale it is.
SELECT branch_id, store_id, COUNT(*) AS batches, SUM(amount) AS total_amount,
       MAX(insert_date) AS last_insert, MAX(update_date) AS last_update
FROM Branches_Product_Amount
GROUP BY branch_id, store_id
ORDER BY branch_id, store_id;

-- 3) Elsanta's OWN live stock per store (compare with 2 to see overlap / double count).
SELECT store_id, COUNT(*) AS batches, SUM(amount) AS total_amount,
       MAX(insert_date) AS last_insert, MAX(update_date) AS last_update
FROM Product_Amount
GROUP BY store_id
ORDER BY store_id;

-- 4) Replicated purchase lines: last arrival per branch (this is the stalled table).
SELECT branch_id, COUNT(*) AS lines, MAX(insert_date) AS last_insert,
       MAX(update_date) AS last_update
FROM Branches_purchase_details
GROUP BY branch_id
ORDER BY branch_id;

-- 5) Same for replicated sales/purchase headers: is ONLY purchase_details stuck,
--    or has the whole feed from Mashala stopped?
SELECT branch_id, COUNT(*) AS bills, MAX(insert_date) AS last_insert
FROM Branches_purchase_header
GROUP BY branch_id
ORDER BY branch_id;

-- 6) The one product from the sales screen, as Elsanta sees it per branch.
SELECT bpa.branch_id, bpa.store_id, bpa.counter_id, bpa.amount, bpa.exp_date,
       bpa.update_date
FROM Branches_Product_Amount bpa
JOIN Products p ON p.product_id = bpa.product_id
WHERE p.product_code = N'51293'
ORDER BY bpa.branch_id, bpa.store_id, bpa.exp_date;
