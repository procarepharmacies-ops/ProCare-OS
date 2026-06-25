-- ===========================================================================
-- ProCare OS — clean schema, SQLite dialect (demo / shadow database)
-- ---------------------------------------------------------------------------
-- This is a faithful, portable translation of ../../../../sql/procare-schema.sql
-- (the SQL Server system-of-record schema). Table and column names are kept
-- IDENTICAL so every query in app/queries.py, the whitelist views, and the AI
-- assistant run unchanged against either SQLite (this demo DB) or the real
-- SQL Server ProCare database.
--
-- Type mapping SQL Server -> SQLite:
--   INT IDENTITY(1,1)  -> INTEGER PRIMARY KEY AUTOINCREMENT
--   NVARCHAR/VARCHAR   -> TEXT
--   MONEY/DECIMAL      -> REAL
--   BIT                -> INTEGER (0/1)  with CHECK (col IN (0,1))
--   DATETIME2/DATE     -> TEXT (ISO-8601: 'YYYY-MM-DD' / 'YYYY-MM-DD HH:MM:SS')
--
-- The data-quality guarantees from the SQL Server schema are preserved:
--   * real FOREIGN KEYS everywhere      (PRAGMA foreign_keys = ON at connect)
--   * CHECK (amount >= 0) on stock       -> no zero/negative batch debt
--   * sale_date is NOT NULL              -> eStock's NULL bill_date bug is fixed
--   * indexes (incl. partial) from day one
-- ===========================================================================

PRAGMA foreign_keys = ON;

-- 1) BRANCHES -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS branches (
    branch_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    NOT NULL UNIQUE,                 -- MAIN / ELSANTA
    name_ar     TEXT    NOT NULL,
    name_en     TEXT    NOT NULL,
    is_pilot    INTEGER NOT NULL DEFAULT 0 CHECK (is_pilot IN (0,1)),
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 2) REFERENCE / LOOKUP -------------------------------------------------------
CREATE TABLE IF NOT EXISTS companies (
    company_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ar     TEXT    NOT NULL,
    name_en     TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);
CREATE TABLE IF NOT EXISTS product_groups (
    group_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ar     TEXT    NOT NULL,
    name_en     TEXT
);
CREATE TABLE IF NOT EXISTS units (
    unit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ar     TEXT    NOT NULL,                        -- علبة / شريط / قرص
    name_en     TEXT                                     -- box / strip / tablet
);
CREATE TABLE IF NOT EXISTS sale_classes (
    sale_class_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ar       TEXT  NOT NULL,
    name_en       TEXT
);
CREATE TABLE IF NOT EXISTS customer_classes (
    customer_class_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ar           TEXT NOT NULL,                     -- تجزئة / جملة
    name_en           TEXT
);

-- 3) PRODUCTS -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    product_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT,
    fast_code       TEXT,
    name_ar         TEXT    NOT NULL,
    name_en         TEXT,
    scientific_name TEXT,                                -- Titan/Drug-Eye map key
    titan_drug_id   INTEGER,                             -- soft link (schema TBD)
    company_id      INTEGER REFERENCES companies(company_id),
    group_id        INTEGER REFERENCES product_groups(group_id),
    unit1_id        INTEGER REFERENCES units(unit_id),
    unit2_id        INTEGER REFERENCES units(unit_id),
    unit3_id        INTEGER REFERENCES units(unit_id),
    is_controlled   INTEGER NOT NULL DEFAULT 0 CHECK (is_controlled IN (0,1)),
    has_expiry      INTEGER NOT NULL DEFAULT 1 CHECK (has_expiry IN (0,1)),
    allow_sale_zero INTEGER NOT NULL DEFAULT 0 CHECK (allow_sale_zero IN (0,1)),
    sell_price      REAL    NOT NULL DEFAULT 0 CHECK (sell_price >= 0),
    buy_price       REAL    NOT NULL DEFAULT 0 CHECK (buy_price >= 0),
    tax_price       REAL    NOT NULL DEFAULT 0 CHECK (tax_price >= 0),
    unit2_sell_price REAL,
    unit3_sell_price REAL,
    wholesale_price REAL,
    min_stock       REAL    NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    is_deleted      INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS IX_products_code       ON products(code)            WHERE code IS NOT NULL;
CREATE INDEX IF NOT EXISTS IX_products_scientific  ON products(scientific_name) WHERE scientific_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS IX_products_name_ar     ON products(name_ar);

CREATE TABLE IF NOT EXISTS product_barcodes (
    barcode_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL REFERENCES products(product_id),
    barcode     TEXT    NOT NULL UNIQUE,
    unit_id     INTEGER REFERENCES units(unit_id)
);

-- 4) CUSTOMERS & VENDORS ------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    customer_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ar           TEXT    NOT NULL,
    name_en           TEXT,
    mobile            TEXT,
    customer_class_id INTEGER REFERENCES customer_classes(customer_class_id),
    credit_limit      REAL    NOT NULL DEFAULT 0,        -- eStock customer_max_money
    current_balance   REAL    NOT NULL DEFAULT 0,        -- eStock customer_current_money
    opening_balance   REAL    NOT NULL DEFAULT 0,
    disc_local        REAL    NOT NULL DEFAULT 0,
    disc_import       REAL    NOT NULL DEFAULT 0,
    is_active         INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    is_deleted        INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1)),
    created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS IX_customers_mobile ON customers(mobile) WHERE mobile IS NOT NULL;
CREATE INDEX IF NOT EXISTS IX_customers_name   ON customers(name_ar);

CREATE TABLE IF NOT EXISTS vendors (
    vendor_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ar         TEXT    NOT NULL,
    name_en         TEXT,
    tel             TEXT,
    mobile          TEXT,
    credit_limit    REAL    NOT NULL DEFAULT 0,
    current_balance REAL    NOT NULL DEFAULT 0,          -- what we owe the vendor
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 5) EMPLOYEES ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    job_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ar TEXT NOT NULL,
    name_en TEXT
);
CREATE TABLE IF NOT EXISTS employees (
    employee_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ar             TEXT    NOT NULL,
    name_en             TEXT,
    username            TEXT    NOT NULL UNIQUE,
    password_hash       TEXT    NOT NULL,                -- ProCare hashes (eStock stored plaintext)
    job_id              INTEGER REFERENCES jobs(job_id),
    branch_id           INTEGER REFERENCES branches(branch_id),
    basic_salary        REAL    NOT NULL DEFAULT 0,
    max_disc_per        REAL    NOT NULL DEFAULT 0,
    max_disc_money      REAL    NOT NULL DEFAULT 0,
    return_backdate_days INTEGER NOT NULL DEFAULT 0,
    can_see_buy_price   INTEGER NOT NULL DEFAULT 0 CHECK (can_see_buy_price IN (0,1)),
    can_edit_sell_price INTEGER NOT NULL DEFAULT 0 CHECK (can_edit_sell_price IN (0,1)),
    can_add_product     INTEGER NOT NULL DEFAULT 0 CHECK (can_add_product IN (0,1)),
    can_edit_product    INTEGER NOT NULL DEFAULT 0 CHECK (can_edit_product IN (0,1)),
    can_sale_credit     INTEGER NOT NULL DEFAULT 0 CHECK (can_sale_credit IN (0,1)),
    can_return          INTEGER NOT NULL DEFAULT 0 CHECK (can_return IN (0,1)),
    can_void            INTEGER NOT NULL DEFAULT 0 CHECK (can_void IN (0,1)),
    can_delivery        INTEGER NOT NULL DEFAULT 0 CHECK (can_delivery IN (0,1)),
    can_change_shift    INTEGER NOT NULL DEFAULT 0 CHECK (can_change_shift IN (0,1)),
    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 6) STOCK — batch-level, per branch ------------------------------------------
CREATE TABLE IF NOT EXISTS stock_batches (
    batch_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id     INTEGER NOT NULL REFERENCES products(product_id),
    branch_id      INTEGER NOT NULL REFERENCES branches(branch_id),
    vendor_id      INTEGER REFERENCES vendors(vendor_id),
    source_counter INTEGER,
    amount         REAL    NOT NULL DEFAULT 0 CHECK (amount >= 0),  -- kills 33,249 neg-batch debt
    buy_price      REAL    NOT NULL DEFAULT 0,
    sell_price     REAL    NOT NULL DEFAULT 0,
    tax_price      REAL    NOT NULL DEFAULT 0,
    exp_date       TEXT,                                            -- NULL only when has_expiry = 0
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS IX_stock_product_branch ON stock_batches(product_id, branch_id);
CREATE INDEX IF NOT EXISTS IX_stock_branch         ON stock_batches(branch_id);
CREATE INDEX IF NOT EXISTS IX_stock_expiry         ON stock_batches(exp_date, branch_id) WHERE amount > 0;

CREATE TABLE IF NOT EXISTS stock_movements (
    movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id    INTEGER NOT NULL REFERENCES stock_batches(batch_id),
    branch_id   INTEGER NOT NULL REFERENCES branches(branch_id),
    delta       REAL    NOT NULL,
    reason      TEXT    NOT NULL CHECK
        (reason IN ('sale','purchase','transfer_out','transfer_in','adjust','writeoff','opening','return','lock')),
    ref_id      INTEGER,
    employee_id INTEGER REFERENCES employees(employee_id),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS IX_movements_batch ON stock_movements(batch_id);
CREATE INDEX IF NOT EXISTS IX_movements_ref   ON stock_movements(reason, ref_id);

-- 7) SALES --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales (
    sale_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id       INTEGER NOT NULL REFERENCES branches(branch_id),
    customer_id     INTEGER REFERENCES customers(customer_id),     -- NULL = walk-in
    cashier_id      INTEGER REFERENCES employees(employee_id),
    delivery_man_id INTEGER REFERENCES employees(employee_id),
    sale_class_id   INTEGER REFERENCES sale_classes(sale_class_id),
    sale_date       TEXT    NOT NULL,                               -- COALESCE(bill_date, insert_date) fix
    total_gross     REAL    NOT NULL DEFAULT 0 CHECK (total_gross >= 0),
    total_discount  REAL    NOT NULL DEFAULT 0 CHECK (total_discount >= 0),
    total_net       REAL    NOT NULL DEFAULT 0 CHECK (total_net >= 0),
    cash_paid       REAL    NOT NULL DEFAULT 0,
    card_paid       REAL    NOT NULL DEFAULT 0,
    change_given    REAL    NOT NULL DEFAULT 0,
    is_return       INTEGER NOT NULL DEFAULT 0 CHECK (is_return IN (0,1)),
    is_credit       INTEGER NOT NULL DEFAULT 0 CHECK (is_credit IN (0,1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS IX_sales_date        ON sales(sale_date);
CREATE INDEX IF NOT EXISTS IX_sales_branch_date ON sales(branch_id, sale_date);
CREATE INDEX IF NOT EXISTS IX_sales_customer    ON sales(customer_id) WHERE customer_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS sale_lines (
    line_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id    INTEGER NOT NULL REFERENCES sales(sale_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    batch_id   INTEGER REFERENCES stock_batches(batch_id),
    amount     REAL    NOT NULL CHECK (amount > 0),
    sell_price REAL    NOT NULL,
    buy_price  REAL    NOT NULL,                                   -- cost snapshot for profit
    disc_money REAL    NOT NULL DEFAULT 0,
    total_sell REAL    NOT NULL,
    is_return  INTEGER NOT NULL DEFAULT 0 CHECK (is_return IN (0,1))
);
CREATE INDEX IF NOT EXISTS IX_sale_lines_sale    ON sale_lines(sale_id);
CREATE INDEX IF NOT EXISTS IX_sale_lines_product ON sale_lines(product_id);

-- 8) PURCHASING ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchases (
    purchase_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id      INTEGER NOT NULL REFERENCES branches(branch_id),
    vendor_id      INTEGER NOT NULL REFERENCES vendors(vendor_id),
    bill_date      TEXT    NOT NULL,
    bill_number    TEXT,
    total_gross    REAL    NOT NULL DEFAULT 0,
    total_discount REAL    NOT NULL DEFAULT 0,
    total_tax      REAL    NOT NULL DEFAULT 0,
    other_expenses REAL    NOT NULL DEFAULT 0,
    is_return      INTEGER NOT NULL DEFAULT 0 CHECK (is_return IN (0,1)),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS IX_purchases_branch_date ON purchases(branch_id, bill_date);
CREATE INDEX IF NOT EXISTS IX_purchases_vendor      ON purchases(vendor_id);

CREATE TABLE IF NOT EXISTS purchase_lines (
    line_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL REFERENCES purchases(purchase_id),
    product_id  INTEGER NOT NULL REFERENCES products(product_id),
    batch_id    INTEGER REFERENCES stock_batches(batch_id),
    amount      REAL    NOT NULL CHECK (amount > 0),
    bonus       REAL    NOT NULL DEFAULT 0,
    buy_price   REAL    NOT NULL,
    sell_price  REAL    NOT NULL,
    exp_date    TEXT
);
CREATE INDEX IF NOT EXISTS IX_purchase_lines_purchase ON purchase_lines(purchase_id);

-- 9) INTER-BRANCH TRANSFERS ---------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_transfers (
    transfer_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    from_branch_id INTEGER NOT NULL REFERENCES branches(branch_id),
    to_branch_id   INTEGER NOT NULL REFERENCES branches(branch_id),
    status         TEXT    NOT NULL DEFAULT 'requested'
                   CHECK (status IN ('requested','in_transit','received','cancelled')),
    requested_by   INTEGER REFERENCES employees(employee_id),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    shipped_at     TEXT,
    received_at    TEXT,
    CHECK (from_branch_id <> to_branch_id)
);
CREATE TABLE IF NOT EXISTS stock_transfer_lines (
    line_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    transfer_id   INTEGER NOT NULL REFERENCES stock_transfers(transfer_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    from_batch_id INTEGER REFERENCES stock_batches(batch_id),
    to_batch_id   INTEGER REFERENCES stock_batches(batch_id),
    amount        REAL    NOT NULL CHECK (amount > 0),
    buy_price     REAL    NOT NULL DEFAULT 0,
    exp_date      TEXT
);
CREATE INDEX IF NOT EXISTS IX_transfer_lines_transfer ON stock_transfer_lines(transfer_id);

CREATE TABLE IF NOT EXISTS cash_transfers (
    cash_transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_branch_id   INTEGER NOT NULL REFERENCES branches(branch_id),
    to_branch_id     INTEGER NOT NULL REFERENCES branches(branch_id),
    amount           REAL    NOT NULL CHECK (amount > 0),
    status           TEXT    NOT NULL DEFAULT 'sent'
                     CHECK (status IN ('sent','received','cancelled')),
    sent_by          INTEGER REFERENCES employees(employee_id),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    received_at      TEXT,
    CHECK (from_branch_id <> to_branch_id)
);

-- 10) FINANCIAL LEDGER --------------------------------------------------------
CREATE TABLE IF NOT EXISTS ledger_entries (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id    INTEGER NOT NULL REFERENCES branches(branch_id),
    entry_date   TEXT    NOT NULL DEFAULT (datetime('now')),
    account_type TEXT    NOT NULL CHECK
        (account_type IN ('customer','vendor','cash','bank','branch','general')),
    account_ref  INTEGER,
    ref_type     TEXT,
    ref_id       INTEGER,
    debit        REAL    NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit       REAL    NOT NULL DEFAULT 0 CHECK (credit >= 0),
    note         TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS IX_ledger_branch_date ON ledger_entries(branch_id, entry_date);
CREATE INDEX IF NOT EXISTS IX_ledger_account     ON ledger_entries(account_type, account_ref);
CREATE INDEX IF NOT EXISTS IX_ledger_ref         ON ledger_entries(ref_type, ref_id);

-- 11) CLINICAL (Titan/Drug-Eye advisory cache) --------------------------------
-- The real Titan schema is TBD (docs/03). This local table backs the advisory
-- drug-interaction lookup so the counter feature works in shadow mode. Output
-- is ALWAYS advisory and NEVER blocks a sale (clinical guardrail).
CREATE TABLE IF NOT EXISTS drug_interactions (
    interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_a   TEXT NOT NULL,                         -- scientific_name
    ingredient_b   TEXT NOT NULL,
    severity       TEXT NOT NULL CHECK (severity IN ('minor','moderate','severe')),
    note_ar        TEXT NOT NULL,
    note_en        TEXT
);
CREATE INDEX IF NOT EXISTS IX_interactions_a ON drug_interactions(ingredient_a);
CREATE INDEX IF NOT EXISTS IX_interactions_b ON drug_interactions(ingredient_b);

-- 12) ETL / RECONCILIATION AUDIT ---------------------------------------------
-- Records each mirror sync + reconciliation pass (Phase 1 validation gate).
CREATE TABLE IF NOT EXISTS etl_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT    NOT NULL,                          -- 'estock' / 'titan' / 'demo_seed'
    kind        TEXT    NOT NULL,                          -- 'full' / 'incremental' / 'seed'
    started_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    status      TEXT    NOT NULL DEFAULT 'running' CHECK (status IN ('running','ok','failed')),
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    note        TEXT
);
