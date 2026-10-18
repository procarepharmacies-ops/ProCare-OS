-- diagnose-unit-balance.sql  (READ-ONLY, SQL Server 2008-safe, schema-agnostic)
-- Why does one product code show different balances on the eStock sales screen?
-- Run on the branch server (e.g. Mashala) against the eStock database, then
-- send ALL result grids back. Change @code to the product being checked.
-- Uses SELECT * and INFORMATION_SCHEMA so it works whatever the column names are.

USE stock;   -- the eStock database is named `stock` (NOT ProCare)

DECLARE @code NVARCHAR(50) = N'51293';

-- 1) The product row, every column (look for unit / factor / pack columns).
SELECT * FROM Products WHERE product_code = @code;

-- 2) Columns of Products that look unit-related (name tells us where the
--    big/small factor lives on THIS database).
SELECT COLUMN_NAME, DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'Products'
  AND (COLUMN_NAME LIKE '%unit%' OR COLUMN_NAME LIKE '%no2%'
       OR COLUMN_NAME LIKE '%per%' OR COLUMN_NAME LIKE '%pack%'
       OR COLUMN_NAME LIKE '%factor%' OR COLUMN_NAME LIKE '%small%'
       OR COLUMN_NAME LIKE '%big%');

-- 3) Any OTHER table that has a unit/factor column (separate units table?).
SELECT TABLE_NAME, COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME <> 'Products'
  AND (COLUMN_NAME LIKE '%unit%' OR COLUMN_NAME LIKE '%no2per1%'
       OR COLUMN_NAME LIKE '%factor%')
ORDER BY TABLE_NAME, COLUMN_NAME;

-- 4) Stored stock rows for the product, every column. 465.12 => the store
--    keeps SMALL units; 12.92 => BIG units; both => mixed storage.
SELECT pa.*
FROM Product_Amount pa
JOIN Products p ON p.product_id = pa.product_id
WHERE p.product_code = @code;

-- 5) Same, per-branch stock table if present (ignore the error if it does not exist).
SELECT bpa.*
FROM Branches_Product_Amount bpa
JOIN Products p ON p.product_id = bpa.product_id
WHERE p.product_code = @code;
