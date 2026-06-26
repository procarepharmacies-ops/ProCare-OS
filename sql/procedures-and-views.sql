/* ===========================================================================
   ProCare OS — Hot-path stored procedures + AI whitelist views (T-SQL)
   ---------------------------------------------------------------------------
   Target  : Microsoft SQL Server (T-SQL). Run AFTER procare-schema.sql.

   These complete the TODO block at the bottom of procare-schema.sql. eStock had
   ZERO stored procedures / functions (all logic locked in the .exe); ProCare
   moves the hot paths into tested, atomic, versioned procedures.

   The application layer (src/backend/app/services/pos.py) implements the SAME
   logic in Python so the system is fully runnable on SQLite in dev. On SQL
   Server these procedures are the authoritative, in-database implementation —
   call them from sp_create_sale etc. for atomicity at the engine.

   The vw_* views are the READ-ONLY whitelist the Arabic AI assistant is allowed
   to query (docs/04 §4.3). The assistant's DB login is granted SELECT on these
   views ONLY — never on base tables — so a bad generation can never read HR
   salaries / password hashes or write anything.
   =========================================================================== */
USE ProCare;
GO

/* ---------------------------------------------------------------------------
   sp_check_credit — enforce the customer credit limit (fixes 61 over-limit).
   Returns 0 = OK, raises if over limit without an authorised override.
   --------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE dbo.sp_check_credit
    @customer_id INT,
    @new_charge  MONEY,
    @override_by INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @limit MONEY, @balance MONEY;
    SELECT @limit = credit_limit, @balance = current_balance
    FROM dbo.customers WHERE customer_id = @customer_id;

    IF @limit IS NULL
        THROW 50010, 'Customer not found', 1;
    IF @limit <= 0 RETURN 0;                       -- no limit configured
    IF (@balance + @new_charge) <= @limit RETURN 0;

    IF @override_by IS NOT NULL
       AND EXISTS (SELECT 1 FROM dbo.employees
                   WHERE employee_id = @override_by AND can_sale_credit = 1)
        RETURN 0;                                  -- authorised override

    THROW 50011, 'Credit limit exceeded (needs authorised override)', 1;
END;
GO

/* ---------------------------------------------------------------------------
   sp_deduct_stock — FEFO decrement that can NEVER go negative.
   Walks live (non-expired, amount>0) batches first-expire-first, logs one
   stock_movement per batch hit. Relies on CK_stock_amount as the backstop.
   --------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE dbo.sp_deduct_stock
    @product_id  INT,
    @branch_id   INT,
    @qty         DECIMAL(18,3),
    @ref_id      BIGINT = NULL,
    @employee_id INT = NULL,
    @reason      VARCHAR(20) = 'sale'
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @available DECIMAL(18,3);
    SELECT @available = ISNULL(SUM(amount), 0)
    FROM dbo.stock_batches
    WHERE product_id = @product_id AND branch_id = @branch_id AND amount > 0
      AND (exp_date IS NULL OR exp_date > CAST(GETDATE() AS DATE));

    IF @available < @qty
        THROW 50020, 'Insufficient sellable stock', 1;   -- also blocks expired-only

    DECLARE @remaining DECIMAL(18,3) = @qty, @batch_id BIGINT, @amt DECIMAL(18,3), @take DECIMAL(18,3);
    DECLARE fefo CURSOR LOCAL FAST_FORWARD FOR
        SELECT batch_id, amount FROM dbo.stock_batches
        WHERE product_id = @product_id AND branch_id = @branch_id AND amount > 0
          AND (exp_date IS NULL OR exp_date > CAST(GETDATE() AS DATE))
        ORDER BY CASE WHEN exp_date IS NULL THEN 1 ELSE 0 END, exp_date ASC;

    OPEN fefo;
    FETCH NEXT FROM fefo INTO @batch_id, @amt;
    WHILE @@FETCH_STATUS = 0 AND @remaining > 0
    BEGIN
        SET @take = CASE WHEN @amt < @remaining THEN @amt ELSE @remaining END;
        UPDATE dbo.stock_batches SET amount = amount - @take WHERE batch_id = @batch_id;
        INSERT dbo.stock_movements (batch_id, branch_id, delta, reason, ref_id, employee_id)
            VALUES (@batch_id, @branch_id, -@take, @reason, @ref_id, @employee_id);
        SET @remaining -= @take;
        FETCH NEXT FROM fefo INTO @batch_id, @amt;
    END;
    CLOSE fefo; DEALLOCATE fefo;
END;
GO

/* ---------------------------------------------------------------------------
   sp_calc_profit — revenue - cost over a period/branch (NULL branch = all).
   --------------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE dbo.sp_calc_profit
    @from_date DATE, @to_date DATE, @branch_id INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        SUM(sl.total_sell)                       AS revenue,
        SUM(sl.amount * sl.buy_price)            AS cost,
        SUM(sl.total_sell) - SUM(sl.amount * sl.buy_price) AS gross_profit
    FROM dbo.sale_lines sl
    JOIN dbo.sales s ON s.sale_id = sl.sale_id
    WHERE s.is_return = 0
      AND (@branch_id IS NULL OR s.branch_id = @branch_id)
      AND CAST(s.sale_date AS DATE) BETWEEN @from_date AND @to_date;
END;
GO

/* sp_create_sale and sp_transfer_stock wrap the above in a single transaction.
   The full bodies mirror app/services/pos.py:create_sale / transfer_stock —
   insert header + lines, call sp_deduct_stock per line, post ledger_entries,
   advance status — all under BEGIN TRAN / COMMIT with XACT_ABORT ON so any
   failure rolls the whole invoice back. Kept in the app layer as the single
   source of truth during Phase 1–2; promote here at cutover. */
GO

/* ===========================================================================
   AI ASSISTANT WHITELIST VIEWS (read-only) — docs/04 §4.3
   Grant the assistant login SELECT on these ONLY.
   =========================================================================== */
CREATE OR ALTER VIEW dbo.vw_daily_sales AS
    SELECT s.branch_id,
           CAST(s.sale_date AS DATE) AS sale_date,
           COUNT(*)            AS bills,
           SUM(s.total_net)    AS revenue
    FROM dbo.sales s
    WHERE s.is_return = 0
    GROUP BY s.branch_id, CAST(s.sale_date AS DATE);
GO

CREATE OR ALTER VIEW dbo.vw_top_products AS
    SELECT s.branch_id, p.product_id, p.name_ar, p.name_en,
           SUM(sl.amount)     AS units_sold,
           SUM(sl.total_sell) AS revenue
    FROM dbo.sale_lines sl
    JOIN dbo.sales s    ON s.sale_id = sl.sale_id
    JOIN dbo.products p ON p.product_id = sl.product_id
    WHERE s.is_return = 0
    GROUP BY s.branch_id, p.product_id, p.name_ar, p.name_en;
GO

CREATE OR ALTER VIEW dbo.vw_expiry_risk AS
    SELECT sb.branch_id, p.name_ar, p.name_en,
           sb.exp_date, sb.amount,
           sb.amount * sb.buy_price AS expected_loss,
           DATEDIFF(day, CAST(GETDATE() AS DATE), sb.exp_date) AS days_left
    FROM dbo.stock_batches sb
    JOIN dbo.products p ON p.product_id = sb.product_id
    WHERE sb.amount > 0 AND sb.exp_date IS NOT NULL;
GO

CREATE OR ALTER VIEW dbo.vw_low_stock AS
    SELECT p.product_id, p.name_ar, p.name_en, sb.branch_id,
           ISNULL(SUM(sb.amount), 0) AS on_hand, p.min_stock
    FROM dbo.products p
    LEFT JOIN dbo.stock_batches sb
           ON sb.product_id = p.product_id AND sb.amount > 0
          AND (sb.exp_date IS NULL OR sb.exp_date > CAST(GETDATE() AS DATE))
    WHERE p.is_active = 1
    GROUP BY p.product_id, p.name_ar, p.name_en, sb.branch_id, p.min_stock
    HAVING ISNULL(SUM(sb.amount), 0) < p.min_stock;
GO

CREATE OR ALTER VIEW dbo.vw_customer_debtors AS
    SELECT customer_id, name_ar, name_en, credit_limit, current_balance,
           (credit_limit - current_balance) AS available_credit,
           CASE WHEN credit_limit > 0 AND current_balance > credit_limit THEN 1 ELSE 0 END AS over_limit
    FROM dbo.customers
    WHERE current_balance > 0;
GO
