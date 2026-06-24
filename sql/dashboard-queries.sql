/* ===========================================================================
   ProCare OS — Read-only dashboard & KPI queries
   ---------------------------------------------------------------------------
   Source: eStock Full-Picture Report. These run against the eStock `stock`
   database during the mirror phase, and (with table renames) against ProCare's
   own schema after cutover.

   Data-quality rules baked in:
     • bill_date is often NULL  -> use insert_date / COALESCE(bill_date, insert_date)
     • exclude returns          -> AND (back IS NULL OR back <> 'Y')
     • available stock only     -> amount > 0 AND not expired
     • FEFO                     -> ORDER BY exp_date ASC
   =========================================================================== */

-- 1. TODAY'S REVENUE
SELECT COUNT(*) AS bills_count,
       ISNULL(SUM(total_bill_net), 0) AS revenue,
       ISNULL(SUM(bill_cash), 0)      AS cash_collected
FROM   Sales_header
WHERE  CONVERT(date, insert_date) = CONVERT(date, GETDATE())
  AND  (back IS NULL OR back <> 'Y');

-- 2. THIS MONTH vs LAST MONTH
SELECT SUM(CASE WHEN MONTH(insert_date) = MONTH(GETDATE())     THEN total_bill_net ELSE 0 END) AS this_month,
       SUM(CASE WHEN MONTH(insert_date) = MONTH(GETDATE()) - 1 THEN total_bill_net ELSE 0 END) AS last_month
FROM   Sales_header
WHERE  YEAR(insert_date) = YEAR(GETDATE());

-- 3. TOP 10 SELLING PRODUCTS TODAY
SELECT TOP 10 p.product_name_ar,
       SUM(sd.amount)     AS units_sold,
       SUM(sd.total_sell) AS revenue
FROM   Sales_details sd
JOIN   Sales_header  sh ON sd.sales_id   = sh.sales_id
JOIN   Products      p  ON sd.product_id = p.product_id
WHERE  CONVERT(date, sh.insert_date) = CONVERT(date, GETDATE())
  AND  (sh.back IS NULL OR sh.back <> 'Y')
GROUP  BY p.product_name_ar
ORDER  BY revenue DESC;

-- 4. EXPIRING IN NEXT 30 DAYS
SELECT p.product_name_ar, pa.exp_date, SUM(pa.amount) AS qty_remaining
FROM   Product_Amount pa
JOIN   Products p ON pa.product_id = p.product_id
WHERE  pa.exp_date BETWEEN GETDATE() AND DATEADD(day, 30, GETDATE())
  AND  pa.amount > 0
GROUP  BY p.product_name_ar, pa.exp_date
ORDER  BY pa.exp_date ASC;

-- 5. LOW STOCK ALERTS (< 10 units total)
SELECT p.product_name_ar, SUM(pa.amount) AS total_qty
FROM   Product_Amount pa
JOIN   Products p ON pa.product_id = p.product_id
WHERE  pa.amount > 0
GROUP  BY p.product_name_ar, p.product_id
HAVING SUM(pa.amount) < 10
ORDER  BY total_qty ASC;

-- 6. TOP CUSTOMER DEBTORS
SELECT TOP 10 customer_name_ar, customer_current_money AS balance
FROM   Customer
WHERE  customer_current_money > 0
ORDER  BY customer_current_money DESC;

-- 7. VENDOR PAYABLES (what you owe)
SELECT TOP 10 vendor_name_ar, vendor_current_money AS amount_owed
FROM   Vendor
WHERE  vendor_current_money > 0
ORDER  BY vendor_current_money DESC;

-- 8. DAILY SALES (last 30 days)
SELECT CONVERT(date, insert_date) AS sale_date,
       COUNT(*)            AS bills_count,
       SUM(total_bill_net) AS revenue
FROM   Sales_header
WHERE  insert_date >= DATEADD(day, -30, GETDATE())
  AND  (back IS NULL OR back <> 'Y')
GROUP  BY CONVERT(date, insert_date)
ORDER  BY sale_date ASC;

-- 9. CASHIER PERFORMANCE TODAY
SELECT sh.cashier_id, e.emp_name_ar,
       COUNT(*)               AS bills,
       SUM(sh.total_bill_net) AS revenue
FROM   Sales_header sh
LEFT   JOIN Employee e ON sh.cashier_id = e.username
WHERE  CONVERT(date, sh.insert_date) = CONVERT(date, GETDATE())
GROUP  BY sh.cashier_id, e.emp_name_ar
ORDER  BY revenue DESC;

-- 10. HOURLY SALES TODAY (peak-hours)
SELECT DATEPART(hour, insert_date) AS hour_of_day,
       COUNT(*)            AS bills,
       SUM(total_bill_net) AS revenue
FROM   Sales_header
WHERE  CONVERT(date, insert_date) = CONVERT(date, GETDATE())
GROUP  BY DATEPART(hour, insert_date)
ORDER  BY hour_of_day;

-- 11. STOCK LOOKUP — FEFO (first expire, first out)
SELECT pa.counter_id, pa.exp_date, pa.amount AS available_qty,
       pa.sell_price, pa.buy_price,
       p.product_name_ar, p.product_name_en, p.product_unit1
FROM   Product_Amount pa
JOIN   Products p ON pa.product_id = p.product_id
WHERE  pa.product_id = @product_id
  AND  pa.store_id   = @store_id
  AND  pa.amount     > 0
  AND  (pa.exp_date > GETDATE() OR p.product_has_expire = 'N')
ORDER  BY pa.exp_date ASC;

-- 12. CUSTOMER CREDIT CHECK
SELECT customer_name_ar,
       customer_max_money     AS credit_limit,
       customer_current_money AS current_balance,
       (customer_max_money - customer_current_money) AS available_credit
FROM   Customer
WHERE  customer_id = @customer_id;

-- 13. PROFIT PER PERIOD
SELECT SUM(sd.total_sell)                                  AS revenue,
       SUM(sd.amount * sd.buy_price)                       AS cost,
       SUM(sd.total_sell) - SUM(sd.amount * sd.buy_price)  AS gross_profit
FROM   Sales_header  sh
JOIN   Sales_details sd ON sh.sales_id = sd.sales_id
WHERE  COALESCE(sh.bill_date, sh.insert_date) BETWEEN @from_date AND @to_date
  AND  (sh.back IS NULL OR sh.back <> 'Y');
