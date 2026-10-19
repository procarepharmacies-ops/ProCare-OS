-- diagnose-missing-product.sql   (READ-ONLY, SQL Server 2008-safe)
-- "Panadol disappeared": find every Panadol row in eStock (`stock`) and in ProCare,
-- and read eStock's own logs to see who changed / deleted it and when.
-- Run on the server that has the database where it went missing (Elsanta has both).
-- Send every grid back (Ctrl+T = results as text, then F5, then copy all). Changes nothing.
--
-- How ProCare reads eStock's flags (Products ONLY, audited 2026-07):
--   deleted = '1'  -> normal, sellable product   (the name is inverted in eStock)
--   deleted = '0'  -> REMOVED  (ProCare hides it on the next sync)
--   active  = '0'  -> inactive

USE stock;

-- 1) Every Panadol product in eStock with its flags and last edit (who/when).
SELECT product_id, product_code, product_name_ar, product_name_en, deleted, active,
       insert_date, insert_uid, up_date, up_uid
FROM Products
WHERE product_name_ar LIKE N'%بانادول%' OR product_name_ar LIKE N'%بنادول%'
   OR product_name_en LIKE N'%panadol%'
ORDER BY up_date DESC;

-- 2) eStock's product EDIT LOG for those products (newest first). Look for the row
--    where deleted/active flipped, or the name/code changed, and the user (up_uid).
SELECT TOP 100 e.product_edit_id, e.product_id, e.insert_type, e.product_code,
       e.product_name_ar, e.deleted, e.active, e.sell_price,
       e.insert_date, e.insert_uid, e.up_date, e.up_uid, e.notes
FROM Branches_products_edit e
WHERE e.product_id IN (SELECT product_id FROM Products
                       WHERE product_name_ar LIKE N'%بانادول%' OR product_name_ar LIKE N'%بنادول%'
                          OR product_name_en LIKE N'%panadol%')
   OR e.product_name_ar LIKE N'%بانادول%' OR e.product_name_ar LIKE N'%بنادول%'
   OR e.product_name_en LIKE N'%panadol%'
ORDER BY e.product_edit_id DESC;

-- 3) Price / unit change log.
SELECT TOP 50 c.product_change_id, c.product_id, c.class, c.sell_price_old, c.sell_price,
       c.unit1_2_old, c.unit1_2, c.insert_uid, c.insert_date
FROM Product_Changes c
WHERE c.product_id IN (SELECT product_id FROM Products
                       WHERE product_name_ar LIKE N'%بانادول%' OR product_name_ar LIKE N'%بنادول%'
                          OR product_name_en LIKE N'%panadol%')
ORDER BY c.product_change_id DESC;

-- 4) Stock movement log (did the stock go to zero, and by which form/user?).
SELECT TOP 50 a.id, a.product_id, a.store_id, a.old_amount, a.new_amount, a.exp_date,
       a.form_type, a.form_notice, a.in_type, a.insert_uid, a.insert_date
FROM Product_amount_Change a
WHERE a.product_id IN (SELECT product_id FROM Products
                       WHERE product_name_ar LIKE N'%بانادول%' OR product_name_ar LIKE N'%بنادول%'
                          OR product_name_en LIKE N'%panadol%')
ORDER BY a.id DESC;

-- 5) Current stock in eStock.
SELECT pa.product_id, pa.store_id, SUM(pa.amount) AS amount
FROM Product_Amount pa
WHERE pa.product_id IN (SELECT product_id FROM Products
                        WHERE product_name_ar LIKE N'%بانادول%' OR product_name_ar LIKE N'%بنادول%'
                           OR product_name_en LIKE N'%panadol%')
GROUP BY pa.product_id, pa.store_id;

-- ---------------------------------------------------------------------------
-- ProCare side (skip if this server has no ProCare database).
-- ---------------------------------------------------------------------------
USE ProCare;

-- 6) Panadol in ProCare: is_deleted = 1 hides it from POS/search.
SELECT product_id, code, name_ar, name_en, is_deleted, is_active
FROM products
WHERE name_ar LIKE N'%بانادول%' OR name_ar LIKE N'%بنادول%' OR name_en LIKE N'%panadol%';

-- 7) Its stock per branch in ProCare.
SELECT b.product_id, b.branch_id, SUM(b.amount) AS amount, COUNT(*) AS batches
FROM stock_batches b
JOIN products p ON p.product_id = b.product_id
WHERE p.name_ar LIKE N'%بانادول%' OR p.name_ar LIKE N'%بنادول%' OR p.name_en LIKE N'%panadol%'
GROUP BY b.product_id, b.branch_id;
