/* ===========================================================================
   ProCare OS — Pharmacy performance over time, audit & supplier analysis
   ---------------------------------------------------------------------------
   Runs directly on the NEW SQL Server Express ProCare database (after the
   eStock mirror / cut-over). These are the exact figures the backend
   (app/services/performance.py) and the Reports → Performance screen show —
   kept here so the owner can reproduce every number in SSMS.

   Scope knobs (edit once at the top):
     @today  : "now" (use CAST(GETDATE() AS date) in production).
     @years  : how many full calendar years back to analyse (default 5).
     @vendor : supplier to investigate (default the primary distributor).

   Data-quality rules baked in (docs/05):
     • sales metrics exclude returns          -> is_return = 0
     • available stock = amount > 0 AND not expired (exp_date > @today OR NULL)
     • cost/profit use the buy_price snapshot captured on each sale line

   SQL Server 2008 compatible: no DATEFROMPARTS / LAG (both 2012+). The Elsanta
   branch server is SQL Server 2008 — this script runs there unchanged.
   =========================================================================== */

DECLARE @today  date = CAST(GETDATE() AS date);      -- demo data: '2026-06-26'
DECLARE @years  int  = 5;
DECLARE @vendor nvarchar(100) = N'PharmaOverseas';   -- matches name_en or name_ar
-- Jan 1 of (year - years + 1), built without DATEFROMPARTS (2012+): compose the
-- YYYYMMDD literal and cast. Deterministic and 2008-safe.
DECLARE @from   date = CAST(CAST(YEAR(@today) - @years + 1 AS char(4)) + '0101' AS date);

/* ---------------------------------------------------------------------------
   A. FIVE-YEAR PERFORMANCE BY YEAR
   Revenue, gross profit & margin, invoices, returns, active customers, units,
   cash vs card, and purchasing spend — one row per calendar year.
   --------------------------------------------------------------------------- */
WITH sales_y AS (
    SELECT YEAR(s.sale_date) AS yr,
           COUNT(*)                               AS invoices,
           SUM(s.total_net)                       AS revenue,
           SUM(s.cash_paid)                       AS cash_collected,
           SUM(s.card_paid)                       AS card_collected,
           SUM(s.total_discount)                  AS discount_given,
           COUNT(DISTINCT s.customer_id)          AS active_customers
    FROM   sales s
    WHERE  s.is_return = 0 AND s.sale_date >= @from
    GROUP  BY YEAR(s.sale_date)
),
cogs_y AS (
    SELECT YEAR(s.sale_date) AS yr,
           SUM(sl.amount * sl.buy_price) AS cogs,
           SUM(sl.amount)                AS units_sold
    FROM   sale_lines sl
    JOIN   sales s ON s.sale_id = sl.sale_id
    WHERE  s.is_return = 0 AND s.sale_date >= @from
    GROUP  BY YEAR(s.sale_date)
),
returns_y AS (
    SELECT YEAR(s.sale_date) AS yr, COUNT(*) AS returns_count, SUM(s.total_net) AS returns_value
    FROM   sales s WHERE s.is_return = 1 AND s.sale_date >= @from
    GROUP  BY YEAR(s.sale_date)
),
new_cust_y AS (
    SELECT YEAR(created_at) AS yr, COUNT(*) AS new_customers
    FROM   customers WHERE is_deleted = 0 GROUP BY YEAR(created_at)
),
purch_y AS (
    SELECT YEAR(bill_date) AS yr, COUNT(*) AS purchase_orders,
           SUM(total_gross - total_discount) AS purchases_spend
    FROM   purchases WHERE is_return = 0 AND bill_date >= @from
    GROUP  BY YEAR(bill_date)
)
SELECT s.yr                                         AS [year],
       s.invoices,
       s.revenue,
       c.cogs,
       s.revenue - c.cogs                           AS gross_profit,
       CAST(100.0 * (s.revenue - c.cogs) / NULLIF(s.revenue, 0) AS DECIMAL(5,1)) AS margin_pct,
       c.units_sold,
       s.active_customers,
       ISNULL(nc.new_customers, 0)                  AS new_customers,
       ISNULL(r.returns_count, 0)                   AS returns,
       ISNULL(r.returns_value, 0)                   AS returns_value,
       s.cash_collected,
       s.card_collected,
       CAST(s.revenue / NULLIF(s.invoices, 0) AS DECIMAL(18,2)) AS avg_bill,
       ISNULL(p.purchase_orders, 0)                 AS purchase_orders,
       ISNULL(p.purchases_spend, 0)                 AS purchases_spend,
       -- Year-over-year revenue growth. LAG() is 2012+, so the previous year's
       -- revenue comes from a self-join on (yr - 1) instead — 2008-safe.
       CAST(100.0 * (s.revenue - s_prev.revenue)
             / NULLIF(s_prev.revenue, 0) AS DECIMAL(6,1)) AS revenue_growth_pct
FROM   sales_y s
LEFT   JOIN sales_y   s_prev ON s_prev.yr = s.yr - 1
LEFT   JOIN cogs_y    c  ON c.yr  = s.yr
LEFT   JOIN returns_y r  ON r.yr  = s.yr
LEFT   JOIN new_cust_y nc ON nc.yr = s.yr
LEFT   JOIN purch_y   p  ON p.yr  = s.yr
ORDER  BY s.yr;

/* ---------------------------------------------------------------------------
   A2. SAME, BY BRANCH — revenue, gross profit & invoices per branch per year
   (Main vs Elsanta). Drop the JOIN's year filter for an all-time comparison.
   --------------------------------------------------------------------------- */
SELECT b.name_ar AS branch, YEAR(s.sale_date) AS [year],
       COUNT(*)         AS invoices,
       SUM(s.total_net) AS revenue,
       SUM(s.total_net)
         - ISNULL((SELECT SUM(sl.amount * sl.buy_price)
                   FROM sale_lines sl JOIN sales s2 ON s2.sale_id = sl.sale_id
                   WHERE s2.is_return = 0 AND s2.branch_id = s.branch_id
                     AND YEAR(s2.sale_date) = YEAR(s.sale_date)), 0) AS gross_profit
FROM   sales s JOIN branches b ON b.branch_id = s.branch_id
WHERE  s.is_return = 0 AND s.sale_date >= @from
GROUP  BY b.name_ar, s.branch_id, YEAR(s.sale_date)
ORDER  BY branch, [year];

/* ---------------------------------------------------------------------------
   B. MONTHLY TREND (for the chart) — revenue, invoices, gross profit per month
   --------------------------------------------------------------------------- */
SELECT FORMAT(s.sale_date, 'yyyy-MM')          AS [month],
       COUNT(*)                                AS invoices,
       SUM(s.total_net)                        AS revenue,
       SUM(s.total_net)
         - ISNULL((SELECT SUM(sl.amount * sl.buy_price)
                   FROM sale_lines sl JOIN sales s2 ON s2.sale_id = sl.sale_id
                   WHERE s2.is_return = 0
                     AND FORMAT(s2.sale_date,'yyyy-MM') = FORMAT(s.sale_date,'yyyy-MM')), 0) AS gross_profit
FROM   sales s
WHERE  s.is_return = 0 AND s.sale_date >= @from
GROUP  BY FORMAT(s.sale_date, 'yyyy-MM')
ORDER  BY [month];

/* ---------------------------------------------------------------------------
   C. CURRENT STOCK LEVEL, VALUATION & CASH ON HAND (snapshot)
   --------------------------------------------------------------------------- */
SELECT
  (SELECT SUM(amount) FROM stock_batches
     WHERE amount > 0 AND (exp_date IS NULL OR exp_date > @today))               AS stock_on_hand_units,
  (SELECT SUM(amount * buy_price) FROM stock_batches
     WHERE amount > 0 AND (exp_date IS NULL OR exp_date > @today))               AS stock_value_at_cost,
  (SELECT SUM(amount * sell_price) FROM stock_batches
     WHERE amount > 0 AND (exp_date IS NULL OR exp_date > @today))               AS stock_value_at_retail,
  (SELECT SUM(amount * buy_price) FROM stock_batches
     WHERE amount > 0 AND exp_date IS NOT NULL AND exp_date <= @today)           AS expired_stock_value,
  (SELECT SUM(current_balance) FROM customers WHERE current_balance > 0)         AS receivables_from_customers,
  (SELECT SUM(current_balance) FROM vendors   WHERE current_balance > 0)         AS payables_to_vendors,
  (SELECT COUNT(*) FROM customers WHERE is_deleted = 0)                          AS registered_customers;

/* ---------------------------------------------------------------------------
   D. SUPPLIER PURCHASING INVESTIGATION — PharmaOverseas
   --------------------------------------------------------------------------- */
DECLARE @vendor_id int = (
    SELECT TOP 1 vendor_id FROM vendors
    WHERE name_en LIKE '%' + @vendor + '%' OR name_ar LIKE N'%' + @vendor + N'%'
    ORDER BY vendor_id);

-- D1. Spend / orders / items from this supplier, per year.
SELECT YEAR(p.bill_date) AS [year],
       COUNT(DISTINCT p.purchase_id)              AS orders,
       SUM(p.total_gross - p.total_discount)      AS spend,
       (SELECT SUM(pl.amount) FROM purchase_lines pl
          JOIN purchases pp ON pp.purchase_id = pl.purchase_id
          WHERE pp.vendor_id = @vendor_id AND pp.is_return = 0
            AND YEAR(pp.bill_date) = YEAR(p.bill_date)) AS items
FROM   purchases p
WHERE  p.vendor_id = @vendor_id AND p.is_return = 0 AND p.bill_date >= @from
GROUP  BY YEAR(p.bill_date)
ORDER  BY [year];

-- D2. Top products bought from this supplier (by spend).
SELECT TOP 10 pr.name_ar, pr.name_en,
       SUM(pl.amount)                 AS units,
       SUM(pl.amount * pl.buy_price)  AS spend
FROM   purchase_lines pl
JOIN   purchases p ON p.purchase_id = pl.purchase_id
JOIN   products  pr ON pr.product_id = pl.product_id
WHERE  p.vendor_id = @vendor_id AND p.is_return = 0 AND p.bill_date >= @from
GROUP  BY pr.product_id, pr.name_ar, pr.name_en
ORDER  BY spend DESC;

-- D3. Vendor ranking + share of total purchasing (context for the above).
SELECT v.name_ar, v.name_en,
       COUNT(DISTINCT p.purchase_id)         AS orders,
       SUM(p.total_gross - p.total_discount) AS spend,
       CAST(100.0 * SUM(p.total_gross - p.total_discount)
            / NULLIF((SELECT SUM(total_gross - total_discount) FROM purchases
                      WHERE is_return = 0 AND bill_date >= @from), 0) AS DECIMAL(5,1)) AS share_pct,
       v.current_balance                     AS current_payable
FROM   purchases p
JOIN   vendors   v ON v.vendor_id = p.vendor_id
WHERE  p.is_return = 0 AND p.bill_date >= @from
GROUP  BY v.vendor_id, v.name_ar, v.name_en, v.current_balance
ORDER  BY spend DESC;

-- D4. This supplier's spend split by branch (Main vs Elsanta).
SELECT b.name_ar AS branch,
       COUNT(DISTINCT p.purchase_id)         AS orders,
       SUM(p.total_gross - p.total_discount) AS spend
FROM   purchases p JOIN branches b ON b.branch_id = p.branch_id
WHERE  p.vendor_id = @vendor_id AND p.is_return = 0 AND p.bill_date >= @from
GROUP  BY b.name_ar
ORDER  BY spend DESC;

/* ---------------------------------------------------------------------------
   E. POST-SYNC DATA-QUALITY AUDIT
   One row per check; status ok / warn / fail. Run this straight after a sync.
   --------------------------------------------------------------------------- */
SELECT 'negative_stock' AS [check],
       (SELECT COUNT(*) FROM stock_batches WHERE amount < 0) AS value,
       CASE WHEN (SELECT COUNT(*) FROM stock_batches WHERE amount < 0) = 0
            THEN 'ok' ELSE 'fail' END AS status
UNION ALL
SELECT 'expired_in_stock_products',
       (SELECT COUNT(DISTINCT product_id) FROM stock_batches
          WHERE amount > 0 AND exp_date IS NOT NULL AND exp_date <= @today),
       CASE WHEN (SELECT COUNT(*) FROM stock_batches
                    WHERE amount > 0 AND exp_date IS NOT NULL AND exp_date <= @today) = 0
            THEN 'ok' ELSE 'warn' END
UNION ALL
SELECT 'orphan_batches',
       (SELECT COUNT(*) FROM stock_batches sb
          LEFT JOIN products p ON p.product_id = sb.product_id
          WHERE p.product_id IS NULL OR p.is_deleted = 1),
       CASE WHEN (SELECT COUNT(*) FROM stock_batches sb
                    LEFT JOIN products p ON p.product_id = sb.product_id
                    WHERE p.product_id IS NULL OR p.is_deleted = 1) = 0
            THEN 'ok' ELSE 'warn' END
UNION ALL
SELECT 'zero_line_sales',
       (SELECT COUNT(*) FROM sales s
          WHERE s.is_return = 0
            AND NOT EXISTS (SELECT 1 FROM sale_lines sl WHERE sl.sale_id = s.sale_id)),
       CASE WHEN (SELECT COUNT(*) FROM sales s
                    WHERE s.is_return = 0
                      AND NOT EXISTS (SELECT 1 FROM sale_lines sl WHERE sl.sale_id = s.sale_id)) = 0
            THEN 'ok' ELSE 'warn' END
UNION ALL
SELECT 'price_below_cost',
       (SELECT COUNT(*) FROM products WHERE is_active = 1 AND buy_price > 0 AND sell_price < buy_price),
       CASE WHEN (SELECT COUNT(*) FROM products
                    WHERE is_active = 1 AND buy_price > 0 AND sell_price < buy_price) = 0
            THEN 'ok' ELSE 'warn' END
UNION ALL
SELECT 'customers_over_limit',
       (SELECT COUNT(*) FROM customers WHERE credit_limit > 0 AND current_balance > credit_limit),
       CASE WHEN (SELECT COUNT(*) FROM customers
                    WHERE credit_limit > 0 AND current_balance > credit_limit) = 0
            THEN 'ok' ELSE 'warn' END;
