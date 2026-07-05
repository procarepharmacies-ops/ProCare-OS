# Cash-Flow Audit SQL Pack — PharmaOverseas & Branch Treasuries

Companion to the **Official Audit Report** (Elsanta & Mas-hala). ProCare's dev
database here is demo data, so the exact figures MUST come from the live
eStock SQL Server on the pharmacy PC. Open **SSMS → the `stock` database** and
run these read-only queries; paste each result into the matching field of the
report. Every query is SELECT-only.

> The vendor name in eStock may be stored in Arabic (e.g. `فارما اوفرسيز`).
> Run query 0 first to find the exact `vendor_id`, then replace `@VENDOR_ID`
> everywhere below.

```sql
-- 0) Find PharmaOverseas
SELECT vendor_id, vendor_name_ar, vendor_name_en,
       vendor_current_money AS we_owe_now, vendor_max_money AS credit_limit
FROM Vendor
WHERE vendor_name_ar LIKE N'%فارما%' OR vendor_name_en LIKE '%overseas%';
```

```sql
-- 1) PharmaOverseas purchases — last 3 months, per branch/store
DECLARE @VENDOR_ID decimal = 0;  -- from query 0
SELECT store_id,
       COUNT(*)                   AS invoices,
       SUM(total_bill)            AS gross,
       SUM(bill_disc_money)       AS invoice_discounts,
       SUM(total_bill - ISNULL(bill_disc_money,0) + ISNULL(bill_tax,0)) AS net_payable
FROM Purchase_header
WHERE vendor_id = @VENDOR_ID
  AND bill_date >= DATEADD(month, -3, GETDATE())
  AND (back IS NULL OR back <> 'Y')
GROUP BY store_id;

-- 1b) The individual invoices (for the report annex)
SELECT purchase_id, store_id, bill_date, bill_number, total_bill,
       bill_disc_per, bill_disc_money, bill_tax
FROM Purchase_header
WHERE vendor_id = @VENDOR_ID
  AND bill_date >= DATEADD(month, -3, GETDATE())
ORDER BY bill_date;
```

```sql
-- 2) What we PAID PharmaOverseas in the same window (vendor ledger)
DECLARE @VENDOR_ID decimal = 0;
SELECT *
FROM Gedo_Vendors
WHERE vendor_id = @VENDOR_ID
  AND
 /* adapt the date column name — commonly gedo_date/insert_date */
      gedo_date >= DATEADD(month, -3, GETDATE())
ORDER BY gedo_date;
-- Purchases (1.net_payable) − payments here = growth of the debt.
```

```sql
-- 3) Revenue per branch — last 3 months (use insert_date: bill_date is NULL-bugged)
SELECT store_id,
       COUNT(*)            AS bills,
       SUM(total_bill_net) AS revenue,
       SUM(bill_cash)      AS cash_collected
FROM Sales_header
WHERE insert_date >= DATEADD(month, -3, GETDATE())
  AND (back IS NULL OR back <> 'Y')
GROUP BY store_id;

-- 3b) Gross profit per branch (revenue − cost at sale time)
SELECT sh.store_id,
       SUM(sd.total_sell)                        AS revenue,
       SUM(sd.amount * sd.buy_price)             AS cogs,
       SUM(sd.total_sell) - SUM(sd.amount*sd.buy_price) AS gross_profit
FROM Sales_details sd
JOIN Sales_header sh ON sh.sales_id = sd.sales_id
WHERE sh.insert_date >= DATEADD(month, -3, GETDATE())
  AND (sh.back IS NULL OR sh.back <> 'Y')
GROUP BY sh.store_id;
```

```sql
-- 4) Purchases vs sales ratio — ALL vendors (is buying outrunning selling?)
SELECT p.store_id,
       (SELECT SUM(total_bill) FROM Purchase_header
         WHERE store_id = p.store_id
           AND bill_date >= DATEADD(month,-3,GETDATE())
           AND (back IS NULL OR back <> 'Y'))            AS purchases_3m,
       (SELECT SUM(total_bill_net) FROM Sales_header
         WHERE store_id = p.store_id
           AND insert_date >= DATEADD(month,-3,GETDATE())
           AND (back IS NULL OR back <> 'Y'))            AS sales_3m
FROM (SELECT DISTINCT store_id FROM Purchase_header) p;
-- Healthy: purchases ≈ 70–80% of sales. Above 85% = cash is being converted
-- into shelf stock faster than the shelf converts back into cash.
```

```sql
-- 5) Cash desk closes — expected vs counted, last 3 months
SELECT store_id, COUNT(*) AS closures /* add the table's expected/counted/variance columns */
FROM Cash_disk_close
WHERE  /* date column */ insert_date >= DATEADD(month, -3, GETDATE())
GROUP BY store_id;
-- Any recurring negative variance is direct cash leakage.
```

```sql
-- 6) Treasury movement between branches — last 3 months
SELECT *
FROM Branch_money_convert
WHERE /* date column */ insert_date >= DATEADD(month, -3, GETDATE())
ORDER BY insert_date;
-- Cross-check each row against Branch_money_order (requested vs executed).
```

```sql
-- 7) Expenses — general ledger, last 3 months (non-purchase cash out)
SELECT at.*, gf.*
FROM Gedo_Financial gf
LEFT JOIN Account_Tree at ON at.account_id = gf.account_id   -- adapt keys
WHERE gf./*date col*/ gedo_date >= DATEADD(month, -3, GETDATE())
ORDER BY gf.gedo_date;
-- Sum by account: salaries, rent, utilities, owner draws. These compete with
-- PharmaOverseas for the same cash.
```

```sql
-- 8) Stock value per branch — cost, retail, and the DEAD part
SELECT store_id,
       COUNT(DISTINCT product_id)               AS products,
       SUM(amount)                              AS units,
       SUM(amount * buy_price)                  AS stock_value_cost,
       SUM(amount * sell_price)                 AS stock_value_retail
FROM Product_Amount
WHERE amount > 0
GROUP BY store_id;

-- 8b) Cash already lost to EXPIRED stock (the June audit found 74 batches)
SELECT store_id, COUNT(*) AS expired_batches,
       SUM(amount * buy_price) AS cash_locked_expired
FROM Product_Amount
WHERE amount > 0 AND exp_date < GETDATE()
GROUP BY store_id;

-- 8c) Cash at risk in the next 90 days
SELECT store_id, SUM(amount * buy_price) AS cash_at_risk_90d
FROM Product_Amount
WHERE amount > 0 AND exp_date BETWEEN GETDATE() AND DATEADD(day, 90, GETDATE())
GROUP BY store_id;

-- 8d) Dead stock: on-shelf items with ZERO sales in 90 days
SELECT pa.store_id, COUNT(DISTINCT pa.product_id) AS dead_products,
       SUM(pa.amount * pa.buy_price)              AS cash_locked_dead
FROM Product_Amount pa
WHERE pa.amount > 0
  AND NOT EXISTS (
      SELECT 1 FROM Sales_details sd
      JOIN Sales_header sh ON sh.sales_id = sd.sales_id
      WHERE sd.product_id = pa.product_id
        AND sh.insert_date >= DATEADD(day, -90, GETDATE()))
GROUP BY pa.store_id;
```

```sql
-- 9) Cash locked in customer receivables (the June audit: 61 over limit)
SELECT COUNT(*)                        AS debtors,
       SUM(customer_current_money)     AS total_receivables,
       SUM(CASE WHEN customer_current_money > customer_max_money
                THEN customer_current_money - customer_max_money ELSE 0 END)
                                       AS receivables_over_limit
FROM Customer
WHERE customer_current_money > 0;
```

```sql
-- 10) The cash equation for the report's §4 (fill per branch):
--   cash_in   = 3.cash_collected + receivable collections (2/7 ledgers)
--   cash_out  = payments to ALL vendors + 7.expenses + owner draws
--   locked    = 8.stock_value_cost + 9.total_receivables
--   lost      = 8b.cash_locked_expired (+ recurring 5.negative variances)
```

## Reading the results

* **Query 4 above 85%** → over-purchasing is the primary cause; apply the
  ProCare 80% budget rule (`GET /api/purchasing/budget`).
* **Query 8b/8d large** → the PharmaOverseas money is sitting on the shelf as
  expired/dead stock; run the liquidation + return-to-vendor ladder in the
  report's inventory plan.
* **Query 9 large** → the money is in customers' pockets; enforce the credit
  gate (ProCare blocks over-limit credit sales without an authorised override).
* **Query 5 recurring negatives** → cash-desk leakage; close every shift in
  ProCare (variance is computed automatically).
