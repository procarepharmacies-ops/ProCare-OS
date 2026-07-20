# eStock Database — Reference (source of truth to mirror)

> Extracted from the **eStock Database Full‑Picture Report**.
> Database: `stock` (`stock_phy_ver1.8.0.0`) on LAN host `192.168.1.2`.
> Report generated from the live database on host `DESKTOP-SHTFS3J` — **2026‑06‑23**.

This is the faithful map of **what data exists in eStock** and **what ProCare OS must read during the
Phase‑1 mirror**. ProCare reproduces this functional surface in its **own clean, independent schema**
(real FKs, indexes, NON‑NULL dates, no broken views) and **never writes back** to eStock — read‑only
ETL via a dedicated read‑only SQL login only.

Related docs: [`01-architecture.md`](01-architecture.md) ·
[`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md) ·
[`07-multi-branch.md`](07-multi-branch.md) ·
[`06-roadmap.md`](06-roadmap.md). ProCare's clean target schema lives in
[`../sql/procare-schema.sql`](../sql/procare-schema.sql); ready read‑only queries in
[`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql).

---

## Scale

| Metric | Value |
|---|---|
| Products | 53,474 |
| Sales invoices | 95,088 headers / 183,906 lines |
| Sales returns | 4,359 headers / 4,212 lines |
| Purchase invoices | 685 headers / 9,230 lines |
| Opening stock | 249 headers / 3,400 lines |
| Customers | 1,197 |
| Vendors | 87 / Manufacturer companies 1,210 |
| Branches | **2 (Elsanta السنطه + Mas-hala مسهله)** |
| Stock batches (Product_Amount) | 35,404 |
| Per‑branch stock rows (Branches_Product_Amount) | 121,625 |
| Stock‑change audit rows | 265,249 |
| Time‑clock events | 2,813,466 |
| Login‑audit rows | 4,057 |

---

## Known data‑quality errors in eStock (carry the workarounds into the ETL)

| Issue | Count | Severity | Why it matters |
|-------|------:|----------|----------------|
| Broken views referencing tables that don't exist (`Item_Catalog`, `Pur_trans_h`, `Store_trans_h`, …) | 8 views | **CRITICAL** | Querying them crashes |
| Expired batches still flagged as in stock | 74 batches | High | Wrong stock figures |
| Customers over their credit limit | 61 customers | Medium | Credit control bypassed |
| `bill_date` is NULL on recent sales | all recent records | High | Date‑range reports are wrong |
| Zero/negative stock batches | 33,249 | Normal | Sold‑out batches that clutter queries |
| No foreign keys enforced | DB‑wide | Risk | Orphaned records possible over time |
| No stored procedures / functions (logic trapped in the `.exe`) | DB‑wide | — | Business logic must be re‑implemented in ProCare |

Full handling rules are in [`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md). The
non‑negotiable ETL rules:

- **`bill_date` NULL →** read `COALESCE(bill_date, insert_date)` as the true sale date.
- **Exclude returns** from sales totals: `back IS NULL OR back <> 'Y'`.
- **Available stock** = `amount > 0` **AND** not expired (`exp_date > GETDATE() OR product_has_expire = 'N'`).
- **FEFO** = `ORDER BY exp_date ASC` (sell the oldest‑expiring batch first).

---

## Tables by module

The eStock schema groups into **8 functional modules**. Row counts below are exactly as reported
(2026‑06‑23). Tables with `0` rows are unused features that still ship in the schema — ProCare carries
forward only what is live, but documents the lot so nothing is silently dropped.

### Module 1 — Products & Inventory
| Table | Rows | Purpose |
|-------|-----:|---------|
| `Products` | 53,474 | Master product catalog. 61 columns (names ar/en, codes, scientific name, sell/buy/tax price, 3 unit types, 14 barcode slots, `product_drug` flag, `deleted`/`active`) |
| `Product_Amount` | 35,404 | **Real‑time batch stock**: `product_id` + `store_id` + `counter_id` (batch) + `exp_date` → `amount`, `buy_price`, `sell_price` |
| `Product_amount_Change` | 265,249 | Audit log of every stock change |
| `Product_amount_reg_update` | 10,818 | Periodic stock reconciliation updates |
| `Product_amount_update` | 79 | Manual stock adjustment records |
| `Product_Changes` | 1,831 | Product master data edits log |
| `Product_price_change` | 157 | Price change history |
| `Product_groups` | 437 | Product categories |
| `Product_description` | 250 | Extra product descriptions |
| `Product_Dose` | 69 | Dosage information |
| `Product_units` | 26 | Unit definitions (tablet, box, strip, …) |
| `Product_Vendor` | 3,301 | Product ↔ supplier mapping |
| `Shortcoming` | 5,754 | Items below the minimum stock threshold |
| `barcode_temp` | 2 | Temp table for barcode printing |

### Module 2 — Sales
| Table | Rows | Purpose |
|-------|-----:|---------|
| `Sales_header` | 95,088 | Invoice header: `sales_id`, `store_id`, `customer_id`, `bill_date`, `total_bill`, `total_bill_net`, `bill_cash`, `cashier_id`, `sale_class`, `network_id`, `delivery_man_id` |
| `Sales_details` | 183,906 | Invoice lines: `product_id`, `counter_id` (batch), `exp_date`, `amount`, `sell_price`, `buy_price`, `disc_money`, `total_sell`, `back` flag |
| `Sales_header_Temp` | 0 | Pending/in‑progress sales (cleared after save) |
| `Sales_details_Temp` | 0 | Pending sale lines |
| `Back_sales_header` | 4,359 | Sales return invoices |
| `Back_Sales_details` | 4,212 | Sales return line items |
| `Sales_delivery_header` | 0 | Delivery orders header |
| `Sales_delivery_details` | 0 | Delivery order lines |
| `Sales_delivery_del_header/details` | 0 | Deleted delivery records |
| `Cash_disk_close` | 1,647 | Cashier end‑of‑shift closure records |
| `Cash_depots` | 6 | Cash vault / safe deposits |
| `Sale_classes` | 2 | Sale type classification |

### Module 3 — Purchasing
| Table | Rows | Purpose |
|-------|-----:|---------|
| `Purchase_header` | 685 | Purchase invoices: `purchase_id`, `vendor_id`, `store_id`, `bill_date`, `total_bill`, `bill_disc_per`, `bill_tax` |
| `Purchase_details` | 9,230 | Purchase lines: `product_id`, `amount`, `bouns` (bonus/free units, spelled as in eStock), `buy_price`, `sell_price`, `gain_price`, `exp_date` |
| `Back_purchase_header` | 0 | Purchase return headers |
| `Back_purchase_details` | 0 | Purchase return lines |
| `Temp_Purchase_header` | 3 | In‑progress purchase entry (header) |
| `Temp_Purchase_details` | 6 | In‑progress purchase entry (lines) |
| `Order_header` | 0 | Purchase orders to suppliers |
| `Order_details` | 0 | Purchase order lines |
| `Start_stock_header` | 249 | Opening stock entries |
| `Start_stock_details` | 3,400 | Opening stock line items |
| `Store_convert_header/details` | 0 | Between‑store transfers (single‑store era; superseded by Module 7 branch transfers) |

### Module 4 — Customers & Financial
| Table | Rows | Purpose |
|-------|-----:|---------|
| `Customer` | 1,197 | `customer_id`, names ar/en, `mobile`, `customer_max_money` (credit limit), `customer_current_money` (balance), `customer_disc_local/import`, `area_id`, `sales_man`, `sale_class_id` |
| `Customer_Area` | 1 | Geographic area definitions |
| `Customer_Class` | 2 | Customer classification (retail / wholesale) |
| `customer_contracts` | 0 | Insurance / contract pricing |
| `Checks` | 0 | Post‑dated check tracking |
| `installment` | 0 | Payment installment plans |
| `Tuning_accounts` | 293 | Manual account adjustments |
| `Account_Tree` | 120 | Chart of accounts |
| `Co_bank` | 3 | Bank account definitions |
| `Gedo_Financial` | 93,925 | General ledger / financial journal |
| `Gedo_customers` | 88,359 | Customer ledger transactions |
| `Gedo_Vendors` | 2,878 | Vendor ledger transactions |

### Module 5 — Vendors / Suppliers
| Table | Rows | Purpose |
|-------|-----:|---------|
| `Vendor` | 87 | `vendor_id`, names ar/en, `tel`, `mobile`, `vendor_max_money`, `vendor_current_money`, employee contacts for delivery/collection |
| `Companys` | 1,210 | Manufacturer / distributor companies |
| `company_Owner` | 2 | Ownership info |
| `co_inf` | 1 | Your pharmacy's own info (name, logo, license, etc.) — 42 columns |

### Module 6 — Employees & HR
| Table | Rows | Purpose |
|-------|-----:|---------|
| `Employee` | 11 | 55 columns: `emp_id`, names ar/en, `job_id`, `basic_salary`, `username`, `pass`, `max_disc_per`, 20+ permission flags |
| `Employee_salary` | 215 | Monthly salary records |
| `Employee_daily_time` | 2,813,466 | Time clock — every clock‑in/out event |
| `Employee_work_time` | 4 | Work schedule definitions |
| `Employee_cash_advance` | 0 | Salary advance requests |
| `Employee_commission` | 0 | Sales commissions |
| `Employee_absence_money` | 0 | Absence deductions |
| `EMP_CONTROL` | 30 | System‑level employee permissions (**198 columns**) |
| `Jobs` | 8 | Job title definitions |
| `user_login` | 4,057 | Login audit trail |

### Module 7 — Branches / Multi‑Store  ← **Elsanta + Mas-hala**
| Table | Rows | Purpose |
|-------|-----:|---------|
| `Branches` | **2** | Branch definitions (52 columns — full config per branch) — Elsanta + Mas-hala |
| `Branches_Product_Amount` | 121,625 | Stock per branch (mirrors `Product_Amount`) |
| `Branches_sales_header/details` | 0 | Branch‑specific sales (replication target) |
| `Branches_purchase_header/details` | 0 | Branch purchasing |
| `Branches_customer/Vendor` | 0 | Branch‑level customer/vendor lists |
| `Branch_order_header` | 8,204 | **Inter‑branch transfer orders** |
| `Branch_order_details` | 61,872 | Transfer order lines |
| `Branch_money_order` | 1,102 | Cash transfer orders between branches |
| `Branch_money_convert` | 1,098 | Executed cash transfers |
| `Gedo_branches` | 9,271 | Branch financial ledger |

> This module is how Mas-hala (مسهله) and Elsanta (السنطه) are connected. ProCare replicates it — every
> operational row carries a `branch_id`. See [`07-multi-branch.md`](07-multi-branch.md).

### Module 8 — System / Config
| Table | Rows | Purpose |
|-------|-----:|---------|
| `Stores` | 1 | Physical store / warehouse definitions |
| `Sites` | 314 | Product shelf locations |
| `Flag` | 55 | System feature flags |
| `News_bar` | 0 | Scrolling news / announcements |
| `versions` | 19 | DB upgrade version log |
| `Run_Backup` | 0 | Scheduled backup log |
| `DB_online_update_Error` | 23 | Failed online‑sync errors |

---

## Key columns to carry over

### `Products` (61 columns)
| Column | Type | Notes |
|--------|------|-------|
| `product_id` | decimal | **PK** |
| `product_code` | varchar(50) | Barcode / internal code |
| `product_fast_code` | varchar(20) | Quick‑entry code |
| `product_name_ar` | varchar(100) | Arabic name |
| `product_name_en` | varchar(100) | English name |
| `product_scientific_name` | nvarchar(200) | Generic / scientific name |
| `product_drug` | char(1) | Is it a controlled drug? |
| `company_id` | decimal | → `Companys` |
| `product_has_expire` | char(1) | Tracks expiry dates? |
| `sell_price` | money | Default sell price (unit1) |
| `buy_price` | money | Last purchase price |
| `tax_price` | money | Tax amount |
| `unit2_sell_price` | money | Strip / pack price |
| `unit3_sell_price` | money | Box / carton price |
| `sell_clause` | money | Wholesale price |
| `product_unit1/2/3` | decimal | Unit IDs → `Product_units` |
| `product_buy_number` | decimal | Qty per purchase unit |
| `group_id` | decimal | → `Product_groups` |
| `deleted` | char(1) | Soft‑delete flag |
| `active` | char(1) | Active flag |
| `amount_zero` | char(1) | Allow sale when out of stock |

### `Sales_header` (38 columns)
| Column | Type | Notes |
|--------|------|-------|
| `sales_id` | decimal | **PK** |
| `store_id` | decimal | → `Stores` |
| `customer_id` | decimal | → `Customer` (**0 = walk‑in**) |
| `bill_date` | datetime | Invoice date (**often NULL — bug**) |
| `total_bill` | money | Before discounts |
| `total_bill_net` | money | After all discounts |
| `bill_cash` | money | Cash paid |
| `money_change` | money | Change given |
| `network_id` | decimal | POS network / card payment |
| `network_money` | money | Card payment amount |
| `cashier_id` | varchar(50) | → `Employee.username` |
| `total_disc_per` | decimal | Overall discount % |
| `total_disc_money` | money | Overall discount amount |
| `customer_disc_per` | decimal | Customer‑specific discount % |
| `sale_class` | int | → `Sale_classes` |
| `back` | char(1) | `'Y'` = return invoice |
| `delivery_man_id` | decimal | → `Employee` |
| `insert_date` | datetime | **Actual record creation time** (reliable fallback for `bill_date`) |

### `Sales_details` (24 columns)
| Column | Type | Notes |
|--------|------|-------|
| `details_id` | decimal | **PK** |
| `sales_id` | decimal | → `Sales_header` |
| `product_id` | decimal | → `Products` |
| `counter_id` | decimal | → `Product_Amount` batch |
| `exp_date` | datetime | Batch expiry date |
| `amount` | float | Quantity sold |
| `sell_price` | money | Actual sell price used |
| `buy_price` | money | Cost price (for profit calc) |
| `disc_money` | money | Line discount amount |
| `disc_per` | decimal | Line discount % |
| `total_sell` | money | Line total after discount |
| `back` | char(1) | `'Y'` = returned line |
| `back_amount` | float | Returned quantity |
| `back_price` | money | Refund price |
| `sale_unit_change` | decimal | Unit conversion factor used |

### `Product_Amount` (16 columns) — real‑time stock
| Column | Type | Notes |
|--------|------|-------|
| `pa_id` | decimal | **PK** |
| `product_id` | decimal | → `Products` |
| `store_id` | decimal | → `Stores` |
| `counter_id` | decimal | Batch identifier |
| `vendor_id` | decimal | Which supplier this batch came from |
| `amount` | decimal | Current stock quantity |
| `buy_price` | money | Batch purchase price |
| `sell_price` | money | Batch sell price |
| `tax_price` | money | Tax |
| `exp_date` | datetime | Expiry date |
| `Product_update` | char(1) | Needs price‑sync flag |

### `Purchase_header` (27 columns)
| Column | Type | Notes |
|--------|------|-------|
| `purchase_id` | decimal | **PK** |
| `vendor_id` | decimal | → `Vendor` |
| `store_id` | decimal | → `Stores` |
| `bill_date` | datetime | Invoice date |
| `bill_number` | varchar(50) | Supplier invoice number |
| `total_bill` | money | Gross total |
| `bill_disc_per` | float | Invoice‑level discount % |
| `bill_disc_money` | money | Invoice‑level discount amount |
| `bill_tax` | money | Tax on invoice |
| `bill_other_expenses` | money | Extra charges |
| `back` | char(1) | Is this a return? |
| `total_back` | money | Total returned amount |

### `Customer` (31 columns)
| Column | Type | Notes |
|--------|------|-------|
| `customer_id` | decimal | **PK** |
| `customer_name_ar` | varchar(50) | Arabic name |
| `customer_name_en` | varchar(50) | English name |
| `mobile` | varchar(20) | Phone |
| `customer_class_id` | decimal | → `Customer_Class` |
| `customer_max_money` | money | **Credit limit** |
| `customer_current_money` | money | **Current outstanding balance** |
| `customer_start_money` | money | Opening balance |
| `customer_disc_local` | float | Local product discount % |
| `customer_disc_import` | float | Import product discount % |
| `area_id` | decimal | → `Customer_Area` |
| `sales_man` | decimal | → `Employee` (assigned rep) |
| `sale_class_id` | decimal | → `Sale_classes` |
| `active` | char(1) | Active flag |
| `deleted` | char(1) | Soft delete |

### `Employee` (55 columns) — permission flags
The permission model is what ProCare's roles must reproduce (see `EMP_CONTROL` — 198 system‑level
columns — for the full matrix).

| Permission column | Meaning |
|-------------------|---------|
| `max_disc_per` | Maximum discount % allowed |
| `max_disc_money` | Maximum discount amount allowed |
| `show_buy` | Can see purchase prices |
| `emp_add_product` | Can add new products |
| `emp_edit_product` | Can edit products |
| `emp_edit_sell_price` | Can change sell price at POS |
| `emp_add_cust` / `emp_edit_cust` / `emp_del_cust` | Customer management rights |
| `allaw_r_sale` | Can process returns |
| `allaw_sale_credit` | Can sell on credit |
| `allaw_un_sale` | Can void sales |
| `allaw_sale_delivery` | Can create delivery orders |
| `emp_show_money` | Can see financial totals |
| `emp_change_cash_disk` | Can open / change shift |
| `emp_r_sale_bill_num` | Number of days returns may be back‑dated |

---

## The 8 broken views (drop or rewrite — do **not** mirror)

All 8 views reference old‑schema tables that no longer exist; querying them crashes. ProCare ignores
them entirely and rebuilds equivalents cleanly.

| Broken view | References (missing) |
|-------------|----------------------|
| `item_purchasing` | `Pur_trans_h`, `Stores` (old name) |
| `item_changes_report` | `Item_Catalog`, `Item_changes` |
| `Item_catalog_date` | `Item_Catalog`, `Companys` |
| `item_qty_chang_report` | `Item_Catalog`, `Item_qty_chang` |
| `item_qty_update_report` | `Item_Catalog`, `Item_qty_update` |
| `item_return_purchasing` | `Pur_trans_h_r` |
| `store_convert_report` | `Store_trans_h` |
| `store_item_qty` | `Item_Class_Store`, `Item_Catalog` |

---

## Programmability — why the logic must move into ProCare

The eStock DB contains **zero custom stored procedures and zero functions**. Only SQL Server system
objects exist; all business logic lives in the application `.exe`.

| Object type | Count | Detail |
|-------------|------:|--------|
| Custom stored procedures | 0 | None |
| Custom functions | 0 | None |
| System SPs (`dt_*`) | 22 | Source‑control stubs — unused |
| System SPs (`sp_*diagram`) | 6 | Diagram support — unused |
| Function (`fn_diagramobjects`) | 1 | System only |

ProCare moves stock deduction, profit calculation, credit checking and FEFO selection into its own
FastAPI service layer (and SQL stored procedures where appropriate), so the logic is testable,
auditable, and no longer trapped in a closed binary.

---

## Application menu (the 9 modules to mirror)

```
MAIN MENU
1. SALES (POS)      — New Sale Invoice, Sale Returns, Cash Desk (Shift Open/Close), Delivery Orders
2. PURCHASING       — New Purchase Invoice, Purchase Returns, Purchase Orders (to suppliers)
3. INVENTORY        — Product Master, Stock by Batch (with expiry), Stock Adjustments,
                      Store/Branch Transfers, Shortcoming / Low Stock, Opening Stock Entry
4. CUSTOMERS        — Customer Master, Customer Account Statement, Credit Management
5. VENDORS          — Vendor Master, Vendor Account Statement
6. HR / EMPLOYEES   — Employee Master + Permissions, Salary Management, Time & Attendance
7. ACCOUNTS         — Chart of Accounts, General Ledger, Manual Journal Entries
8. REPORTS          — Sales (daily/monthly/by product/by cashier/by customer), Purchasing,
                      Profit & Loss, Stock & Expiry, Customer/Vendor Statements
9. SETTINGS         — Company Info (co_inf), Stores & Branches, User Management, Backup & Restore
```

ProCare reproduces all 9 in Arabic‑first (RTL) UI with an optional English toggle; light is default
with an optional dark toggle. See [`01-architecture.md`](01-architecture.md).

---

## Core business rules eStock keeps inside its `.exe`

These are the rules ProCare re‑implements in code / stored procedures (eStock has none). The patterns
below are reconstructed from the report's "How to build a program like eStock" SQL.

### 1. New sale — header, lines, per‑batch stock deduction, audit
A sale is a four‑step transaction: insert `Sales_header`, insert each `Sales_details` line, **deduct
stock per batch** (`UPDATE Product_Amount SET amount = amount - @qty WHERE counter_id = @counter_id
AND store_id = @store_id`), then write an audit row to `Product_amount_Change`. ProCare wraps all four
in one atomic transaction with a `amount >= 0` check constraint so negative stock is impossible.

### 2. FEFO — First Expire, First Out
Stock lookup orders candidate batches by `exp_date ASC`, filtering `amount > 0` and
`(exp_date > GETDATE() OR product_has_expire = 'N')`. The oldest‑expiring valid batch sells first.

### 3. Profit per sale
`gross_profit = Σ total_sell − Σ(amount × buy_price)`, joining `Sales_header` → `Sales_details` over a
date range. Cost is the **line‑level `buy_price`** captured at sale time, not the current product cost.

### 4. Customer credit check
`available_credit = customer_max_money − customer_current_money`. In ProCare this is enforced at POS
via `sp_check_credit`; exceeding the limit requires an explicit override carrying the
`allaw_sale_credit` permission (this is exactly the control eStock failed to enforce — 61 customers
are currently over limit).

> Ready, parameter‑safe READ‑ONLY versions of these queries (today's revenue, month‑over‑month, top
> products, expiring‑in‑30‑days, low stock, debtors, vendor payables, daily/hourly sales, cashier
> performance) are in [`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql). ProCare's clean
> target schema is in [`../sql/procare-schema.sql`](../sql/procare-schema.sql).

---

## What is still TBD

- **Titan / Drug‑Eye schema** (path `D:\Labirdo`) — source of truth for drug NAMES and
  SUBSTITUTION/alternatives (and interactions/dosing). Its DB schema is **not yet audited**. See
  [`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md).
- **Read‑only SQL login credentials** for the ETL — to be provisioned; never committed to git
  (`config/connections.json` is git‑ignored; only `connections.example.json` is committed).
- **Exact `Branches` IDs / per‑branch config** (52 columns/branch) — captured during the mirror phase.
