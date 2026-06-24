/* ===========================================================================
   ProCare OS — Own clean database schema (ProCare's system of record)
   ---------------------------------------------------------------------------
   Target  : Microsoft SQL Server (T-SQL).
   Purpose : ProCare's OWN, INDEPENDENT operational database. It mirrors the
             functional surface of eStock (DB "stock", stock_phy_ver1.8.0.0 on
             LAN host 192.168.1.2) but FIXES every data-quality problem the
             eStock audit found, and is clean from day one:
               - real FOREIGN KEYS everywhere       (eStock enforces ZERO)
               - useful indexes from day one         (eStock missing key indexes)
               - NON-NULL operational dates          (eStock bill_date often NULL)
               - CHECK constraints (e.g. amount >= 0)(eStock has 33,249 zero/neg batches)
               - multi-branch: Main + Elsanta        (branch_id on every operational row)
               - NO broken views                     (eStock ships 8 broken views)

   Strategy (owner's words, see docs/00-CONCLUSION.md):
     Phase 1  read-only ETL FROM eStock to mirror + validate (never write back).
     Phase 2  run ProCare in PARALLEL on ONE branch to test (pilot = Elsanta).
     Phase 3  cut over completely and retire eStock — "my own software".

   Guardrail: ProCare NEVER writes to the eStock DB. A dedicated read-only SQL
   login feeds the ETL only. This file defines the destination, not the source.

   Source mapping & rationale:
     - eStock reference ...... docs/02-eStock-database-reference.md
     - data-quality fixes .... docs/05-data-quality-and-fixes.md
     - multi-branch model .... docs/07-multi-branch.md
     - Titan/Drug-Eye link ... docs/03-titan-drugeye-integration.md  (schema = TBD)
     - architecture .......... docs/01-architecture.md
     - read-only KPI queries . ../sql/dashboard-queries.sql

   NOTE: Column lists are intentionally lean compared to eStock's very wide
   tables (Products has 61 columns, Sales_header 38, Employee 55, EMP_CONTROL
   198, Branches 52). We keep the load-bearing columns and add the rest as the
   mirror proves them necessary. Every retained column is grounded in the eStock
   audit; nothing here is invented. Where a fact is genuinely unknown it is
   marked TBD (e.g. the Titan/Drug-Eye schema, the read-only login name).
   =========================================================================== */

SET NOCOUNT ON;
GO

/* ---------------------------------------------------------------------------
   Database. Adjust collation if the eStock source differs; Arabic_CI_AS gives
   correct Arabic (RTL) sorting/compare. All text columns are NVARCHAR so the
   bilingual name_ar / name_en data round-trips losslessly.
   --------------------------------------------------------------------------- */
IF DB_ID('ProCare') IS NULL
    CREATE DATABASE ProCare COLLATE Arabic_CI_AS;
GO
USE ProCare;
GO

/* ===========================================================================
   1) BRANCHES  (eStock Module 7 — Branches: 2 rows, 52 columns)
   The two physical branches: MAIN (الرئيسي) and ELSANTA (السنتا).
   Every operational row below carries branch_id. Seeded at the bottom.
   =========================================================================== */
CREATE TABLE dbo.branches (
    branch_id     INT IDENTITY(1,1) CONSTRAINT PK_branches PRIMARY KEY,
    code          VARCHAR(20)   NOT NULL,                  -- MAIN / ELSANTA
    name_ar       NVARCHAR(100) NOT NULL,
    name_en       NVARCHAR(100) NOT NULL,
    is_pilot      BIT           NOT NULL CONSTRAINT DF_branches_pilot   DEFAULT 0, -- Elsanta = Phase-2 pilot
    is_active     BIT           NOT NULL CONSTRAINT DF_branches_active  DEFAULT 1,
    created_at    DATETIME2(0)  NOT NULL CONSTRAINT DF_branches_created DEFAULT SYSDATETIME(),
    CONSTRAINT UQ_branches_code UNIQUE (code)
);
GO

/* ===========================================================================
   2) REFERENCE / LOOKUP  (eStock Module 1 & 5)
     companies        <- eStock Companys           (1,210 rows)
     product_groups   <- eStock Product_groups     (437 rows)
     units            <- eStock Product_units       (26 rows; tablet/strip/box…)
     sale_classes     <- eStock Sale_classes        (2 rows)
     customer_classes <- eStock Customer_Class      (2 rows; retail/wholesale)
   =========================================================================== */
CREATE TABLE dbo.companies (
    company_id    INT IDENTITY(1,1) CONSTRAINT PK_companies PRIMARY KEY,
    name_ar       NVARCHAR(150) NOT NULL,
    name_en       NVARCHAR(150) NULL,
    is_active     BIT NOT NULL CONSTRAINT DF_companies_active DEFAULT 1
);
GO
CREATE TABLE dbo.product_groups (
    group_id      INT IDENTITY(1,1) CONSTRAINT PK_product_groups PRIMARY KEY,
    name_ar       NVARCHAR(100) NOT NULL,
    name_en       NVARCHAR(100) NULL
);
GO
CREATE TABLE dbo.units (
    unit_id       INT IDENTITY(1,1) CONSTRAINT PK_units PRIMARY KEY,
    name_ar       NVARCHAR(50) NOT NULL,                   -- علبة / شريط / قرص
    name_en       NVARCHAR(50) NULL                        -- box / strip / tablet
);
GO
CREATE TABLE dbo.sale_classes (
    sale_class_id INT IDENTITY(1,1) CONSTRAINT PK_sale_classes PRIMARY KEY,
    name_ar       NVARCHAR(50) NOT NULL,
    name_en       NVARCHAR(50) NULL
);
GO
CREATE TABLE dbo.customer_classes (
    customer_class_id INT IDENTITY(1,1) CONSTRAINT PK_customer_classes PRIMARY KEY,
    name_ar           NVARCHAR(50) NOT NULL,               -- تجزئة / جملة
    name_en           NVARCHAR(50) NULL                    -- retail / wholesale
);
GO

/* ===========================================================================
   3) PRODUCTS  (eStock Products: 53,474 rows, 61 columns)
   Clean catalog. Bilingual names. titan_drug_id links to Titan/Drug-Eye
   (drug names + substitutions + interactions + dosing). The Titan schema is
   NOT yet audited, so titan_drug_id is a NULLable soft link with no FK yet
   (see docs/03-titan-drugeye-integration.md — mapping key = scientific_name).
   eStock booleans are char(1) 'Y'/'N'; ProCare uses real BIT.
   =========================================================================== */
CREATE TABLE dbo.products (
    product_id        INT IDENTITY(1,1) CONSTRAINT PK_products PRIMARY KEY,
    code              VARCHAR(50)   NULL,        -- eStock product_code (barcode/internal)
    fast_code         VARCHAR(20)   NULL,        -- eStock product_fast_code (quick entry)
    name_ar           NVARCHAR(150) NOT NULL,    -- eStock product_name_ar
    name_en           NVARCHAR(150) NULL,        -- eStock product_name_en
    scientific_name   NVARCHAR(200) NULL,        -- eStock product_scientific_name (Titan map key)
    titan_drug_id     INT           NULL,        -- soft link to Titan/Drug-Eye (no FK yet: schema TBD)

    company_id        INT NULL CONSTRAINT FK_products_company REFERENCES dbo.companies(company_id),
    group_id          INT NULL CONSTRAINT FK_products_group   REFERENCES dbo.product_groups(group_id),
    unit1_id          INT NULL CONSTRAINT FK_products_unit1   REFERENCES dbo.units(unit_id),  -- base unit
    unit2_id          INT NULL CONSTRAINT FK_products_unit2   REFERENCES dbo.units(unit_id),  -- strip/pack
    unit3_id          INT NULL CONSTRAINT FK_products_unit3   REFERENCES dbo.units(unit_id),  -- box/carton

    is_controlled     BIT NOT NULL CONSTRAINT DF_products_controlled DEFAULT 0,  -- eStock product_drug
    has_expiry        BIT NOT NULL CONSTRAINT DF_products_expiry     DEFAULT 1,  -- eStock product_has_expire
    allow_sale_zero   BIT NOT NULL CONSTRAINT DF_products_sellzero   DEFAULT 0,  -- eStock amount_zero

    sell_price        MONEY NOT NULL CONSTRAINT DF_products_sell  DEFAULT 0,     -- unit1 default sell
    buy_price         MONEY NOT NULL CONSTRAINT DF_products_buy   DEFAULT 0,     -- last purchase price
    tax_price         MONEY NOT NULL CONSTRAINT DF_products_tax   DEFAULT 0,
    unit2_sell_price  MONEY NULL,                                                -- eStock unit2_sell_price
    unit3_sell_price  MONEY NULL,                                                -- eStock unit3_sell_price
    wholesale_price   MONEY NULL,                                                -- eStock sell_clause

    min_stock         DECIMAL(18,3) NOT NULL CONSTRAINT DF_products_minstock DEFAULT 0,
    is_active         BIT NOT NULL CONSTRAINT DF_products_active  DEFAULT 1,     -- eStock active
    is_deleted        BIT NOT NULL CONSTRAINT DF_products_deleted DEFAULT 0,     -- eStock deleted (soft)
    created_at        DATETIME2(0) NOT NULL CONSTRAINT DF_products_created DEFAULT SYSDATETIME(),
    updated_at        DATETIME2(0) NOT NULL CONSTRAINT DF_products_updated DEFAULT SYSDATETIME(),

    CONSTRAINT CK_products_prices CHECK (sell_price >= 0 AND buy_price >= 0 AND tax_price >= 0)
);
GO
CREATE INDEX IX_products_code        ON dbo.products(code)            WHERE code IS NOT NULL;
CREATE INDEX IX_products_fast_code   ON dbo.products(fast_code)       WHERE fast_code IS NOT NULL;
CREATE INDEX IX_products_scientific  ON dbo.products(scientific_name) WHERE scientific_name IS NOT NULL;
CREATE INDEX IX_products_titan       ON dbo.products(titan_drug_id)   WHERE titan_drug_id IS NOT NULL;
CREATE INDEX IX_products_name_ar     ON dbo.products(name_ar);
GO

/* Barcodes — eStock crams 14 barcode slots into the Products row. ProCare
   normalizes them into a child table so a product can have any number of codes. */
CREATE TABLE dbo.product_barcodes (
    barcode_id   BIGINT IDENTITY(1,1) CONSTRAINT PK_product_barcodes PRIMARY KEY,
    product_id   INT NOT NULL CONSTRAINT FK_barcodes_product REFERENCES dbo.products(product_id),
    barcode      VARCHAR(64) NOT NULL,
    unit_id      INT NULL CONSTRAINT FK_barcodes_unit REFERENCES dbo.units(unit_id),
    CONSTRAINT UQ_product_barcodes UNIQUE (barcode)
);
GO

/* ===========================================================================
   4) CUSTOMERS & VENDORS  (eStock Module 4 & 5)
     customers <- eStock Customer (1,197 rows, 31 columns)
     vendors   <- eStock Vendor   (87 rows)
   NOTE: 61 customers are over their credit limit in eStock. ProCare keeps the
   limit + balance and ENFORCES it at POS via sp_check_credit (see TODO §12).
   =========================================================================== */
CREATE TABLE dbo.customers (
    customer_id        INT IDENTITY(1,1) CONSTRAINT PK_customers PRIMARY KEY,
    name_ar            NVARCHAR(100) NOT NULL,             -- eStock customer_name_ar
    name_en            NVARCHAR(100) NULL,                 -- eStock customer_name_en
    mobile             VARCHAR(20)   NULL,
    customer_class_id  INT NULL CONSTRAINT FK_customers_class REFERENCES dbo.customer_classes(customer_class_id),
    credit_limit       MONEY NOT NULL CONSTRAINT DF_customers_limit   DEFAULT 0, -- eStock customer_max_money
    current_balance    MONEY NOT NULL CONSTRAINT DF_customers_balance DEFAULT 0, -- eStock customer_current_money
    opening_balance    MONEY NOT NULL CONSTRAINT DF_customers_open    DEFAULT 0, -- eStock customer_start_money
    disc_local         DECIMAL(5,2) NOT NULL CONSTRAINT DF_customers_dloc DEFAULT 0, -- eStock customer_disc_local
    disc_import        DECIMAL(5,2) NOT NULL CONSTRAINT DF_customers_dimp DEFAULT 0, -- eStock customer_disc_import
    is_active          BIT NOT NULL CONSTRAINT DF_customers_active  DEFAULT 1,
    is_deleted         BIT NOT NULL CONSTRAINT DF_customers_deleted DEFAULT 0,
    created_at         DATETIME2(0) NOT NULL CONSTRAINT DF_customers_created DEFAULT SYSDATETIME()
);
GO
CREATE INDEX IX_customers_mobile ON dbo.customers(mobile) WHERE mobile IS NOT NULL;
CREATE INDEX IX_customers_name   ON dbo.customers(name_ar);
GO

CREATE TABLE dbo.vendors (
    vendor_id          INT IDENTITY(1,1) CONSTRAINT PK_vendors PRIMARY KEY,
    name_ar            NVARCHAR(100) NOT NULL,             -- eStock vendor_name_ar
    name_en            NVARCHAR(100) NULL,                 -- eStock vendor_name_en
    tel                VARCHAR(20)   NULL,
    mobile             VARCHAR(20)   NULL,
    credit_limit       MONEY NOT NULL CONSTRAINT DF_vendors_limit   DEFAULT 0,   -- eStock vendor_max_money
    current_balance    MONEY NOT NULL CONSTRAINT DF_vendors_balance DEFAULT 0,   -- eStock vendor_current_money
    is_active          BIT NOT NULL CONSTRAINT DF_vendors_active DEFAULT 1,
    created_at         DATETIME2(0) NOT NULL CONSTRAINT DF_vendors_created DEFAULT SYSDATETIME()
);
GO

/* ===========================================================================
   5) EMPLOYEES  (eStock Employee: 11 rows, 55 columns + EMP_CONTROL: 198 cols)
   The eStock permission flags (char(1)) are modeled as real BIT columns here.
   Mapping of the load-bearing flags from the audit:
     can_see_buy_price    <- show_buy / emp_show_money
     can_edit_sell_price  <- emp_edit_sell_price
     can_add_product      <- emp_add_product
     can_edit_product     <- emp_edit_product
     can_sale_credit      <- allaw_sale_credit
     can_return           <- allaw_r_sale
     can_void             <- allaw_un_sale
     can_delivery         <- allaw_sale_delivery
     can_change_shift     <- emp_change_cash_disk
     max_disc_per/_money  <- max_disc_per / max_disc_money
     return_backdate_days <- emp_r_sale_bill_num
   =========================================================================== */
CREATE TABLE dbo.jobs (                              -- eStock Jobs (8 rows)
    job_id        INT IDENTITY(1,1) CONSTRAINT PK_jobs PRIMARY KEY,
    name_ar       NVARCHAR(80) NOT NULL,
    name_en       NVARCHAR(80) NULL
);
GO
CREATE TABLE dbo.employees (
    employee_id          INT IDENTITY(1,1) CONSTRAINT PK_employees PRIMARY KEY,
    name_ar              NVARCHAR(100) NOT NULL,    -- eStock emp_name_ar
    name_en              NVARCHAR(100) NULL,        -- eStock emp_name_en
    username             VARCHAR(50)  NOT NULL,     -- eStock username (Sales_header.cashier_id joins this)
    password_hash        VARCHAR(255) NOT NULL,     -- ProCare hashes; eStock stored plaintext "pass"
    job_id               INT NULL CONSTRAINT FK_employees_job    REFERENCES dbo.jobs(job_id),
    branch_id            INT NULL CONSTRAINT FK_employees_branch REFERENCES dbo.branches(branch_id),
    basic_salary         MONEY NOT NULL CONSTRAINT DF_emp_salary DEFAULT 0,

    -- permission / limit flags (real BIT, default-deny)
    max_disc_per         DECIMAL(5,2) NOT NULL CONSTRAINT DF_emp_maxdiscper   DEFAULT 0,
    max_disc_money       MONEY        NOT NULL CONSTRAINT DF_emp_maxdiscmoney DEFAULT 0,
    return_backdate_days  INT         NOT NULL CONSTRAINT DF_emp_backdate     DEFAULT 0,
    can_see_buy_price    BIT NOT NULL CONSTRAINT DF_emp_seebuy     DEFAULT 0,
    can_edit_sell_price  BIT NOT NULL CONSTRAINT DF_emp_editsell   DEFAULT 0,
    can_add_product      BIT NOT NULL CONSTRAINT DF_emp_addprod    DEFAULT 0,
    can_edit_product     BIT NOT NULL CONSTRAINT DF_emp_editprod   DEFAULT 0,
    can_sale_credit      BIT NOT NULL CONSTRAINT DF_emp_credit     DEFAULT 0,
    can_return           BIT NOT NULL CONSTRAINT DF_emp_return     DEFAULT 0,
    can_void             BIT NOT NULL CONSTRAINT DF_emp_void       DEFAULT 0,
    can_delivery         BIT NOT NULL CONSTRAINT DF_emp_delivery   DEFAULT 0,
    can_change_shift     BIT NOT NULL CONSTRAINT DF_emp_shift      DEFAULT 0,
    is_active            BIT NOT NULL CONSTRAINT DF_emp_active      DEFAULT 1,
    created_at           DATETIME2(0) NOT NULL CONSTRAINT DF_emp_created DEFAULT SYSDATETIME(),

    CONSTRAINT UQ_employees_username UNIQUE (username)
);
GO

/* ===========================================================================
   6) STOCK — batch-level, per branch
   eStock has TWO stock tables: Product_Amount (35,404, single-store legacy) and
   Branches_Product_Amount (121,625, per-branch). ProCare uses ONE per-branch,
   per-batch table. eStock's batch identity is (product_id, store_id,
   counter_id, exp_date); ProCare gives each batch a surrogate batch_id and
   carries (product, branch, exp_date) + the source counter for traceability.

   Fixes baked in:
     - amount CHECK (>= 0)        -> kills the 33,249 zero/negative-batch problem
                                     (a sold-out batch has amount = 0, never < 0)
     - filtered expiry index      -> fast expiry reports over LIVE stock only
                                     (74 expired-in-stock batches found in eStock)
   "Available stock" = amount > 0 AND (exp_date > today OR product has no expiry).
   FEFO = ORDER BY exp_date ASC.
   =========================================================================== */
CREATE TABLE dbo.stock_batches (
    batch_id        BIGINT IDENTITY(1,1) CONSTRAINT PK_stock_batches PRIMARY KEY,
    product_id      INT NOT NULL CONSTRAINT FK_stock_product REFERENCES dbo.products(product_id),
    branch_id       INT NOT NULL CONSTRAINT FK_stock_branch  REFERENCES dbo.branches(branch_id),
    vendor_id       INT NULL     CONSTRAINT FK_stock_vendor  REFERENCES dbo.vendors(vendor_id),
    source_counter  INT NULL,    -- eStock counter_id, kept for ETL traceability
    amount          DECIMAL(18,3) NOT NULL CONSTRAINT DF_stock_amount DEFAULT 0
                        CONSTRAINT CK_stock_amount CHECK (amount >= 0),
    buy_price       MONEY NOT NULL CONSTRAINT DF_stock_buy  DEFAULT 0,
    sell_price      MONEY NOT NULL CONSTRAINT DF_stock_sell DEFAULT 0,
    tax_price       MONEY NOT NULL CONSTRAINT DF_stock_tax  DEFAULT 0,
    exp_date        DATE  NULL,   -- NULL allowed only when product.has_expiry = 0
    created_at      DATETIME2(0) NOT NULL CONSTRAINT DF_stock_created DEFAULT SYSDATETIME()
);
GO
CREATE INDEX IX_stock_product_branch ON dbo.stock_batches(product_id, branch_id);
CREATE INDEX IX_stock_branch         ON dbo.stock_batches(branch_id);
-- expiry reports / FEFO over LIVE stock only:
CREATE INDEX IX_stock_expiry         ON dbo.stock_batches(exp_date, branch_id) WHERE amount > 0;
GO

/* Audit of EVERY stock change  (eStock Product_amount_Change: 265,249 rows). */
CREATE TABLE dbo.stock_movements (
    movement_id   BIGINT IDENTITY(1,1) CONSTRAINT PK_stock_movements PRIMARY KEY,
    batch_id      BIGINT NOT NULL CONSTRAINT FK_movements_batch  REFERENCES dbo.stock_batches(batch_id),
    branch_id     INT    NOT NULL CONSTRAINT FK_movements_branch REFERENCES dbo.branches(branch_id),
    delta         DECIMAL(18,3) NOT NULL,         -- + in, - out
    reason        VARCHAR(20) NOT NULL,           -- sale/purchase/transfer_out/transfer_in/adjust/writeoff/opening
    ref_id        BIGINT NULL,                    -- sale_id / purchase_id / transfer_id / adjustment_id
    employee_id   INT NULL CONSTRAINT FK_movements_emp REFERENCES dbo.employees(employee_id),
    created_at    DATETIME2(0) NOT NULL CONSTRAINT DF_movements_created DEFAULT SYSDATETIME(),
    CONSTRAINT CK_movements_reason CHECK
        (reason IN ('sale','purchase','transfer_out','transfer_in','adjust','writeoff','opening','return'))
);
GO
CREATE INDEX IX_movements_batch ON dbo.stock_movements(batch_id);
CREATE INDEX IX_movements_ref   ON dbo.stock_movements(reason, ref_id);
GO

/* ===========================================================================
   7) SALES  (eStock Sales_header: 95,088 / Sales_details: 183,906)
   Returns live in the SAME tables via is_return (eStock used separate
   Back_sales_* tables: 4,359 / 4,212 — ProCare unifies them with a flag).

   KEY FIX: sale_date is NOT NULL. eStock's bill_date is frequently NULL, so
   the ETL writes COALESCE(eStock.bill_date, eStock.insert_date) into sale_date.
   =========================================================================== */
CREATE TABLE dbo.sales (
    sale_id            BIGINT IDENTITY(1,1) CONSTRAINT PK_sales PRIMARY KEY,
    branch_id          INT NOT NULL CONSTRAINT FK_sales_branch   REFERENCES dbo.branches(branch_id),
    customer_id        INT NULL     CONSTRAINT FK_sales_customer REFERENCES dbo.customers(customer_id), -- NULL = walk-in
    cashier_id         INT NULL     CONSTRAINT FK_sales_cashier  REFERENCES dbo.employees(employee_id),
    delivery_man_id    INT NULL     CONSTRAINT FK_sales_delivery REFERENCES dbo.employees(employee_id),
    sale_class_id      INT NULL     CONSTRAINT FK_sales_class    REFERENCES dbo.sale_classes(sale_class_id),
    sale_date          DATETIME2(0) NOT NULL CONSTRAINT DF_sales_date DEFAULT SYSDATETIME(), -- eStock bill_date bug fixed
    total_gross        MONEY NOT NULL CONSTRAINT DF_sales_gross DEFAULT 0,  -- eStock total_bill
    total_discount     MONEY NOT NULL CONSTRAINT DF_sales_disc  DEFAULT 0,  -- eStock total_disc_money
    total_net          MONEY NOT NULL CONSTRAINT DF_sales_net   DEFAULT 0,  -- eStock total_bill_net
    cash_paid          MONEY NOT NULL CONSTRAINT DF_sales_cash  DEFAULT 0,  -- eStock bill_cash
    card_paid          MONEY NOT NULL CONSTRAINT DF_sales_card  DEFAULT 0,  -- eStock network_money
    change_given       MONEY NOT NULL CONSTRAINT DF_sales_chg   DEFAULT 0,  -- eStock money_change
    is_return          BIT   NOT NULL CONSTRAINT DF_sales_return DEFAULT 0, -- eStock back = 'Y'
    is_credit          BIT   NOT NULL CONSTRAINT DF_sales_credit DEFAULT 0, -- on-account (vs cash) sale
    created_at         DATETIME2(0) NOT NULL CONSTRAINT DF_sales_created DEFAULT SYSDATETIME(),
    CONSTRAINT CK_sales_totals CHECK (total_gross >= 0 AND total_net >= 0 AND total_discount >= 0)
);
GO
CREATE INDEX IX_sales_date          ON dbo.sales(sale_date);
CREATE INDEX IX_sales_branch_date   ON dbo.sales(branch_id, sale_date);
CREATE INDEX IX_sales_customer      ON dbo.sales(customer_id) WHERE customer_id IS NOT NULL;
GO

CREATE TABLE dbo.sale_lines (
    line_id            BIGINT IDENTITY(1,1) CONSTRAINT PK_sale_lines PRIMARY KEY,
    sale_id            BIGINT NOT NULL CONSTRAINT FK_saleline_sale    REFERENCES dbo.sales(sale_id),
    product_id         INT    NOT NULL CONSTRAINT FK_saleline_product REFERENCES dbo.products(product_id),
    batch_id           BIGINT NULL     CONSTRAINT FK_saleline_batch   REFERENCES dbo.stock_batches(batch_id), -- FEFO batch
    amount             DECIMAL(18,3) NOT NULL,                        -- eStock amount
    sell_price         MONEY NOT NULL,                                -- eStock sell_price (actual used)
    buy_price          MONEY NOT NULL,                                -- eStock buy_price (cost snapshot for profit)
    disc_money         MONEY NOT NULL CONSTRAINT DF_saleline_disc DEFAULT 0, -- eStock disc_money
    total_sell         MONEY NOT NULL,                                -- eStock total_sell (line net)
    is_return          BIT   NOT NULL CONSTRAINT DF_saleline_return DEFAULT 0, -- eStock back = 'Y'
    CONSTRAINT CK_saleline_amount CHECK (amount > 0)
);
GO
CREATE INDEX IX_sale_lines_sale    ON dbo.sale_lines(sale_id);
CREATE INDEX IX_sale_lines_product ON dbo.sale_lines(product_id);
GO

/* ===========================================================================
   8) PURCHASING  (eStock Purchase_header: 685 / Purchase_details: 9,230)
   bill_date is NOT NULL here (purchases always carry a supplier invoice date).
   =========================================================================== */
CREATE TABLE dbo.purchases (
    purchase_id        BIGINT IDENTITY(1,1) CONSTRAINT PK_purchases PRIMARY KEY,
    branch_id          INT NOT NULL CONSTRAINT FK_purch_branch REFERENCES dbo.branches(branch_id),
    vendor_id          INT NOT NULL CONSTRAINT FK_purch_vendor REFERENCES dbo.vendors(vendor_id),
    bill_date          DATE NOT NULL,                            -- eStock bill_date
    bill_number        VARCHAR(50) NULL,                         -- eStock bill_number (supplier invoice #)
    total_gross        MONEY NOT NULL CONSTRAINT DF_purch_gross DEFAULT 0, -- eStock total_bill
    total_discount     MONEY NOT NULL CONSTRAINT DF_purch_disc  DEFAULT 0, -- eStock bill_disc_money
    total_tax          MONEY NOT NULL CONSTRAINT DF_purch_tax   DEFAULT 0, -- eStock bill_tax
    other_expenses     MONEY NOT NULL CONSTRAINT DF_purch_other DEFAULT 0, -- eStock bill_other_expenses
    is_return          BIT   NOT NULL CONSTRAINT DF_purch_return DEFAULT 0, -- eStock back
    created_at         DATETIME2(0) NOT NULL CONSTRAINT DF_purch_created DEFAULT SYSDATETIME()
);
GO
CREATE INDEX IX_purchases_branch_date ON dbo.purchases(branch_id, bill_date);
CREATE INDEX IX_purchases_vendor      ON dbo.purchases(vendor_id);
GO

CREATE TABLE dbo.purchase_lines (
    line_id            BIGINT IDENTITY(1,1) CONSTRAINT PK_purchase_lines PRIMARY KEY,
    purchase_id        BIGINT NOT NULL CONSTRAINT FK_purchline_purch   REFERENCES dbo.purchases(purchase_id),
    product_id         INT    NOT NULL CONSTRAINT FK_purchline_product REFERENCES dbo.products(product_id),
    batch_id           BIGINT NULL     CONSTRAINT FK_purchline_batch   REFERENCES dbo.stock_batches(batch_id), -- batch created on receipt
    amount             DECIMAL(18,3) NOT NULL,                          -- eStock amount
    bonus              DECIMAL(18,3) NOT NULL CONSTRAINT DF_purchline_bonus DEFAULT 0, -- eStock bouns (free units)
    buy_price          MONEY NOT NULL,                                  -- eStock buy_price
    sell_price         MONEY NOT NULL,                                  -- eStock sell_price
    exp_date           DATE  NULL,                                      -- eStock exp_date
    CONSTRAINT CK_purchline_amount CHECK (amount > 0)
);
GO
CREATE INDEX IX_purchase_lines_purchase ON dbo.purchase_lines(purchase_id);
GO

/* Opening stock  (eStock Start_stock_header: 249 / Start_stock_details: 3,400)
   Captured once when a branch goes live in ProCare; each line creates a batch
   and an 'opening' stock_movement. Modeled as a purchase-like document. */
CREATE TABLE dbo.opening_stock (
    opening_id   BIGINT IDENTITY(1,1) CONSTRAINT PK_opening_stock PRIMARY KEY,
    branch_id    INT NOT NULL CONSTRAINT FK_opening_branch REFERENCES dbo.branches(branch_id),
    opening_date DATE NOT NULL,
    note         NVARCHAR(255) NULL,
    created_at   DATETIME2(0) NOT NULL CONSTRAINT DF_opening_created DEFAULT SYSDATETIME()
);
GO
CREATE TABLE dbo.opening_stock_lines (
    line_id      BIGINT IDENTITY(1,1) CONSTRAINT PK_opening_lines PRIMARY KEY,
    opening_id   BIGINT NOT NULL CONSTRAINT FK_openline_open    REFERENCES dbo.opening_stock(opening_id),
    product_id   INT    NOT NULL CONSTRAINT FK_openline_product REFERENCES dbo.products(product_id),
    batch_id     BIGINT NULL     CONSTRAINT FK_openline_batch   REFERENCES dbo.stock_batches(batch_id),
    amount       DECIMAL(18,3) NOT NULL CONSTRAINT CK_openline_amount CHECK (amount > 0),
    buy_price    MONEY NOT NULL,
    sell_price   MONEY NOT NULL,
    exp_date     DATE  NULL
);
GO

/* Stock adjustments  (eStock Product_amount_update: 79 / Product_amount_reg_update: 10,818).
   Manual count corrections, write-offs, expiry write-offs. Each posts a
   stock_movement with reason 'adjust' or 'writeoff'. */
CREATE TABLE dbo.stock_adjustments (
    adjustment_id  BIGINT IDENTITY(1,1) CONSTRAINT PK_stock_adjustments PRIMARY KEY,
    branch_id      INT NOT NULL CONSTRAINT FK_adj_branch  REFERENCES dbo.branches(branch_id),
    batch_id       BIGINT NOT NULL CONSTRAINT FK_adj_batch REFERENCES dbo.stock_batches(batch_id),
    delta          DECIMAL(18,3) NOT NULL,                 -- signed correction
    reason         VARCHAR(20) NOT NULL CONSTRAINT CK_adj_reason CHECK (reason IN ('adjust','writeoff','expiry')),
    note           NVARCHAR(255) NULL,
    employee_id    INT NULL CONSTRAINT FK_adj_emp REFERENCES dbo.employees(employee_id),
    created_at     DATETIME2(0) NOT NULL CONSTRAINT DF_adj_created DEFAULT SYSDATETIME()
);
GO

/* ===========================================================================
   9) INTER-BRANCH TRANSFERS  (eStock Module 7 — Main <-> Elsanta)
     stock_transfers / _lines <- Branch_order_header (8,204) / _details (61,872)
     cash_transfers           <- Branch_money_order (1,102) / Branch_money_convert (1,098)
   Batch identity (and expiry) travels with the transfer so FEFO/expiry stay
   correct across branches (see docs/07-multi-branch.md). The atomic move is
   done by sp_transfer_stock (TODO §12): decrement source, increment
   destination, two stock_movements (transfer_out + transfer_in) under one id.
   =========================================================================== */
CREATE TABLE dbo.stock_transfers (
    transfer_id        BIGINT IDENTITY(1,1) CONSTRAINT PK_stock_transfers PRIMARY KEY,
    from_branch_id     INT NOT NULL CONSTRAINT FK_transfer_from REFERENCES dbo.branches(branch_id),
    to_branch_id       INT NOT NULL CONSTRAINT FK_transfer_to   REFERENCES dbo.branches(branch_id),
    status             VARCHAR(20) NOT NULL CONSTRAINT DF_transfer_status DEFAULT 'requested',
    requested_by       INT NULL CONSTRAINT FK_transfer_reqby REFERENCES dbo.employees(employee_id),
    created_at         DATETIME2(0) NOT NULL CONSTRAINT DF_transfer_created  DEFAULT SYSDATETIME(),
    shipped_at         DATETIME2(0) NULL,
    received_at        DATETIME2(0) NULL,
    CONSTRAINT CK_transfer_status   CHECK (status IN ('requested','in_transit','received','cancelled')),
    CONSTRAINT CK_transfer_branches CHECK (from_branch_id <> to_branch_id)
);
GO
CREATE TABLE dbo.stock_transfer_lines (
    line_id            BIGINT IDENTITY(1,1) CONSTRAINT PK_transfer_lines PRIMARY KEY,
    transfer_id        BIGINT NOT NULL CONSTRAINT FK_transferline_transfer REFERENCES dbo.stock_transfers(transfer_id),
    product_id         INT    NOT NULL CONSTRAINT FK_transferline_product  REFERENCES dbo.products(product_id),
    from_batch_id      BIGINT NULL     CONSTRAINT FK_transferline_frombatch REFERENCES dbo.stock_batches(batch_id),
    to_batch_id        BIGINT NULL     CONSTRAINT FK_transferline_tobatch   REFERENCES dbo.stock_batches(batch_id),
    amount             DECIMAL(18,3) NOT NULL CONSTRAINT CK_transferline_amount CHECK (amount > 0),
    buy_price          MONEY NOT NULL CONSTRAINT DF_transferline_buy DEFAULT 0,  -- cost travels with the batch
    exp_date           DATE  NULL                                                -- batch expiry travels with the transfer
);
GO
CREATE INDEX IX_transfer_lines_transfer ON dbo.stock_transfer_lines(transfer_id);
GO

CREATE TABLE dbo.cash_transfers (
    cash_transfer_id   BIGINT IDENTITY(1,1) CONSTRAINT PK_cash_transfers PRIMARY KEY,
    from_branch_id     INT NOT NULL CONSTRAINT FK_cash_from REFERENCES dbo.branches(branch_id),
    to_branch_id       INT NOT NULL CONSTRAINT FK_cash_to   REFERENCES dbo.branches(branch_id),
    amount             MONEY NOT NULL CONSTRAINT CK_cash_amount CHECK (amount > 0),
    status             VARCHAR(20) NOT NULL CONSTRAINT DF_cash_status DEFAULT 'sent',
    sent_by            INT NULL CONSTRAINT FK_cash_sentby REFERENCES dbo.employees(employee_id),
    created_at         DATETIME2(0) NOT NULL CONSTRAINT DF_cash_created   DEFAULT SYSDATETIME(),
    received_at        DATETIME2(0) NULL,
    CONSTRAINT CK_cash_status   CHECK (status IN ('sent','received','cancelled')),
    CONSTRAINT CK_cash_branches CHECK (from_branch_id <> to_branch_id)
);
GO

/* ===========================================================================
   10) FINANCIAL LEDGER  (branch-aware, double-entry friendly)
   Consolidates eStock's split ledgers into ONE table tagged by account_type:
     Gedo_Financial (93,925) general ledger / journal
     Gedo_customers (88,359) customer ledger
     Gedo_Vendors   (2,878)  vendor ledger
     Gedo_branches  (9,271)  branch ledger
   account_ref points at the customer/vendor/etc. row depending on account_type.
   Every row carries branch_id so per-branch and consolidated statements both work.
   =========================================================================== */
CREATE TABLE dbo.ledger_entries (
    entry_id           BIGINT IDENTITY(1,1) CONSTRAINT PK_ledger PRIMARY KEY,
    branch_id          INT NOT NULL CONSTRAINT FK_ledger_branch REFERENCES dbo.branches(branch_id),
    entry_date         DATETIME2(0) NOT NULL CONSTRAINT DF_ledger_date DEFAULT SYSDATETIME(),
    account_type       VARCHAR(20) NOT NULL,    -- customer / vendor / cash / bank / branch / general
    account_ref        BIGINT NULL,             -- customer_id / vendor_id / branch_id (per account_type)
    ref_type           VARCHAR(20) NULL,        -- sale / purchase / transfer / cash_transfer / manual
    ref_id             BIGINT NULL,             -- sale_id / purchase_id / transfer_id ...
    debit              MONEY NOT NULL CONSTRAINT DF_ledger_debit  DEFAULT 0,
    credit             MONEY NOT NULL CONSTRAINT DF_ledger_credit DEFAULT 0,
    note               NVARCHAR(255) NULL,
    created_at         DATETIME2(0) NOT NULL CONSTRAINT DF_ledger_created DEFAULT SYSDATETIME(),
    CONSTRAINT CK_ledger_account CHECK
        (account_type IN ('customer','vendor','cash','bank','branch','general')),
    CONSTRAINT CK_ledger_amounts CHECK (debit >= 0 AND credit >= 0)
);
GO
CREATE INDEX IX_ledger_branch_date ON dbo.ledger_entries(branch_id, entry_date);
CREATE INDEX IX_ledger_account     ON dbo.ledger_entries(account_type, account_ref);
CREATE INDEX IX_ledger_ref         ON dbo.ledger_entries(ref_type, ref_id);
GO

/* ===========================================================================
   11) SEED DATA — the two physical branches (Main + Elsanta)
   Elsanta is flagged as the Phase-2 pilot branch (see docs/00-CONCLUSION.md,
   docs/07-multi-branch.md).
   =========================================================================== */
INSERT INTO dbo.branches (code, name_ar, name_en, is_pilot) VALUES
    ('MAIN',    N'الرئيسي', N'Main',    0),
    ('ELSANTA', N'السنتا',  N'Elsanta', 1);
GO

/* ===========================================================================
   12) TODO — HOT-PATH STORED PROCEDURES  (Phase 2+)
   eStock has ZERO stored procedures/functions — all business logic is locked
   in the .exe. ProCare moves the hot paths into tested, versioned procedures
   so the logic is reusable, atomic, and reportable. To be authored next:

     sp_create_sale(@branch_id, @customer_id, @cashier_id, @lines …)
        Atomic: insert sales header + sale_lines, deduct stock FEFO
        (ORDER BY exp_date ASC, skipping expired/empty batches), write
        stock_movements (reason='sale'), post ledger_entries, and run
        sp_check_credit for on-account sales. Wrapped in one transaction;
        any failure rolls back the whole invoice.

     sp_deduct_stock(@batch_id | @product_id+@branch_id, @qty)
        Per-batch decrement that can NEVER go negative (relies on
        CK_stock_amount); for product+branch it walks batches FEFO across as
        many batches as the quantity needs. Logs a stock_movement per batch hit.

     sp_calc_profit(@from_date, @to_date, @branch_id = NULL)
        revenue - cost over a period/branch:
        SUM(sale_lines.total_sell) - SUM(sale_lines.amount * sale_lines.buy_price),
        excluding returns (is_return = 0). NULL @branch_id = consolidated.

     sp_check_credit(@customer_id, @new_charge)
        Enforces customers.credit_limit at POS. Blocks (or requires an explicit
        override by an employee with can_sale_credit = 1) when
        current_balance + @new_charge > credit_limit. This is the control that
        was BYPASSED in eStock (61 customers over limit).

     sp_transfer_stock(@from_branch, @to_branch, @lines …)
        Atomic Main <-> Elsanta move: decrement source batches (FEFO),
        create/append destination batches carrying the SAME exp_date + buy_price,
        write two stock_movements (transfer_out + transfer_in) under one
        transfer_id, and advance stock_transfers.status. All-or-nothing.

   Reporting note: read-only KPI/report queries already exist in
   ../sql/dashboard-queries.sql and are reused on this clean schema after
   cutover (with eStock table names mapped to the ProCare names above).

   Open TBDs (do not invent — confirm before building):
     - Read-only ETL SQL login name/permissions for the eStock source (TBD).
     - Titan / Drug-Eye schema at D:\Labirdo (NOT audited) — once known, decide
       whether titan_drug_id becomes a real FK to a mirrored Titan table.
   =========================================================================== */
GO
