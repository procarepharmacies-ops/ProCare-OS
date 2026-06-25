-- ===========================================================================
-- ProCare OS — read-only reporting views (SQLite dialect)
-- ---------------------------------------------------------------------------
-- These curated views are the ONLY objects the Arabic AI assistant's
-- constrained text-to-SQL is allowed to read (see app/ai.py AI_VIEW_WHITELIST).
-- They never expose password hashes, salaries, or raw ledger rows. The same
-- views back several dashboard KPIs.
--
-- Data-quality rules baked in (docs/05):
--   * exclude returns        -> is_return = 0
--   * available stock only   -> amount > 0 AND not expired
--   * FEFO                    -> ORDER BY exp_date ASC at the call site
--
-- Portability note: "today" is date('now') here. On SQL Server, swap
-- date('now') -> CAST(GETDATE() AS date) and julianday(...) differences ->
-- DATEDIFF(day, ...). Names/columns are otherwise identical.
-- ===========================================================================

DROP VIEW IF EXISTS vw_branches;
CREATE VIEW vw_branches AS
SELECT branch_id, code, name_ar, name_en, is_pilot, is_active
FROM branches;

-- Per-branch, per-day net sales (returns excluded). The headline time series.
DROP VIEW IF EXISTS vw_daily_sales;
CREATE VIEW vw_daily_sales AS
SELECT s.branch_id,
       b.name_ar           AS branch_name_ar,
       b.name_en           AS branch_name_en,
       date(s.sale_date)   AS sale_day,
       COUNT(*)            AS bills_count,
       SUM(s.total_net)    AS revenue,
       SUM(s.cash_paid)    AS cash_collected,
       SUM(s.card_paid)    AS card_collected
FROM sales s
JOIN branches b ON b.branch_id = s.branch_id
WHERE s.is_return = 0
GROUP BY s.branch_id, b.name_ar, b.name_en, date(s.sale_date);

-- Per-line profit, returns excluded. Backs profit + top-product reporting.
DROP VIEW IF EXISTS vw_sale_line_profit;
CREATE VIEW vw_sale_line_profit AS
SELECT s.branch_id,
       date(s.sale_date)               AS sale_day,
       sl.product_id,
       p.name_ar                       AS product_name_ar,
       p.name_en                       AS product_name_en,
       sl.amount                       AS units,
       sl.total_sell                   AS revenue,
       (sl.amount * sl.buy_price)      AS cost,
       (sl.total_sell - sl.amount * sl.buy_price) AS profit
FROM sale_lines sl
JOIN sales s    ON s.sale_id = sl.sale_id
JOIN products p ON p.product_id = sl.product_id
WHERE s.is_return = 0 AND sl.is_return = 0;

-- Top products by revenue (all-time in the mirror; filter by day at call site).
DROP VIEW IF EXISTS vw_top_products;
CREATE VIEW vw_top_products AS
SELECT branch_id,
       product_id,
       product_name_ar,
       product_name_en,
       SUM(units)   AS units_sold,
       SUM(revenue) AS revenue,
       SUM(profit)  AS profit
FROM vw_sale_line_profit
GROUP BY branch_id, product_id, product_name_ar, product_name_en;

-- Available stock on hand, per product per branch (amount>0, not expired).
DROP VIEW IF EXISTS vw_stock_on_hand;
CREATE VIEW vw_stock_on_hand AS
SELECT sb.branch_id,
       sb.product_id,
       p.name_ar               AS product_name_ar,
       p.name_en               AS product_name_en,
       p.min_stock             AS min_stock,
       SUM(sb.amount)          AS qty_on_hand,
       SUM(sb.amount * sb.buy_price) AS stock_value
FROM stock_batches sb
JOIN products p ON p.product_id = sb.product_id
WHERE sb.amount > 0
  AND (p.has_expiry = 0 OR sb.exp_date IS NULL OR sb.exp_date > date('now'))
GROUP BY sb.branch_id, sb.product_id, p.name_ar, p.name_en, p.min_stock;

-- Low stock: on-hand below the product's minimum (reorder candidates).
DROP VIEW IF EXISTS vw_low_stock;
CREATE VIEW vw_low_stock AS
SELECT branch_id, product_id, product_name_ar, product_name_en,
       qty_on_hand, min_stock
FROM vw_stock_on_hand
WHERE qty_on_hand <= min_stock;

-- Expiry risk: live batches with their days-to-expiry + expected loss.
DROP VIEW IF EXISTS vw_expiry_risk;
CREATE VIEW vw_expiry_risk AS
SELECT sb.branch_id,
       sb.batch_id,
       sb.product_id,
       p.name_ar    AS product_name_ar,
       p.name_en    AS product_name_en,
       sb.exp_date  AS exp_date,
       sb.amount    AS qty_remaining,
       (sb.amount * sb.buy_price) AS expected_loss,
       CAST(julianday(sb.exp_date) - julianday(date('now')) AS INTEGER) AS days_to_expiry
FROM stock_batches sb
JOIN products p ON p.product_id = sb.product_id
WHERE sb.amount > 0
  AND p.has_expiry = 1
  AND sb.exp_date IS NOT NULL;

-- Customer debtors with an over-limit flag (the 61-over-limit problem made visible).
DROP VIEW IF EXISTS vw_customer_debtors;
CREATE VIEW vw_customer_debtors AS
SELECT customer_id,
       name_ar  AS customer_name_ar,
       name_en  AS customer_name_en,
       mobile,
       credit_limit,
       current_balance AS balance,
       (current_balance - credit_limit) AS over_limit_by,
       CASE WHEN current_balance > credit_limit AND credit_limit > 0 THEN 1 ELSE 0 END AS over_limit
FROM customers
WHERE current_balance > 0 AND is_deleted = 0;

-- Vendor payables (what the pharmacy owes suppliers).
DROP VIEW IF EXISTS vw_vendor_payables;
CREATE VIEW vw_vendor_payables AS
SELECT vendor_id,
       name_ar AS vendor_name_ar,
       name_en AS vendor_name_en,
       current_balance AS amount_owed
FROM vendors
WHERE current_balance > 0 AND is_active = 1;

-- Cashier performance (per cashier, per day; returns excluded).
DROP VIEW IF EXISTS vw_cashier_performance;
CREATE VIEW vw_cashier_performance AS
SELECT s.branch_id,
       date(s.sale_date) AS sale_day,
       s.cashier_id,
       e.name_ar         AS cashier_name_ar,
       e.name_en         AS cashier_name_en,
       COUNT(*)          AS bills,
       SUM(s.total_net)  AS revenue
FROM sales s
LEFT JOIN employees e ON e.employee_id = s.cashier_id
WHERE s.is_return = 0
GROUP BY s.branch_id, date(s.sale_date), s.cashier_id, e.name_ar, e.name_en;
