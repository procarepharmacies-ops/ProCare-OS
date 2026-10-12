-- diagnose-unit-balance.sql  (READ-ONLY, SQL Server 2008-safe)
-- Why does one product code show different balances on the eStock sales screen?
-- Run on the branch server (e.g. Mashala) against the eStock database, then
-- send the three result sets back. Change @code to the product being checked.

DECLARE @code NVARCHAR(50) = N'51293';

-- 1) Unit definition: factor = small units per big unit (e.g. 36 pieces/box).
SELECT product_id, product_code, product_name,
       product_unit1 AS unit_big, product_unit2 AS unit_small,
       product_no2per1 AS unit_factor
FROM Products
WHERE product_code = @code;

-- 2) Stored stock rows. If amounts look like 465.12 the store keeps SMALL units;
--    if 12.92 it keeps BIG units. Mixed rows across batches/stores = real data
--    problem (ProCare mirrors these amounts as-is, see etl._load_stock).
SELECT pa.*
FROM Product_Amount pa
JOIN Products p ON p.product_id = pa.product_id
WHERE p.product_code = @code;

-- 3) Every product whose big/small ratio could be mistaken for a unit mix-up
--    (factor > 1) AND that has stock rows with fractional big-unit amounts.
SELECT TOP 50 p.product_code, p.product_name, p.product_no2per1 AS unit_factor,
       SUM(pa.amount) AS total_amount
FROM Products p
JOIN Product_Amount pa ON pa.product_id = p.product_id
WHERE p.product_no2per1 > 1
GROUP BY p.product_code, p.product_name, p.product_no2per1
HAVING SUM(pa.amount) <> ROUND(SUM(pa.amount), 0)
ORDER BY SUM(pa.amount) DESC;
