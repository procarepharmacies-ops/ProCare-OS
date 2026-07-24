-- ============================================================================
-- ProCare OS Database Setup — SQL Server on ProCare Dev (192.168.1.10)
-- ============================================================================
-- Run this script on ProCare Dev to create the ProCare database and schema.
-- Prerequisites:
--   - SQL Server 2019+ running on 192.168.1.10
--   - You have sysadmin privileges (or CREATE DATABASE permission)
--   - No existing 'ProCare' database (or you're OK overwriting it)
-- ============================================================================

-- Step 1: Create database
-- ============================================================================
IF EXISTS (SELECT 1 FROM sys.databases WHERE name = 'ProCare')
BEGIN
    ALTER DATABASE ProCare SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE ProCare;
END
GO

CREATE DATABASE ProCare
    ON PRIMARY (
        NAME = N'ProCare_data',
        FILENAME = N'D:\SQLData\ProCare.mdf',
        SIZE = 100 MB,
        FILEGROWTH = 50 MB
    )
    LOG ON (
        NAME = N'ProCare_log',
        FILENAME = N'D:\SQLData\ProCare.ldf',
        SIZE = 50 MB,
        FILEGROWTH = 25 MB
    );
GO

USE ProCare;
GO

-- ============================================================================
-- Step 2: Create login + user for application
-- ============================================================================

-- Create read-only login for eStock mirror
USE [master];
GO
IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'procare_readonly')
    DROP LOGIN procare_readonly;
GO

CREATE LOGIN procare_readonly WITH PASSWORD = N'ChangeMe@123';
GO

-- Create application login (read/write on ProCare)
IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'procare_app')
    DROP LOGIN procare_app;
GO

CREATE LOGIN procare_app WITH PASSWORD = N'ChangeMe@123';
GO

USE ProCare;
GO

-- Add users to ProCare database
CREATE USER procare_app FROM LOGIN procare_app;
ALTER ROLE db_owner ADD MEMBER procare_app;
GO

-- ============================================================================
-- Step 3: Enable foreign keys + cleanup
-- ============================================================================
EXEC sp_configure 'show advanced options', 1;
RECONFIGURE;
EXEC sp_configure 'xp_cmdshell', 0;  -- Disable shell for security
RECONFIGURE;
GO

-- ============================================================================
-- Step 4: Schema (from sql/procare-schema.sql)
-- ============================================================================
-- NOTE: For now, this is a placeholder. In practice, you would:
-- 1. Read procare-schema.sql (SQL Server version, not SQLite)
-- 2. Execute the entire DDL here
--
-- For now, creating minimal schema to allow ETL mirror to work:

-- Branches
CREATE TABLE branches (
    branch_id    INT PRIMARY KEY IDENTITY(1,1),
    code         VARCHAR(50) NOT NULL UNIQUE,
    name_ar      NVARCHAR(255) NOT NULL,
    name_en      VARCHAR(255),
    is_pilot     BIT NOT NULL DEFAULT 0,
    is_active    BIT NOT NULL DEFAULT 1,
    created_at   DATETIME2 NOT NULL DEFAULT GETDATE()
);

-- Products
CREATE TABLE product_groups (
    group_id     INT PRIMARY KEY IDENTITY(1,1),
    name_ar      NVARCHAR(255) NOT NULL,
    name_en      VARCHAR(255)
);

CREATE TABLE units (
    unit_id      INT PRIMARY KEY IDENTITY(1,1),
    name_ar      NVARCHAR(255) NOT NULL,
    name_en      VARCHAR(255)
);

CREATE TABLE products (
    product_id           INT PRIMARY KEY IDENTITY(1,1),
    code                 VARCHAR(50) NOT NULL UNIQUE,
    name_ar              NVARCHAR(255) NOT NULL,
    name_en              VARCHAR(255),
    scientific_name      VARCHAR(255),
    group_id             INT REFERENCES product_groups(group_id),
    unit1_id             INT REFERENCES units(unit_id),
    unit2_id             INT REFERENCES units(unit_id),
    unit3_id             INT REFERENCES units(unit_id),
    is_controlled        BIT NOT NULL DEFAULT 0,
    has_expiry           BIT NOT NULL DEFAULT 1,
    allow_sale_zero      BIT NOT NULL DEFAULT 0,
    sell_price           MONEY NOT NULL DEFAULT 0,
    buy_price            MONEY NOT NULL DEFAULT 0,
    tax_price            MONEY NOT NULL DEFAULT 0,
    min_stock            REAL NOT NULL DEFAULT 0,
    is_active            BIT NOT NULL DEFAULT 1,
    created_at           DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX IX_products_code ON products(code);

-- Customers
CREATE TABLE customers (
    customer_id          INT PRIMARY KEY IDENTITY(1,1),
    name_ar              NVARCHAR(255) NOT NULL,
    name_en              VARCHAR(255),
    mobile               VARCHAR(20),
    credit_limit         MONEY NOT NULL DEFAULT 0,
    current_balance      MONEY NOT NULL DEFAULT 0,
    is_active            BIT NOT NULL DEFAULT 1,
    created_at           DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX IX_customers_mobile ON customers(mobile);

-- Vendors
CREATE TABLE vendors (
    vendor_id            INT PRIMARY KEY IDENTITY(1,1),
    name_ar              NVARCHAR(255) NOT NULL,
    name_en              VARCHAR(255),
    mobile               VARCHAR(20),
    credit_limit         MONEY NOT NULL DEFAULT 0,
    current_balance      MONEY NOT NULL DEFAULT 0,
    is_active            BIT NOT NULL DEFAULT 1,
    created_at           DATETIME2 NOT NULL DEFAULT GETDATE()
);

-- Employees
CREATE TABLE jobs (
    job_id               INT PRIMARY KEY IDENTITY(1,1),
    name_ar              NVARCHAR(255) NOT NULL,
    name_en              VARCHAR(255)
);

CREATE TABLE employees (
    employee_id          INT PRIMARY KEY IDENTITY(1,1),
    name_ar              NVARCHAR(255) NOT NULL,
    name_en              VARCHAR(255),
    username             VARCHAR(50) NOT NULL UNIQUE,
    password_hash        VARCHAR(255) NOT NULL,
    job_id               INT REFERENCES jobs(job_id),
    branch_id            INT REFERENCES branches(branch_id),
    basic_salary         MONEY NOT NULL DEFAULT 0,
    can_sale_credit      BIT NOT NULL DEFAULT 0,
    can_return           BIT NOT NULL DEFAULT 0,
    is_active            BIT NOT NULL DEFAULT 1,
    created_at           DATETIME2 NOT NULL DEFAULT GETDATE()
);

-- Stock (batch-level, per branch)
CREATE TABLE stock_batches (
    batch_id             INT PRIMARY KEY IDENTITY(1,1),
    product_id           INT NOT NULL REFERENCES products(product_id),
    branch_id            INT NOT NULL REFERENCES branches(branch_id),
    vendor_id            INT REFERENCES vendors(vendor_id),
    amount               REAL NOT NULL DEFAULT 0 CHECK (amount >= 0),
    buy_price            MONEY NOT NULL DEFAULT 0,
    sell_price           MONEY NOT NULL DEFAULT 0,
    exp_date             DATE,
    created_at           DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX IX_stock_product_branch ON stock_batches(product_id, branch_id);
CREATE INDEX IX_stock_expiry ON stock_batches(exp_date, branch_id) WHERE amount > 0;

-- Stock movements
CREATE TABLE stock_movements (
    id                   INT PRIMARY KEY IDENTITY(1,1),
    batch_id             INT NOT NULL REFERENCES stock_batches(batch_id),
    movement_type        VARCHAR(50) NOT NULL,  -- sale_reserved, sale_deduction, purchase, etc.
    qty                  REAL NOT NULL CHECK (qty >= 0),
    branch_id            INT NOT NULL REFERENCES branches(branch_id),
    reference_id         INT,
    reference_type       VARCHAR(50),  -- sale, purchase, transfer, return
    notes                NVARCHAR(MAX),
    created_at           DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX IX_movements_batch ON stock_movements(batch_id);
CREATE INDEX IX_movements_ref ON stock_movements(reference_type, reference_id);

-- Sales
CREATE TABLE sale_classes (
    sale_class_id        INT PRIMARY KEY IDENTITY(1,1),
    name_ar              NVARCHAR(255) NOT NULL,
    name_en              VARCHAR(255)
);

CREATE TABLE sales (
    sale_id              INT PRIMARY KEY IDENTITY(1,1),
    branch_id            INT NOT NULL REFERENCES branches(branch_id),
    customer_id          INT REFERENCES customers(customer_id),
    cashier_id           INT REFERENCES employees(employee_id),
    delivery_man_id      INT REFERENCES employees(employee_id),
    sale_class_id        INT REFERENCES sale_classes(sale_class_id),
    sale_date            DATETIME2 NOT NULL,
    total_gross          MONEY NOT NULL DEFAULT 0 CHECK (total_gross >= 0),
    total_discount       MONEY NOT NULL DEFAULT 0 CHECK (total_discount >= 0),
    total_net            MONEY NOT NULL DEFAULT 0 CHECK (total_net >= 0),
    cash_paid            MONEY NOT NULL DEFAULT 0,
    card_paid            MONEY NOT NULL DEFAULT 0,
    change_given         MONEY NOT NULL DEFAULT 0,
    is_return            BIT NOT NULL DEFAULT 0,
    is_credit            BIT NOT NULL DEFAULT 0,
    payment_method       VARCHAR(50) DEFAULT 'cash',
    original_sale_id     INT REFERENCES sales(sale_id),
    created_at           DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX IX_sales_date ON sales(sale_date);
CREATE INDEX IX_sales_branch_date ON sales(branch_id, sale_date);

-- Sale lines
CREATE TABLE sale_lines (
    line_id              INT PRIMARY KEY IDENTITY(1,1),
    sale_id              INT NOT NULL REFERENCES sales(sale_id),
    product_id           INT NOT NULL REFERENCES products(product_id),
    batch_id             INT REFERENCES stock_batches(batch_id),
    amount               REAL NOT NULL CHECK (amount > 0),
    sell_price           MONEY NOT NULL,
    buy_price            MONEY NOT NULL,
    disc_money           MONEY NOT NULL DEFAULT 0,
    total_sell           MONEY NOT NULL,
    is_return            BIT NOT NULL DEFAULT 0,
    qty_sold             REAL,
    unit_price           MONEY,
    unit_cost            MONEY DEFAULT 0
);
CREATE INDEX IX_sale_lines_sale ON sale_lines(sale_id);

-- Purchases
CREATE TABLE purchases (
    purchase_id          INT PRIMARY KEY IDENTITY(1,1),
    branch_id            INT NOT NULL REFERENCES branches(branch_id),
    vendor_id            INT NOT NULL REFERENCES vendors(vendor_id),
    bill_date            DATE NOT NULL,
    bill_number          VARCHAR(50),
    total_gross          MONEY NOT NULL DEFAULT 0,
    total_discount       MONEY NOT NULL DEFAULT 0,
    total_tax            MONEY NOT NULL DEFAULT 0,
    is_return            BIT NOT NULL DEFAULT 0,
    created_at           DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX IX_purchases_branch_date ON purchases(branch_id, bill_date);

-- Purchase lines
CREATE TABLE purchase_lines (
    line_id              INT PRIMARY KEY IDENTITY(1,1),
    purchase_id          INT NOT NULL REFERENCES purchases(purchase_id),
    product_id           INT NOT NULL REFERENCES products(product_id),
    batch_id             INT REFERENCES stock_batches(batch_id),
    amount               REAL NOT NULL CHECK (amount > 0),
    buy_price            MONEY NOT NULL,
    exp_date             DATE
);

-- Cashier shifts
CREATE TABLE cashier_shifts (
    shift_id             INT PRIMARY KEY IDENTITY(1,1),
    cashier_id           INT NOT NULL REFERENCES employees(employee_id),
    branch_id            INT NOT NULL REFERENCES branches(branch_id),
    opening_float        MONEY NOT NULL DEFAULT 0,
    closing_float        MONEY,
    opened_at            DATETIME2 NOT NULL DEFAULT GETDATE(),
    closed_at            DATETIME2,
    closing_notes        NVARCHAR(MAX),
    created_at           DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX IX_shifts_cashier_open ON cashier_shifts(cashier_id, closed_at) WHERE closed_at IS NULL;

-- Ledger
CREATE TABLE ledger_entries (
    entry_id             INT PRIMARY KEY IDENTITY(1,1),
    branch_id            INT NOT NULL REFERENCES branches(branch_id),
    entry_date           DATETIME2 NOT NULL,
    account_type         VARCHAR(50) NOT NULL,  -- customer, vendor, cash, branch, general
    account_ref          INT,
    ref_type             VARCHAR(50),
    ref_id               INT,
    debit                MONEY NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit               MONEY NOT NULL DEFAULT 0 CHECK (credit >= 0),
    note                 NVARCHAR(MAX),
    created_at           DATETIME2 NOT NULL DEFAULT GETDATE()
);
CREATE INDEX IX_ledger_branch ON ledger_entries(branch_id, entry_date);

-- ============================================================================
-- Step 5: Seed initial branches
-- ============================================================================
INSERT INTO branches (code, name_ar, name_en, is_pilot, is_active)
VALUES
    ('MAIN', N'الرئيسي', 'Main', 0, 1),
    ('ELSANTA', N'السنتا', 'Elsanta', 1, 1),
    ('MSHALA', N'مشعل', 'Mshala', 1, 1);
GO

INSERT INTO jobs (name_ar, name_en)
VALUES
    (N'كاشير', 'Cashier'),
    (N'مدير', 'Manager'),
    (N'موظف مخزن', 'Warehouse Staff');
GO

INSERT INTO sale_classes (name_ar, name_en)
VALUES
    (N'نقدي', 'Cash'),
    (N'آجل', 'Credit');
GO

-- ============================================================================
-- Step 6: Verification
-- ============================================================================
SELECT 'ProCare database created successfully!' AS Status;
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo' ORDER BY TABLE_NAME;
GO

-- ============================================================================
-- Security: revoke public permissions
-- ============================================================================
REVOKE CONNECT FROM [public];
GO

PRINT 'Setup complete. Next: Update config/connections.json with credentials and run ETL mirror.';
