# eStock Software — Full Structural Specification (for Claude Code)

This document describes the **eStock** system (ModernSoft pharmacy ERP, the legacy
SQL Server we mirror FROM) in full structural detail — every module, screen,
menu, submenu, the triggers/alarms, login, employees, shareholders, accounting,
balances, and main-vs-branch logic. Use it to build the ProCare-OS mirror so that
the ProCare frontend faithfully represents the eStock domain.

**Source of truth:** the live eStock databases at
- elsanta (WAN) `196.202.93.37` DB `stock` — store_id 1 (main) + store_id 2 (branch)
- mashala (LAN) `192.168.1.2` DB `stock` — store_id 1 (only)

**Schema verified:** 113 tables on mashala (113 incl. a few elsanta-only). The
table/column names below are the ACTUAL eStock table names. ProCare's `etl.py`
MIRROR_PLAN maps these to ProCare tables — keep that mapping.

**Conventions in eStock:**
- Every transactional table has `insert_uid` (who created) + `insert_date`.
- `update_uid`/`update_date` appear on editable masters.
- `_Temp` tables (e.g. `Sales_header_Temp`, `Sales_details_Temp`) are the
  in-progress/cart buffer before a bill is finalized — ignore for the mirror
  (only finalized `*_header`/`*_details` count as completed sales).
- `store_id` = which physical store the row belongs to (main=1, branch=2).
- `branch_id` (on `Branches_*` tables) = the destination branch for
  inter-branch documents.
- `deleted` / `active` flags on masters = soft-delete / enable toggles.
- `*_current_money` columns = running balances (cash, customer credit, vendor debt).
- `gf_id` = General Financial (Gedo) document id linking to `Gedo_Financial`.
- `class` = document type/classifier (0 = normal sale, etc.).
- `back` / `back_*` = return (مرتجع) data.

---

## 1. LOGIN & AUTH (تسجيل الدخول)

- **`user_login`** (`lu_id, u_id, start_time, end_time, compu_name`) — session log
  of every login/logout per user + machine. This is the login audit trail.
- **`Employee.username` / `Employee.pass`** — the actual credentials live on the
  Employee master (each employee is a user). `use_compu` flag = allowed to use PC.
- **`EMP_CONTROL`** — the **permissions matrix**: one row per `emp_id` with ~200
  boolean columns (A,A1..A35, B,B1..B34, C,C1..C7, D,D1..D11, E,E1..E8, F,F1..F28,
  G,G1..G31, H,H1..H2, I,I1..I21, J,J1..J25). Each column gates a screen/action
  (e.g. `emp_add_product`, `emp_edit_sell_price`, `emp_change_cash_disk`,
  `allaw_sale_credit`, `allaw_sale_delivery`, `emp_del_vendor`). This is the
  role/ACL system — map to ProCare role flags.
- **`co_inf`** — company info (name AR/EN, owner, tax, logo, branch_id,
  master_branch_id) — the "about / company profile" screen.

**Screens:** Login → (username+pass) → main menu filtered by `EMP_CONTROL`
permissions. Logout writes `user_login.end_time`.

---

## 2. EMPLOYEES (الموظفين)

Master: **`Employee`** (`emp_id, emp_code, emp_name_ar/en, emp_gender, job_id,
birth_date, hire_date, work_date, mobile, home_tel, address, card_id, active,
max_disc_per, max_disc_money, … salary_typ, basic_salary, more_salary,
emp_commission1, emp_commission2, absence_money, emp_cust_max_money,
emp_add_product, emp_edit_product, emp_edit_sell_price, emp_change_cash_disk,
allaw_r_sale, allaw_sale_credit, allaw_sale_delivery, allaw_un_sale,
allaw_save_cash_credit, emp_del_vendor, emp_del_product, username, pass,
use_compu, deleted, cash_advance, emp_show_money, numof_customer`).

Sub-tables (HR/payroll):
- **`Jobs`** (job_id, job_code, job_name_ar/en) — job titles.
- **`Employee_salary`** (`salary_id, emp_id, state, basic_salary, emp_commission,
  emp_over_commission, emp_deduction, emp_absence_money, total, month_salary,
  cash_advance`) — monthly payroll record.
- **`Employee_cash_advance`** (`cash_advance_id, emp_id, cash_advance, type`) —
  salary advances (سلف).
- **`Employee_commission`** / **`Employee_over_commission`** / **`Employee_deduction`**
  / **`Employee_absence_money`** — commission/bonus/deduction/absence components.
- **`Employee_daily_time`** / **`Employee_daily_time_archive`** — weekly work
  schedule (Saturday..Friday, start/end).
- **`Employee_work_time`** — actual clock-in/out archive.
- **`Branches_employee_edit`** — branch-level employee edits (per-branch overrides).

**Screens:** Employees list → Add/Edit (with permissions + salary) → Payroll
(compute monthly salary from basic + commission − deduction − absence + advance)
→ Attendance (daily time). Triggers: `max_disc_per`/`max_disc_money` limit how much
discount a cashier may grant at POS (enforced in sales screen).

---

## 3. SHAREHOLDERS / OWNERS (المساهمون)

- **`company_Owner`** (`coow_id, coow_code, coow_name_ar/en, tel, mobile, address,
  coow_current_money, coow_start_money, active, deleted`) — shareholders with
  current capital balance.
- **`Gedo_Dividends_paied`** (`dividends_id, coow_id, yaer_id, gf_id, paied_money`)
  — dividends paid to each shareholder per year.
- Linked to **`Gedo_Financial`** (the general ledger, see §5) via `gf_id`.

**Screens:** Shareholders list → capital balance → annual dividends (ربح موزع).

---

## 4. PRODUCTS / INVENTORY (الأصناف والمخزون)

Master: **`Products`** (`product_id, product_code, product_fast_code, product_int_code,
product_name_ar/en, product_scientific_name, product_drug, company_id,
product_has_expire, site_id, product_buy_number, product_big_number,
product_small_number, sell_price, product_disc1/2, tax_price, buy_price, deleted,
active, product_unit1/2/3, product_unit1_2, product_unit1_3, group_id, pd_id,
product_print_barcode, product_allow_disc, product_max_disc, product_minus,
product_made, product_sale_unit, unit2_sell_price, unit3_sell_price, …`).
- `Products_online` — online/catalog copy.
- **`Product_groups`** (group_id, group_name_ar/en) — categories.
- **`Product_description`** (pd_id, pd_name_ar/en) — descriptions/forms.
- **`Product_Dose`** (dose_id, dose_name) — drug doses.
- **`Product_units`** (unit_id, unit_name_ar/en) — units of measure.
- **`Companys`** (company_id, co_name_ar/en) — suppliers/manufacturers.
- **`Sites`** (site_id) — locations/sites.
- **`Product_Vendor`** (PV_id, product_id, vendor_id, buy_price, sell_price, disc…)
  — per-vendor pricing.

Stock (batches, FEFO):
- **`Product_Amount`** (`counter_id, product_id, store_id, vendor_id, amount,
  buy_price, sell_price, tax_price, exp_date, pa_id`) — the stock ledger; one row
  per (product × store × vendor × expiry) batch. `exp_date` drives FEFO.
- **`Branches_Product_Amount`** — branch mirror of stock.
- **`Product_amount_Change`** / **`Product_amount_reg_update`** /
  **`Product_amount_update`** — stock adjustment / correction logs (with old/new
  amount + reason `form_type`/`form_notice`). These are the **stock-movement audit
  triggers**.
- **`Start_stock_header`** / **`Start_stock_details`** — opening stock.

**Screens:** Products (list, add/edit, barcode) → Groups → Units → Stock (per
store, FEFO batches, expiry) → Stock adjustments (with reason) → Per-vendor prices.

---

## 5. ACCOUNTING / GENERAL LEDGER (الحسابات)

- **`Account_Tree`** (`account_id, account_code, account_name_ar/en,
  account_major, account_start_money, insert_uid`) — chart of accounts
  (tree/hierarchy via `account_major`).
- **`Gedo_Financial`** (`gf_id, gf_code, gf_gedo_type, gf_value, gf_from_type,
  gf_from_id, gf_to_type, gf_to_id, gf_notes, gf_computer, gf_actual_cashier,
  gf_form_type`) — the **central journal**: every money movement posts here
  (from_type/to_type reference Customer/Vendor/Branch/Employee/Shareholder).
- **`Gedo_Vendors`** / **`Gedo_branches`** / **`Gedo_customers`** / **`Gedo_employee`**
  / **`Gedo_installment`** — sub-ledgers per party (for_him / for_me balances).
- **`Tuning_accounts`** (`Tuning_accounts_id, class, who_class, who_id,
  Tuning_accounts_reason_id, Tuning_accounts_money, notes`) + **`Tuning_accounts_reason`**
  — manual journal adjustments with reason codes (تسويات).
- **`Checks`** (`ch_id, gf_id, Flag, out_in, ch_number, ch_date_created,
  ch_valid_date, ch_status, ch_expenses, name, cashed`) — cheque (شيك) register.
- **`Cash_depots`** (`cash_depot_id, cash_depot_code, cash_depot_name_ar/en,
  cash_depot_class, cash_depot_current_money, account_number, bank_id`) — cash
  boxes / bank accounts with **running balance** `cash_depot_current_money`.
- **`Branches_cash_depots`** — per-branch cash boxes.
- **`Co_bank`** (bank_id, bank_name) — banks.
- **`Cash_disk_close`** (`cdc_id, cdc_cash_id, cdc_emp_id, cdc_shift_start_time,
  cdc_start_cash, cdc_curr_cash, cdc_act_cash, cdc_to_emp_id, cdc_fcs_id,
  cdc_trans_value, cdc_notice`) — cashier shift open/close reconciliation.
  `Branches_Cash_disk_close` = branch version.
- **`Run_Backup`** — scheduled DB backup jobs.

**Screens:** Chart of Accounts → Journal (Gedo_Financial) → Sub-ledgers
(Customer/Vendor/Branch/Employee/Shareholder) → Manual adjustments (Tuning) →
Cheques → Cash depots (balance) → Shift open/close (Cash_disk_close).

---

## 6. SALES / POS (المبيعات ونقطة البيع)

- **`Sales_header`** (`sales_id, store_id, customer_id, class, product_number,
  bill_money_befor, total_bill, total_after_disc, total_bill_net, total_disc_per,
  total_disc_money, total_product_disc, customer_disc_per, bill_cash, cashier_id,
  notes, bill_other_expenses, gf_id, contract_id, major_customer_part, bill_number,
  back, bill_date, compu_name, cashier_disk_id, cust_name, sale_class,
  network_id, network_money, money_change, delivery_man_id`) — the invoice header.
- **`Sales_details`** (`details_id, sales_id, product_id, counter_id, exp_date,
  amount, sale_unit_change, sale_unit, sell_price, buy_price, disc_money, disc_per,
  total_sell, back, back_amount, back_unit_change, back_price, back_unit,
  back_gf_id, sales_details_id`) — invoice lines; `exp_date` = FEFO batch picked.
- **`Sales_header_Temp`** / **`Sales_details_Temp`** — cart buffer (ignore in mirror).
- **`Back_sales_header`** / **`Back_sales_details`** — **returns** (مرتجع), linked
  by `back_sales_id`→`sales_id`, `back='Y'` on header marks a return bill.
- **`Sales_delivery_header`** / **`Sales_delivery_details`** / **`Sales_delivery_del_*`**
  — delivery (توصيل) orders.
- **`Sale_classes`** (sale_class_id, sale_class_name) — sale types (retail/wholesale).
- **`Customer_contracts`** (contract_id, customer_id, max_bill_money, bill_disc,
  customer_pay_rate, product_disc…) — customer pricing contracts.
- **`Customer`** (`customer_id, customer_code, customer_name_ar/en, job_id, mobile,
  tel, address, customer_class_id, customer_major, active, customer_max_money,
  customer_current_money, customer_start_money, customer_pay_type, contract_id,
  customer_disc_local/import, customer_insurance_code, deleted`) — customers with
  **credit balance** `customer_current_money`.

**Screens:** POS (cart, FEFO pick, discount w/ `max_disc` enforcement, customer
select → credit) → Invoices list → Returns → Delivery → Sale classes. The
`cashier_id`/`cashier_disk_id` tie every sale to the cashier + shift (for
Cash_disk_close reconciliation).

---

## 7. PURCHASES / SUPPLIERS (المشتريات والموردون)

- **`Vendor`** (`vendor_id, vendor_code, vendor_name_ar/en, tel, mobile, address,
  company_code, vendor_max_money, vendor_current_money, vendor_start_money,
  active, deleted, ven_notes, ven_return`) — suppliers with **debt balance**
  `vendor_current_money`.
- **`Purchase_header`** (`purchase_id, store_id, vendor_id, order_id, class,
  product_number, total_bill, bill_disc_per, bill_disc_money, bill_other_expenses,
  cashier_id, bill_number, bill_date, back, total_back, total_after_back, notes,
  gf_id, back_number, customer_id, bill_tax`) — GRN header.
- **`Purchase_details`** (`details_id, purchase_id, product_id, counter_id,
  exp_date, amount, bouns, sell_price, buy_price, gain_price, tax_price, back,
  back_amount, back_price, back_bouns, back_tax_price`) — GRN lines.
- **`Back_purchase_header`** / **`Back_purchase_details`** — purchase returns.
- **`Order_header`** / **`Order_details`** — purchase orders.
- **`Temp_Purchase_*`** — draft purchases (ignore in mirror).
- **`Product_Vendor`** — per-vendor catalog/pricing.

**Screens:** Vendors → Purchase Orders → Receive (GRN) → Purchase Returns →
Per-vendor balance (`vendor_current_money`).

---

## 8. BRANCHES / INTER-BRANCH (الفروع ونقل الفروع)

- **`Branches`** (`branch_id, branch_code, branch_name, branch_address, branch_tel,
  branch_mobile, active, branch_ip1/ip2, is_server, master_branch_id, rep_*`) —
  the branch registry; `is_server` = main, `master_branch_id` = parent.
- **`Stores`** (`store_id, store_code, store_name_ar/en, active`) — physical stores
  within a branch (every doc has `store_id`).
- **`Branches_*`** tables = the **branch-side replicas** of every document type
  (sales, purchases, products, customers, vendors, cash, employee) prefixed
  `Branches_` and tagged `branch_id`. These are how a branch mirrors the main
  server's data (and vice-versa) — this is eStock's own sync mechanism.
- **Inter-branch transfers:**
  - **`Branch_order_header`** / **`Branch_order_details`** — branch requisition.
  - **`Branch_money_order`** / **`Branch_money_convert`** — inter-branch money moves.
  - **`Branches_convert_header`** / **`Branches_convert_details`** — branch stock
    convert (transfer).
  - **`Store_convert_header`** / **`Store_convert_details`** — intra-branch store
    transfer.
  - **`Branches_Product_amount_Change`** — branch stock adjustments.
- **`Branches_Cash_disk_close`** — branch shift close.

**Main vs Branch logic:** `store_id=1` is typically the MAIN store; `store_id=2`
is the branch store. `Branches_sales_header` carries `branch_id` for the receiving
branch. ProCare mirrors this as branch entities (MASHALA/ELSANTA) — keep the
`store_branch_map` (elsanta: {1→ELSANTA, 2→ELSANTA}; mashala: {1→MASHALA}).

**Screens:** Branches → Stores → Branch orders → Inter-branch transfers (stock &
money) → Branch reconciliation.

---

## 9. ALARMS / TRIGGERS / ALERTS (التنبيهات والإنذارات)

eStock has NO single "alarms" table — alerts are **derived triggers** over data:
- **Expiry alarm:** `Product_Amount.exp_date` within N days of today → near-expiry
  stock (the ProCare `/alerts/expiry` endpoint). `product_has_expire` gates it.
- **Low stock alarm:** `Product_Amount.amount` < product's min (or `amount_zero`
  flag) → reorder. (`product_minus` = allow negative.)
- **Price-change log (audit trigger):** **`Product_Changes`** /
  **`Product_online_Changes`** (`product_id, class, sell_price_old→new,
  buy_price_old→new, …`) — every price edit is logged (audit/trigger).
- **Stock-change log:** **`Product_amount_Change`** (old_amount→new_amount + reason)
  — stock edits logged.
- **`News_bar`** (`news_id, news, company_id, deleted`) — broadcast messages on the
  status bar (internal alerts/announcements).
- **`Checks`** with `ch_valid_date` + `ch_status` — cheque due-date alarms.
- **`DB_online_update_Error`** — replication/sync error log (trigger on failed
  online update).
- **`Flag`** (f_id, f_code, f_name) — generic status flags.
- **`installment`** / **`installment_state`** — customer installment schedules;
  `pay_month`/`state` drive due alarms.
- **`customer_contracts`** + **`Customer.customer_insurance_code`** — insurance
  contract alerts.

**ProCare mapping:** build `/alerts/expiry`, `/alerts/low-stock`, `/alerts/reorder`,
and add `/alerts/below-cost` (sell_price < buy_price, see QA report) — all derived
from the mirrored tables above. Do NOT expect a literal "alarms" table.

---

## 10. CUSTOMERS (العملاء)

Master **`Customer`** (see §6) with credit `customer_current_money`, class
**`Customer_Class`**, area **`Customer_Area`**, contracts **`customer_contracts`**,
insurance code. Sub-ledger **`Gedo_customers`**. Installments **`installment`**.

**Screens:** Customers list → Add/Edit → Credit limit/balance → Contracts →
Installments → Area report.

---

## 11. REPORTS (التقارير)

Backed by the transactional tables above; key ones:
- Daily/Monthly sales (group `Sales_header` by `bill_date`, `store_id`, `cashier_id`).
- Stock valuation (`Product_Amount.amount × buy_price/sell_price`, FEFO).
- Customer/Vendor statements (`customer_current_money` / `vendor_current_money`
  + `Gedo_*` sub-ledgers).
- Cashier shift report (`Cash_disk_close` + `Sales_header.cashier_disk_id`).
- Expiry / low-stock (§9).
- Profit (`Sales_details.total_sell − buy_price×amount`).
- `News_bar` feeds the on-screen ticker.

---

## 12. MIRROR MAPPING (eStock → ProCare) — already in `etl.MIRROR_PLAN`

| eStock table | ProCare table | Notes |
|---|---|---|
| Products | products | unit_big/unit_small → String (use `_str()`) |
| Customer | customers | credit balance = `customer_current_money` |
| Vendor | vendors | debt = `vendor_current_money` |
| Product_Amount | stock_batches | FEFO by `exp_date` |
| Sales_header + Sales_details + Back_* | sales + sale_lines | `back='Y'`→is_return, `sale_date=COALESCE(bill_date,insert_date)` |
| Branches_sales_header | sales (branch) | tag branch |
| Purchase_header + Purchase_details + Back_purchase_* | purchases + purchase_lines | |
| Cash_depots | ledger_entries (treasury) | balance = `cash_depot_current_money` |
| Employee | employees | + permissions from EMP_CONTROL |
| Account_Tree + Gedo_Financial + Tuning_accounts | accounts / journal | accounting |
| company_Owner + Gedo_Dividends_paied | shareholders | |

---

## 13. WHAT TO BUILD IN PROCARE-OS (hand-off to Claude Code)

Mirror ALL the above from eStock read-only, preserving:
1. **Main vs branch** distinction (`store_id`/`branch_id` → ProCare branches).
2. **Balances** (`*_current_money`, `cash_depot_current_money`) — these are the
   authoritative running totals; the dashboard "balance" cards must use them.
3. **FEFO** stock picks (`exp_date`).
4. **Returns** (`back='Y'` / `Back_*` tables) as negative/credit notes.
5. **Employee permissions** (`EMP_CONTROL` matrix) → ProCare role flags.
6. **Alarms** derived from expiry/low-stock/price-change/cheque-due (§9), not a
   literal table.
7. **Soft deletes** (`deleted`/`active`) preserved.
8. **Audit logs** (`Product_Changes`, `Product_amount_Change`, `user_login`) surfaced
   as change history.

The mirror must be **chunked + retry-on-WAN-drop** (elsanta WAN throws `10054` on
big pulls — see the ETL task doc). Do NOT write to eStock — SELECT only.
