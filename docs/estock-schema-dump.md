# eStock schema dump + ProCare coverage

- **Total tables:** 114
- **Mirrored into ProCare models (dedicated loaders):** 28
- **Mirrored verbatim into `estock_raw_mirror`:** 86
- **Not mirrored:** 0
- **Coverage:** 100.0%

Legend: ✅ dedicated ProCare model · 📦 verbatim row in `estock_raw_mirror`.

## Verbatim-only tables (held in full, not yet modelled)

Mirrored row-for-row, queried as JSON. Promote one to a dedicated loader
when the domain needs it — the rows are already local, so that no longer
costs another trip to the pharmacy server.

- `Back_purchase_details` (11 cols, PK: details_id, back_purchase_id) — 807 rows
- `Back_purchase_header` (11 cols, PK: back_purchase_id) — 169 rows
- `Branch_money_convert` (11 cols, PK: branch_money_id, from_branch_id) — 1,128 rows
- `Branch_money_order` (12 cols, PK: bill_id, from_branch_id) — 1,128 rows
- `Branches` (52 cols, PK: branch_id) — 2 rows
- `Branches_Product_amount_Change` (18 cols, PK: branch_id, id) — 1,052,383 rows
- `Branches_Vendor` (18 cols, PK: branch_id, vendor_id) — 0 rows
- `Branches_back_purchase_details` (14 cols, PK: branch_id, details_id, back_purchase_id) — 819 rows
- `Branches_back_purchase_header` (12 cols, PK: branch_id, back_purchase_id) — 336 rows
- `Branches_cash_depots` (13 cols, PK: branch_id, cash_depot_id) — 15 rows
- `Branches_company_edit` (13 cols, PK: company_edit_id) — 16 rows
- `Branches_convert_details` (16 cols, PK: details_id, from_branch_id, branch_convert_id) — 62,181 rows
- `Branches_convert_header` (12 cols, PK: branch_convert_id, from_branch_id) — 8,306 rows
- `Branches_customer` (29 cols, PK: branch_id, customer_id) — 0 rows
- `Branches_description_edit` (9 cols, PK: pd_edit_id) — 0 rows
- `Branches_employee_edit` (56 cols, PK: emp_edit_id) — 79 rows
- `Branches_group_edit` (9 cols, PK: group_edit_id) — 10 rows
- `Branches_mail` (10 cols, PK: mail_id) — 241 rows
- `Branches_products_edit` (53 cols, PK: product_edit_id) — 31,570 rows
- `Branches_shortcoming` (13 cols, PK: branch_id, product_id, store_id) — 21,005 rows
- `Branches_stores` (10 cols, PK: branch_id, store_id) — 3 rows
- `Branches_unit_edit` (9 cols, PK: unit_edit_id) — 1 rows
- `Checks` (17 cols, PK: ch_id) — 0 rows
- `Co_bank` (10 cols, PK: bank_id) — 2 rows
- `Companys` (11 cols, PK: company_id) — 1,210 rows
- `Customer_Area` (9 cols, PK: no declared key) — 9 rows
- `Customer_Class` (5 cols, PK: customer_class_id) — 2 rows
- `DB_online_update_Error` (7 cols, PK: error_id) — 8 rows
- `EMP_CONTROL` (198 cols, PK: emp_id) — 46 rows
- `Employee_absence_money` (6 cols, PK: no declared key) — 2 rows
- `Employee_commission` (6 cols, PK: no declared key) — 0 rows
- `Employee_daily_time` (13 cols, PK: no declared key) — 92 rows
- `Employee_deduction` (6 cols, PK: no declared key) — 19 rows
- `Employee_over_commission` (6 cols, PK: no declared key) — 33 rows
- `Employee_work_time` (11 cols, PK: id) — 2,138 rows
- `Flag` (3 cols, PK: no declared key) — 55 rows
- `Gedo_Vendors` (11 cols, PK: gv_id) — 20,784 rows
- `Gedo_branches` (10 cols, PK: gb_id) — 8,855 rows
- `Gedo_customers` (11 cols, PK: gc_id) — 118,493 rows
- `Gedo_employee` (10 cols, PK: no declared key) — 635 rows
- `Gedo_installment` (10 cols, PK: no declared key) — 0 rows
- `Jobs` (8 cols, PK: job_id) — 8 rows
- `News_bar` (9 cols, PK: no declared key) — 0 rows
- `Order_details` (11 cols, PK: details_id, order_id) — 590 rows
- `Order_header` (8 cols, PK: order_id) — 7 rows
- `Product_Changes` (15 cols, PK: product_change_id) — 36,190 rows
- `Product_Dose` (7 cols, PK: dose_id) — 69 rows
- `Product_Vendor` (12 cols, PK: PV_id, product_id, vendor_id) — 42,563 rows
- `Product_amount_Change` (16 cols, PK: no declared key) — 533,275 rows
- `Product_amount_reg_update` (18 cols, PK: id) — 46,982 rows
- `Product_amount_update` (17 cols, PK: id) — 4,154 rows
- `Product_description` (7 cols, PK: pd_id) — 250 rows
- `Product_groups` (7 cols, PK: group_id) — 437 rows
- `Product_online_Changes` (15 cols, PK: no declared key) — 0 rows
- `Product_price_change` (12 cols, PK: price_change_id) — 90 rows
- `Product_units` (7 cols, PK: unit_id) — 26 rows
- `Products_online` (47 cols, PK: no declared key) — 0 rows
- `Run_Backup` (7 cols, PK: job_id) — 5 rows
- `Sale_classes` (5 cols, PK: no declared key) — 2 rows
- `Sales_delivery_del_details` (16 cols, PK: details_id, sales_delivery_id) — 49 rows
- `Sales_delivery_del_header` (31 cols, PK: sales_delivery_id) — 15 rows
- `Sales_delivery_details` (20 cols, PK: details_id, sales_delivery_id) — 0 rows
- `Sales_delivery_header` (31 cols, PK: sales_delivery_id) — 0 rows
- `Sales_details_Temp` (23 cols, PK: no declared key) — 0 rows
- `Sales_header_Temp` (33 cols, PK: no declared key) — 0 rows
- `Shortcoming` (12 cols, PK: id) — 9,403 rows
- `Sites` (8 cols, PK: site_id) — 221 rows
- `Start_stock_details` (16 cols, PK: details_id, sstock_id) — 4 rows
- `Start_stock_header` (10 cols, PK: sstock_id) — 3 rows
- `Store_convert_details` (11 cols, PK: details_id, store_convert_id) — 0 rows
- `Store_convert_header` (9 cols, PK: store_convert_id) — 0 rows
- `Stores` (8 cols, PK: store_id) — 2 rows
- `Temp_Purchase_details` (12 cols, PK: details_id, temp_purchase_id) — 39 rows
- `Temp_Purchase_header` (15 cols, PK: temp_purchase_id) — 2 rows
- `Tuning_accounts_reason` (8 cols, PK: Tuning_accounts_reason_id) — 6 rows
- `barcode_temp` (42 cols, PK: no declared key) — 2 rows
- `co_inf` (42 cols, PK: no declared key) — 1 rows
- `customer_contracts` (18 cols, PK: contract_id) — 0 rows
- `dtproperties` (7 cols, PK: id, property) — 0 rows
- `installment` (20 cols, PK: no declared key) — 0 rows
- `installment_state` (10 cols, PK: no declared key) — 0 rows
- `sysdiagrams` (5 cols, PK: diagram_id) — 0 rows
- `user_login` (5 cols, PK: lu_id) — 7,434 rows
- `versions` (4 cols, PK: no declared key) — 18 rows
- `zz_fix_backup_20260730` (5 cols, PK: no declared key) — 4 rows
- `zz_quarantine_purchase_details` (25 cols, PK: no declared key) — 553 rows

## All tables

### ✅ `Account_Tree` · 119 rows

_PK: account_id_

- `account_id` DECIMAL(18, 0) NOT NULL
- `account_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `account_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `account_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `account_major` DECIMAL(18, 0) NULL
- `account_start_money` MONEY NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### ✅ `Back_Sales_details` · 8,877 rows

_PK: no declared key_

- `back_sales_id` DECIMAL(18, 0) NOT NULL
- `sales_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `exp_date` DATETIME NULL
- `sell_price` MONEY NOT NULL
- `buy_price` MONEY NULL
- `back_amount` FLOAT NULL
- `back_unit_change` DECIMAL(18, 0) NULL
- `back_price` MONEY NULL
- `back_unit` INTEGER NULL
- `back_gf_id` DECIMAL(18, 0) NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL
- `disc_per` FLOAT NULL
- `disc_money` MONEY NULL
- `details_id` DECIMAL(18, 0) NULL
- `back_sales_details_id` DECIMAL(18, 0) NOT NULL

### 📦 `Back_purchase_details` · 807 rows

_PK: details_id, back_purchase_id_

- `details_id` DECIMAL(18, 0) NOT NULL
- `back_purchase_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `amount` FLOAT NULL
- `exp_date` DATETIME NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `tax_price` MONEY NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Back_purchase_header` · 169 rows

_PK: back_purchase_id_

- `back_purchase_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `total` MONEY NULL
- `class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `bill_number` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `gf_id` DECIMAL(18, 0) NULL
- `product_number` INTEGER NULL
- `notes` TEXT(16) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### ✅ `Back_sales_header` · 6,989 rows

_PK: no declared key_

- `back_sales_id` DECIMAL(18, 0) NOT NULL
- `sales_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `customer_id` DECIMAL(18, 0) NULL
- `class` INTEGER NULL
- `r_money_befor` MONEY NULL
- `s_money_befor` MONEY NULL
- `r_total_bill` MONEY NULL
- `s_total_bill` MONEY NULL
- `total_bill_net` MONEY NULL
- `total_disc_per` FLOAT NULL
- `bill_cash` MONEY NULL
- `cashier_id` DECIMAL(18, 0) NULL
- `notes` VARCHAR(200) COLLATE "Arabic_CI_AS" NULL
- `gf_id` DECIMAL(18, 0) NULL
- `contract_id` DECIMAL(18, 0) NULL
- `major_customer_part` MONEY NULL
- `compu_name` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `cashier_disk_id` DECIMAL(18, 0) NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL
- `update_uid` DECIMAL(18, 0) NULL
- `update_date` DATETIME NULL
- `network_id` DECIMAL(18, 0) NULL
- `network_money` MONEY NULL
- `money_change` MONEY NULL
- `delivery_man_id` DECIMAL(18, 0) NULL
- `cashier_money` MONEY NULL

### 📦 `Branch_money_convert` · 1,128 rows

_PK: branch_money_id, from_branch_id_

- `branch_money_id` DECIMAL(18, 0) NOT NULL
- `from_branch_id` DECIMAL(18, 0) NOT NULL
- `from_cash_id` DECIMAL(18, 0) NOT NULL
- `to_branch_id` DECIMAL(18, 0) NULL
- `to_cash_id` DECIMAL(18, 0) NULL
- `class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `amount` MONEY NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `is_open` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Branch_money_order` · 1,128 rows

_PK: bill_id, from_branch_id_

- `branch_money_id` DECIMAL(18, 0) NOT NULL
- `bill_id` DECIMAL(18, 0) NOT NULL
- `from_branch_id` DECIMAL(18, 0) NOT NULL
- `from_cash_id` DECIMAL(18, 0) NOT NULL
- `to_branch_id` DECIMAL(18, 0) NULL
- `to_cash_id` DECIMAL(18, 0) NULL
- `class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `amount` MONEY NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `is_open` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### ✅ `Branch_order_details` · 62,181 rows

_PK: details_id, from_branch_id, branch_order_id_

- `details_id` DECIMAL(18, 0) NOT NULL
- `from_branch_id` DECIMAL(18, 0) NOT NULL
- `branch_order_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NULL
- `counter_id` DECIMAL(18, 0) NULL
- `amount` FLOAT NULL
- `exp_date` DATETIME NULL
- `unit_id` DECIMAL(18, 0) NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL
- `tax_price` MONEY NULL
- `is_open` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `unit_change` FLOAT NULL

### ✅ `Branch_order_header` · 8,306 rows

_PK: bill_id, from_branch_id_

- `branch_order_id` DECIMAL(18, 0) NOT NULL
- `bill_id` DECIMAL(18, 0) NOT NULL
- `from_branch_id` DECIMAL(18, 0) NOT NULL
- `from_store_id` DECIMAL(18, 0) NOT NULL
- `to_branch_id` DECIMAL(18, 0) NULL
- `to_store_id` DECIMAL(18, 0) NULL
- `class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `total_sell_price` MONEY NULL
- `total_buy_price` MONEY NULL
- `product_number` INTEGER NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `is_open` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Branches` · 2 rows

_PK: branch_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `branch_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `branch_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `branch_address` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `branch_tel` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `branch_mobile` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `branch_ip1` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `branch_ip2` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `rep_last_sales_id` DECIMAL(18, 0) NULL
- `rep_sales_date` DATETIME NULL
- `rep_last_purchase_id` DECIMAL(18, 0) NULL
- `rep_purchase_date` DATETIME NULL
- `rep_last_shortcoming_id` DECIMAL(18, 0) NULL
- `rep_shortcoming_date` DATETIME NULL
- `rep_last_product_id` DECIMAL(18, 0) NULL
- `rep_last_product_date` DATETIME NULL
- `rep_last_cash_disk_id` DECIMAL(18, 0) NULL
- `rep_cash_disk_date` DATETIME NULL
- `rep_back_purchase_id` DECIMAL(18, 0) NULL
- `rep_back_purchase_date` DATETIME NULL
- `rep_store_id` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `update_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `rep_last_unit_id` DECIMAL(18, 0) NULL
- `rep_last_group_id` DECIMAL(18, 0) NULL
- `rep_last_pd_id` DECIMAL(18, 0) NULL
- `rep_last_company_id` DECIMAL(18, 0) NULL
- `rep_last_unit_date` DATETIME NULL
- `rep_last_group_date` DATETIME NULL
- `rep_last_pd_date` DATETIME NULL
- `rep_last_company_date` DATETIME NULL
- `rep_last_pa_id` DECIMAL(18, 0) NULL
- `rep_last_pa_date` DATETIME NULL
- `rep_last_customer_id` DECIMAL(18, 0) NULL
- `rep_customer_date` DATETIME NULL
- `rep_last_vendor_id` DECIMAL(18, 0) NULL
- `rep_vendor_date` DATETIME NULL
- `rep_last_cash_disk_close_id` DECIMAL(18, 0) NULL
- `rep_cash_disk_close_date` DATETIME NULL
- `is_server` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `barcode_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `barcode_tel` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `rep_last_master_pa_id` DECIMAL(18, 0) NULL
- `rep_last_master_pa_date` DATETIME NULL
- `rep_last_emp_id` DECIMAL(18, 0) NULL
- `rep_last_master_pa_ch_id` DECIMAL(18, 0) NULL
- `rep_last_pa_ch_id` DECIMAL(18, 0) NULL
- `rep_last_sales_details_id` DECIMAL(18, 0) NULL
- `rep_last_emp_date` DATETIME NULL

### ✅ `Branches_Cash_disk_close` · 7,145 rows

_PK: branch_id, cdc_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `cdc_id` DECIMAL(18, 0) NOT NULL
- `cdc_cash_id` DECIMAL(18, 0) NULL
- `cdc_emp_id` DECIMAL(18, 0) NULL
- `cdc_shift_start_time` DATETIME NULL
- `cdc_start_cash` MONEY NULL
- `cdc_curr_cash` MONEY NULL
- `cdc_act_cash` MONEY NULL
- `cdc_to_emp_id` DECIMAL(18, 0) NULL
- `cdc_fcs_id` DECIMAL(18, 0) NULL
- `cdc_trans_value` MONEY NULL
- `cdc_notice` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### ✅ `Branches_Product_Amount` · 123,310 rows

_PK: branch_id, counter_id, product_id, store_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NOT NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `amount` FLOAT NULL
- `buy_price` MONEY NULL
- `sell_price` MONEY NULL
- `tax_price` MONEY NULL
- `exp_date` DATETIME NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `pa_id` DECIMAL(18, 0) NOT NULL
- `branch_pa_id` DECIMAL(18, 0) NOT NULL

### 📦 `Branches_Product_amount_Change` · 1,052,383 rows

_PK: branch_id, id_

- `ch_id` DECIMAL(18, 0) NOT NULL
- `branch_id` DECIMAL(18, 0) NOT NULL
- `id` DECIMAL(18, 0) NOT NULL
- `in_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `counter_id` DECIMAL(18, 0) NULL
- `product_id` DECIMAL(18, 0) NULL
- `store_id` DECIMAL(18, 0) NULL
- `amount` FLOAT NULL
- `exp_date` DATETIME NULL
- `form_type` INTEGER NULL
- `form_notice` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `tax_price` MONEY NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `stock` FLOAT NULL

### 📦 `Branches_Vendor` · 0 rows

_PK: branch_id, vendor_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `vendor_id` DECIMAL(18, 0) NOT NULL
- `vendor_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `vendor_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `vendor_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `tel` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `mobile` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `address` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `company_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `vendor_max_money` MONEY NULL
- `vendor_current_money` MONEY NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `vendor_start_money` MONEY NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 📦 `Branches_back_purchase_details` · 819 rows

_PK: branch_id, details_id, back_purchase_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `details_id` DECIMAL(18, 0) NOT NULL
- `back_purchase_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `amount` FLOAT NULL
- `exp_date` DATETIME NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `tax_price` MONEY NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL
- `unit_id` DECIMAL(18, 0) NULL
- `unit_ch` DECIMAL(18, 0) NULL

### 📦 `Branches_back_purchase_header` · 336 rows

_PK: branch_id, back_purchase_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `back_purchase_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `total` MONEY NULL
- `class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `bill_number` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `gf_id` DECIMAL(18, 0) NULL
- `product_number` INTEGER NULL
- `notes` TEXT(16) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL

### 📦 `Branches_cash_depots` · 15 rows

_PK: branch_id, cash_depot_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `cash_depot_id` DECIMAL(18, 0) NOT NULL
- `cash_depot_code` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `cash_depot_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `cash_depot_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `cash_depot_class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `cash_depot_current_money` MONEY NULL
- `account_number` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `bank_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 📦 `Branches_company_edit` · 16 rows

_PK: company_edit_id_

- `company_edit_id` DECIMAL(18, 0) NOT NULL
- `insert_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `company_id` DECIMAL(18, 0) NULL
- `company_code` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `co_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `mobile` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `tel` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `address` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 📦 `Branches_convert_details` · 62,181 rows

_PK: details_id, from_branch_id, branch_convert_id_

- `details_id` DECIMAL(18, 0) NOT NULL
- `from_branch_id` DECIMAL(18, 0) NOT NULL
- `branch_convert_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NULL
- `counter_id` DECIMAL(18, 0) NULL
- `amount` FLOAT NULL
- `exp_date` DATETIME NULL
- `unit_id` DECIMAL(18, 0) NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `insert_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `tax_price` MONEY NULL
- `is_open` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `unit_change` FLOAT NULL

### 📦 `Branches_convert_header` · 8,306 rows

_PK: branch_convert_id, from_branch_id_

- `branch_convert_id` DECIMAL(18, 0) NOT NULL
- `from_branch_id` DECIMAL(18, 0) NOT NULL
- `to_branch_id` DECIMAL(18, 0) NULL
- `from_store_id` DECIMAL(18, 0) NOT NULL
- `to_store_id` DECIMAL(18, 0) NULL
- `total_sell_price` MONEY NULL
- `total_buy_price` MONEY NULL
- `product_number` INTEGER NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `is_open` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Branches_customer` · 0 rows

_PK: branch_id, customer_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `customer_id` DECIMAL(18, 0) NOT NULL
- `customer_code` VARCHAR(25) COLLATE "Arabic_CI_AS" NULL
- `customer_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `customer_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `job_id` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `mobile` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `tel` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `address` VARCHAR(250) COLLATE "Arabic_CI_AS" NULL
- `customer_class_id` DECIMAL(18, 0) NULL
- `customer_major` DECIMAL(18, 0) NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `start_work_date` DATETIME NULL
- `customer_max_money` MONEY NULL
- `customer_current_money` MONEY NULL
- `customer_rate_pay` FLOAT NULL
- `customer_house_no` VARCHAR(25) COLLATE "Arabic_CI_AS" NULL
- `customer_pay_type` INTEGER NULL
- `customer_start_money` MONEY NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `contract_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `area_id` DECIMAL(18, 0) NULL
- `sales_man` DECIMAL(18, 0) NULL
- `sale_class_id` DECIMAL(18, 0) NULL
- `sell_price_buy` CHAR(1) COLLATE "Arabic_CI_AS" NULL

### 📦 `Branches_description_edit` · 0 rows

_PK: pd_edit_id_

- `pd_edit_id` DECIMAL(18, 0) NOT NULL
- `insert_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `pd_id` DECIMAL(18, 0) NULL
- `pd_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `pd_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `pd_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 📦 `Branches_employee_edit` · 79 rows

_PK: emp_edit_id_

- `emp_edit_id` DECIMAL(18, 0) NOT NULL
- `insert_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_id` DECIMAL(18, 0) NOT NULL
- `emp_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `emp_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `emp_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `emp_gender` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `job_id` DECIMAL(18, 0) NULL
- `birth_date` SMALLDATETIME NULL
- `hire_date` SMALLDATETIME NULL
- `work_date` SMALLDATETIME NULL
- `mobile` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `home_tel` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `address` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `card_id` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `card_date` DATETIME NULL
- `card_place` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `max_disc_per` DECIMAL(19, 4) NULL
- `max_disc_money` MONEY NULL
- `show_buy` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `show_cash_disk_history` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `show_total_sales_report` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `use_compu` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `username` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `pass` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `salary_typ` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `basic_salary` MONEY NULL
- `more_salary` MONEY NULL
- `emp_cust_max_money` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_add_product` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_edit_product` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_r_sale_date` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_r_sale_bill_num` INTEGER NULL
- `emp_add_cust` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_edit_cust` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_del_cust` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_commission1` FLOAT NULL
- `emp_commission2` FLOAT NULL
- `emp_edit_sell_price` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `absence_money` MONEY NULL
- `allaw_r_sale` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_show_money` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_change_cash_disk` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `numof_customer` INTEGER NULL
- `allaw_sale_credit` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `allaw_un_sale` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `allaw_sale_delivery` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `allaw_save_cash_credit` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_del_vendor` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_del_product` CHAR(1) COLLATE "Arabic_CI_AS" NULL

### 📦 `Branches_group_edit` · 10 rows

_PK: group_edit_id_

- `group_edit_id` DECIMAL(18, 0) NOT NULL
- `insert_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `group_id` DECIMAL(18, 0) NULL
- `group_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `group_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `group_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 📦 `Branches_mail` · 241 rows

_PK: mail_id_

- `mail_id` DECIMAL(18, 0) NOT NULL
- `mail_address` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `mail_notes` TEXT(16) COLLATE "Arabic_CI_AS" NULL
- `is_read` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `update_date` DATETIME NULL
- `update_uid` DECIMAL(18, 0) NULL
- `from_branch` DECIMAL(18, 0) NULL
- `to_branch` DECIMAL(18, 0) NOT NULL

### 📦 `Branches_products_edit` · 31,570 rows

_PK: product_edit_id_

- `product_edit_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `insert_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `product_fast_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `product_int_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `product_name_ar` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `product_name_en` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `product_scientific_name` NVARCHAR(200) COLLATE "Arabic_CI_AS" NULL
- `product_drug` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `company_id` DECIMAL(18, 0) NULL
- `product_has_expire` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `site_id` DECIMAL(18, 0) NULL
- `product_buy_number` DECIMAL(18, 0) NULL
- `product_big_number` DECIMAL(18, 0) NULL
- `product_small_number` DECIMAL(18, 0) NULL
- `sell_price` MONEY NULL
- `product_disc1` DECIMAL(10, 0) NULL
- `product_disc2` DECIMAL(18, 0) NULL
- `tax_price` MONEY NULL
- `buy_price` MONEY NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_unit1` DECIMAL(18, 0) NULL
- `product_unit2` DECIMAL(18, 0) NULL
- `product_unit3` DECIMAL(18, 0) NULL
- `product_unit1_2` DECIMAL(18, 0) NULL
- `product_unit1_3` DECIMAL(18, 0) NULL
- `product_sale_unit` DECIMAL(18, 0) NULL
- `group_id` DECIMAL(18, 0) NULL
- `pd_id` DECIMAL(18, 0) NULL
- `product_print_barcode` INTEGER NOT NULL
- `product_allow_disc` INTEGER NULL
- `product_max_disc` FLOAT NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `up_date` DATETIME NULL
- `up_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(300) COLLATE "Arabic_CI_AS" NULL
- `product_minus` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_made` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code1` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_int_code2` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_int_code3` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_int_code4` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_unit1_sale` DECIMAL(18, 0) NULL
- `unit2_sell_price` MONEY NULL
- `unit3_sell_price` MONEY NULL
- `sell_clause` MONEY NULL
- `unit2_sell_price_clause` MONEY NULL
- `unit3_sell_price_clause` MONEY NULL
- `amount_zero` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `no_print_name` CHAR(1) COLLATE "Arabic_CI_AS" NULL

### ✅ `Branches_purchase_details` · 267,852 rows

_PK: branch_id, details_id, purchase_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `details_id` DECIMAL(18, 0) NOT NULL
- `purchase_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `exp_date` DATETIME NULL
- `amount` FLOAT NULL
- `bouns` FLOAT NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `gain_price` MONEY NULL
- `tax_price` MONEY NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `back_amount` FLOAT NULL
- `back_price` MONEY NULL
- `back_bouns` FLOAT NULL
- `back_tax_price` MONEY NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `co_tax_price` MONEY NULL

### ✅ `Branches_purchase_header` · 25,315 rows

_PK: branch_id, purchase_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `purchase_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `order_id` DECIMAL(18, 0) NULL
- `class` VARCHAR(2) COLLATE "Arabic_CI_AS" NULL
- `product_number` INTEGER NULL
- `total_bill` MONEY NULL
- `bill_disc_per` FLOAT NULL
- `bill_disc_money` MONEY NULL
- `bill_other_expenses` MONEY NULL
- `cashier_id` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `bill_number` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `bill_date` DATETIME NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `total_back` MONEY NULL
- `total_after_back` MONEY NULL
- `notes` TEXT(16) COLLATE "Arabic_CI_AS" NULL
- `gf_id` DECIMAL(18, 0) NULL
- `back_number` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `sell_back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `man_back_details` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `customer_id` DECIMAL(18, 0) NULL
- `bill_tax` MONEY NULL

### ✅ `Branches_sales_details` · 505,189 rows

_PK: branch_id, details_id, sales_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `details_id` DECIMAL(18, 0) NOT NULL
- `sales_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `exp_date` DATETIME NULL
- `amount` FLOAT NOT NULL
- `sale_unit_change` DECIMAL(18, 0) NULL
- `sale_unit` INTEGER NULL
- `sell_price` MONEY NOT NULL
- `buy_price` MONEY NULL
- `disc_money` MONEY NULL
- `disc_per` DECIMAL(18, 3) NULL
- `total_sell` MONEY NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `back_amount` FLOAT NULL
- `back_unit_change` DECIMAL(18, 0) NULL
- `back_price` MONEY NULL
- `back_unit` INTEGER NULL
- `back_gf_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `sales_details_id` DECIMAL(18, 0) NULL

### ✅ `Branches_sales_header` · 257,542 rows

_PK: branch_id, sales_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `sales_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `customer_id` DECIMAL(18, 0) NULL
- `class` INTEGER NULL
- `product_number` INTEGER NULL
- `bill_money_befor` MONEY NULL
- `total_bill` MONEY NULL
- `total_after_disc` MONEY NULL
- `total_bill_net` MONEY NULL
- `total_disc_per` DECIMAL(18, 0) NULL
- `total_disc_money` MONEY NULL
- `total_product_disc` MONEY NULL
- `customer_disc_per` DECIMAL(18, 0) NULL
- `bill_cash` MONEY NULL
- `cashier_id` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(200) COLLATE "Arabic_CI_AS" NULL
- `bill_other_expenses` MONEY NULL
- `gf_id` DECIMAL(18, 0) NULL
- `contract_id` DECIMAL(18, 0) NULL
- `major_customer_part` MONEY NULL
- `bill_number` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `bill_date` DATETIME NULL
- `compu_name` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `cashier_disk_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `cust_name` VARCHAR(75) COLLATE "Arabic_CI_AS" NULL
- `sale_class` INTEGER NULL
- `money_change` MONEY NULL
- `network_money` MONEY NULL
- `network_id` DECIMAL(18, 0) NULL

### 📦 `Branches_shortcoming` · 21,005 rows

_PK: branch_id, product_id, store_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NOT NULL
- `id` DECIMAL(18, 0) NOT NULL
- `class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `general` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `amount` FLOAT NULL

### 📦 `Branches_stores` · 3 rows

_PK: branch_id, store_id_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NOT NULL
- `store_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `store_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `store_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 📦 `Branches_unit_edit` · 1 rows

_PK: unit_edit_id_

- `unit_edit_id` DECIMAL(18, 0) NOT NULL
- `insert_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `unit_id` DECIMAL(18, 0) NULL
- `unit_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `unit_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `unit_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### ✅ `Cash_depots` · 5 rows

_PK: cash_depot_id_

- `cash_depot_id` DECIMAL(18, 0) NOT NULL
- `cash_depot_code` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `cash_depot_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `cash_depot_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `cash_depot_class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `cash_depot_current_money` MONEY NULL
- `account_number` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `bank_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### ✅ `Cash_disk_close` · 3,608 rows

_PK: cdc_id_

- `cdc_id` DECIMAL(18, 0) NOT NULL
- `cdc_cash_id` DECIMAL(18, 0) NULL
- `cdc_emp_id` DECIMAL(18, 0) NULL
- `cdc_shift_start_time` DATETIME NULL
- `cdc_start_cash` MONEY NULL
- `cdc_curr_cash` MONEY NULL
- `cdc_act_cash` MONEY NULL
- `cdc_to_emp_id` DECIMAL(18, 0) NULL
- `cdc_fcs_id` DECIMAL(18, 0) NULL
- `cdc_trans_value` MONEY NULL
- `cdc_notice` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `last_gf_id` DECIMAL(18, 0) NULL

### 📦 `Checks` · 0 rows

_PK: ch_id_

- `ch_id` DECIMAL(18, 0) NOT NULL
- `gf_id` DECIMAL(18, 0) NULL
- `Flag` INTEGER NULL
- `out_in` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `ch_number` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `ch_date_created` SMALLDATETIME NULL
- `ch_valid_date` SMALLDATETIME NULL
- `ch_status` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `ch_status_change_date` DATETIME NULL
- `ch_expenses` MONEY NULL
- `name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `cashed` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `gf_id_cash` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 📦 `Co_bank` · 2 rows

_PK: bank_id_

- `bank_id` DECIMAL(18, 0) NOT NULL
- `bank_code` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `bank_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `bank_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `bank_address` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `bank_tel` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 📦 `Companys` · 1,210 rows

_PK: company_id_

- `company_id` DECIMAL(18, 0) NOT NULL
- `company_code` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `co_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `mobile` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `tel` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `address` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### ✅ `Customer` · 4,597 rows

_PK: customer_id_

- `customer_id` DECIMAL(18, 0) NOT NULL
- `customer_code` VARCHAR(25) COLLATE "Arabic_CI_AS" NULL
- `customer_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `customer_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `job_id` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `mobile` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `tel` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `address` VARCHAR(250) COLLATE "Arabic_CI_AS" NULL
- `customer_class_id` DECIMAL(18, 0) NULL
- `customer_major` DECIMAL(18, 0) NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `start_work_date` DATETIME NULL
- `customer_max_money` MONEY NULL
- `customer_current_money` MONEY NULL
- `customer_rate_pay` FLOAT NULL
- `customer_house_no` VARCHAR(25) COLLATE "Arabic_CI_AS" NULL
- `customer_pay_type` INTEGER NULL
- `customer_start_money` MONEY NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `contract_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `area_id` DECIMAL(18, 0) NULL
- `sales_man` DECIMAL(18, 0) NULL
- `sale_class_id` DECIMAL(18, 0) NULL
- `sell_price_buy` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `customer_disc_local` FLOAT NULL
- `customer_disc_import` FLOAT NULL
- `customer_insurance_code` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL

### 📦 `Customer_Area` · 9 rows

_PK: no declared key_

- `area_id` DECIMAL(18, 0) NOT NULL
- `area_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `area_name_ar` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `area_name_en` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 📦 `Customer_Class` · 2 rows

_PK: customer_class_id_

- `customer_class_id` DECIMAL(18, 0) NOT NULL
- `class_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `class_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 📦 `DB_online_update_Error` · 8 rows

_PK: error_id_

- `error_id` DECIMAL(18, 0) NOT NULL
- `trans_id` DECIMAL(18, 0) NOT NULL
- `table_id` INTEGER NULL
- `trans_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `trans` TEXT(16) COLLATE "Arabic_CI_AS" NULL
- `ex` TEXT(16) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `EMP_CONTROL` · 46 rows

_PK: emp_id_

- `emp_id` DECIMAL(18, 0) NOT NULL
- `A` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `A1` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `A2` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `A3` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `A4` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `A5` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `A6` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `A7` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `A8` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `A9` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B1` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B2` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B3` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B4` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B5` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B6` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B7` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B8` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B9` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B10` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B11` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B12` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B13` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B14` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B15` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B16` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B17` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B18` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B19` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B20` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B21` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B22` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B23` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B24` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B25` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B26` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B27` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B28` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `C` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `C1` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `C2` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `C3` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `C4` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `C5` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `C6` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `C7` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D1` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D2` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D3` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D4` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D5` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D6` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D7` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D8` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D9` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `E` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `E1` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `E2` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `E3` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `E4` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `E5` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F1` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F2` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F3` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F4` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F5` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F6` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F7` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F8` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F9` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F10` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F11` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F12` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F13` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F14` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F15` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F16` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F17` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `GA` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `GA1` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `GA2` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `GA3` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `GA4` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `GA5` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `GA6` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G1` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G2` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G3` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G4` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G5` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G6` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G7` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G8` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G9` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G10` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G11` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G12` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G13` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G14` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G15` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G16` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G17` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G18` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G19` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G20` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `H` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `H1` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `H2` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I1` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I2` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I3` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I4` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I5` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I6` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G21` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G22` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F18` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `E6` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `E7` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F19` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F20` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F21` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I7` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I8` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I9` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I10` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I11` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I12` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I13` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I14` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I15` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I16` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I17` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I18` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B29` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G23` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D10` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G24` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `A10` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B0` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F22` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F23` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `E8` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B30` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B31` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J1` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J2` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J3` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J4` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J5` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J6` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J7` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J8` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J9` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J10` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J11` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J12` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J13` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J14` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J15` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J16` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J17` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J18` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F24` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J19` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J20` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J21` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J22` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J23` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J24` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B32` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `J25` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `25` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B33` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G26` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G27` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G28` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G29` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G30` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F25` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G25` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F26` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `D11` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I19` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I20` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `I21` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B34` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F28` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `B35` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `F27` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `G31` CHAR(1) COLLATE "Arabic_CI_AS" NULL

### ✅ `Employee` · 46 rows

_PK: emp_id_

- `emp_id` DECIMAL(18, 0) NOT NULL
- `emp_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `emp_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `emp_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `emp_gender` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `job_id` DECIMAL(18, 0) NULL
- `birth_date` SMALLDATETIME NULL
- `hire_date` SMALLDATETIME NULL
- `work_date` SMALLDATETIME NULL
- `mobile` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `home_tel` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `address` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `card_id` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `card_date` DATETIME NULL
- `card_place` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `max_disc_per` DECIMAL(19, 4) NULL
- `max_disc_money` MONEY NULL
- `show_buy` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `show_cash_disk_history` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `show_total_sales_report` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `use_compu` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `username` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `pass` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `salary_typ` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `basic_salary` MONEY NULL
- `more_salary` MONEY NULL
- `emp_cust_max_money` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_add_product` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_edit_product` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_r_sale_date` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_r_sale_bill_num` INTEGER NULL
- `emp_add_cust` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_edit_cust` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_del_cust` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_commission1` FLOAT NULL
- `emp_commission2` FLOAT NULL
- `emp_edit_sell_price` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `absence_money` MONEY NULL
- `allaw_r_sale` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `numof_customer` INTEGER NULL
- `emp_show_money` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_change_cash_disk` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `allaw_sale_credit` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `allaw_un_sale` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `allaw_sale_delivery` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `cash_advance` MONEY NULL
- `allaw_save_cash_credit` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_del_vendor` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_del_product` CHAR(1) COLLATE "Arabic_CI_AS" NULL

### 📦 `Employee_absence_money` · 2 rows

_PK: no declared key_

- `emp_id` DECIMAL(18, 0) NOT NULL
- `emp_absence_money` MONEY NULL
- `month_salary` DATETIME NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### ✅ `Employee_cash_advance` · 139 rows

_PK: cash_advance_id_

- `cash_advance_id` DECIMAL(18, 0) NOT NULL
- `emp_id` DECIMAL(18, 0) NOT NULL
- `cash_advance` MONEY NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `type` CHAR(1) COLLATE "Arabic_CI_AS" NULL

### 📦 `Employee_commission` · 0 rows

_PK: no declared key_

- `emp_id` DECIMAL(18, 0) NOT NULL
- `emp_commission` MONEY NULL
- `month_salary` DATETIME NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 📦 `Employee_daily_time` · 92 rows

_PK: no declared key_

- `emp_code` DECIMAL(18, 0) NOT NULL
- `start_end` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `Saturday` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `Sunday` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `Monday` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `Tuesday` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `Wednesday` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `Thursday` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `Friday` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 📦 `Employee_deduction` · 19 rows

_PK: no declared key_

- `emp_id` DECIMAL(18, 0) NOT NULL
- `emp_deduction` MONEY NULL
- `month_salary` DATETIME NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 📦 `Employee_over_commission` · 33 rows

_PK: no declared key_

- `emp_id` DECIMAL(18, 0) NOT NULL
- `emp_over_commission` MONEY NULL
- `month_salary` DATETIME NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### ✅ `Employee_salary` · 379 rows

_PK: no declared key_

- `salary_id` DECIMAL(18, 0) NOT NULL
- `emp_id` DECIMAL(18, 0) NOT NULL
- `state` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `basic_salary` MONEY NULL
- `emp_commission` MONEY NULL
- `emp_over_commission` MONEY NULL
- `emp_deduction` MONEY NULL
- `emp_absence_money` MONEY NULL
- `total` MONEY NULL
- `month_salary` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `cash_advance` MONEY NULL

### 📦 `Employee_work_time` · 2,138 rows

_PK: id_

- `id` DECIMAL(18, 0) NOT NULL
- `employee_id` DECIMAL(18, 0) NULL
- `day_start` DATETIME NULL
- `daily_start` DATETIME NULL
- `day_end` DATETIME NULL
- `daily_end` DATETIME NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `day_class` CHAR(1) COLLATE "Arabic_CI_AS" NULL

### 📦 `Flag` · 55 rows

_PK: no declared key_

- `f_id` DECIMAL(18, 0) NOT NULL
- `f_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `f_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL

### ✅ `Gedo_Dividends_paied` · 32 rows

_PK: dividends_id_

- `dividends_id` DECIMAL(18, 0) NOT NULL
- `coow_id` DECIMAL(18, 0) NULL
- `yaer_id` INTEGER NULL
- `gf_id` DECIMAL(18, 0) NULL
- `paied_money` MONEY NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### ✅ `Gedo_Financial` · 176,310 rows

_PK: gf_id_

- `gf_id` DECIMAL(18, 0) NOT NULL
- `gf_code` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `gf_gedo_type` INTEGER NULL
- `gf_value` MONEY NULL
- `gf_from_type` INTEGER NULL
- `gf_from_id` DECIMAL(18, 0) NULL
- `gf_to_type` INTEGER NULL
- `gf_to_id` DECIMAL(18, 0) NULL
- `gf_notes` VARCHAR(250) COLLATE "Arabic_CI_AS" NULL
- `gf_computer` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `gf_actual_cashier` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `gf_form_type` INTEGER NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 📦 `Gedo_Vendors` · 20,784 rows

_PK: gv_id_

- `gv_id` DECIMAL(18, 0) NOT NULL
- `gf_id` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `Flag` INTEGER NULL
- `gv_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `gv_for_him` MONEY NULL
- `gv_for_me` MONEY NULL
- `total` MONEY NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL

### 📦 `Gedo_branches` · 8,855 rows

_PK: gb_id_

- `gb_id` DECIMAL(18, 0) NOT NULL
- `gf_id` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `Flag` INTEGER NULL
- `gb_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `branch_id` DECIMAL(18, 0) NULL
- `gb_for_him` MONEY NULL
- `gb_for_me` MONEY NULL
- `total` MONEY NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 📦 `Gedo_customers` · 118,493 rows

_PK: gc_id_

- `gc_id` DECIMAL(18, 0) NOT NULL
- `gf_id` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `Flag` INTEGER NULL
- `gc_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `customer_id` DECIMAL(18, 0) NULL
- `gc_for_him` MONEY NULL
- `gc_for_me` MONEY NULL
- `total` MONEY NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL

### 📦 `Gedo_employee` · 635 rows

_PK: no declared key_

- `ge_id` DECIMAL(18, 0) NOT NULL
- `gf_id` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `flag` INTEGER NULL
- `ge_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `emp_id` DECIMAL(18, 0) NULL
- `ge_for_him` MONEY NULL
- `ge_for_me` MONEY NULL
- `total` MONEY NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Gedo_installment` · 0 rows

_PK: no declared key_

- `gi_id` DECIMAL(18, 0) NOT NULL
- `f_id` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `flag` INTEGER NULL
- `gi_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `cu_id` DECIMAL(18, 0) NULL
- `gi_for_him` MONEY NULL
- `gi_for_me` MONEY NULL
- `total` MONEY NULL
- `insert_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Jobs` · 8 rows

_PK: job_id_

- `job_id` DECIMAL(18, 0) NOT NULL
- `job_code` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `job_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `job_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 📦 `News_bar` · 0 rows

_PK: no declared key_

- `id` DECIMAL(18, 0) NOT NULL
- `news_id` DECIMAL(18, 0) NULL
- `news` VARCHAR(300) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `syndicate_id` DECIMAL(18, 0) NULL
- `company_id` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `news_insert_date` DATETIME NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `deleted_date` DATETIME NULL

### 📦 `Order_details` · 590 rows

_PK: details_id, order_id_

- `details_id` DECIMAL(18, 0) NOT NULL
- `order_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NULL
- `amount` FLOAT NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL
- `product_price` MONEY NULL
- `product_disc` FLOAT NULL
- `buy_price` MONEY NULL
- `tax_price` MONEY NULL
- `buy_amount` DECIMAL(18, 2) NULL

### 📦 `Order_header` · 7 rows

_PK: order_id_

- `order_id` DECIMAL(18, 0) NOT NULL
- `order_class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `product_number` INTEGER NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `buy_money` MONEY NULL
- `product_money` MONEY NULL

### ✅ `Product_Amount` · 67,376 rows

_PK: counter_id, product_id, store_id_

- `counter_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NOT NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `amount` DECIMAL(18, 3) NULL
- `buy_price` MONEY NULL
- `sell_price` MONEY NULL
- `tax_price` MONEY NULL
- `exp_date` DATETIME NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `Product_update` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `Product_update_date` DATETIME NULL
- `pa_id` DECIMAL(18, 0) NOT NULL

### 📦 `Product_Changes` · 36,190 rows

_PK: product_change_id_

- `product_change_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NULL
- `class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `sell_price_old` MONEY NULL
- `buy_price_old` MONEY NULL
- `tax_price_old` MONEY NULL
- `unit1_2_old` DECIMAL(18, 0) NULL
- `unit1_3_old` DECIMAL(18, 0) NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `tax_price` MONEY NULL
- `unit1_2` DECIMAL(18, 0) NULL
- `unit1_3` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Product_Dose` · 69 rows

_PK: dose_id_

- `dose_id` DECIMAL(18, 0) NOT NULL
- `dose_code` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `dose_name_ar` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `dose_name_en` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` DECIMAL(18, 0) NULL

### 📦 `Product_Vendor` · 42,563 rows

_PK: PV_id, product_id, vendor_id_

- `PV_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `vendor_id` DECIMAL(18, 0) NOT NULL
- `PV_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `buy_price` MONEY NULL
- `tax_price` MONEY NULL
- `sell_price` MONEY NULL
- `product_disc1` DECIMAL(18, 0) NULL
- `product_disc2` DECIMAL(18, 0) NULL
- `product_disc3` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 📦 `Product_amount_Change` · 533,275 rows

_PK: no declared key_

- `id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NULL
- `product_id` DECIMAL(18, 0) NULL
- `store_id` DECIMAL(18, 0) NULL
- `old_amount` FLOAT NULL
- `new_amount` FLOAT NULL
- `exp_date` DATETIME NULL
- `form_type` INTEGER NULL
- `form_notice` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `tax_price` MONEY NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `in_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL

### 📦 `Product_amount_reg_update` · 46,982 rows

_PK: id_

- `id` DECIMAL(18, 0) NOT NULL
- `paru_id` DECIMAL(18, 0) NULL
- `product_id` DECIMAL(18, 0) NULL
- `store_id` DECIMAL(18, 0) NULL
- `counter_id` DECIMAL(18, 0) NULL
- `old_amount` FLOAT NULL
- `new_amount` FLOAT NULL
- `new_exp_date` DATETIME NULL
- `old_exp_date` DATETIME NULL
- `sell_price` MONEY NULL
- `tax_price` MONEY NULL
- `buy_price` MONEY NULL
- `store_date` DATETIME NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `product_unit` DECIMAL(18, 0) NULL
- `notes` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL

### 📦 `Product_amount_update` · 4,154 rows

_PK: id_

- `id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NULL
- `store_id` DECIMAL(18, 0) NULL
- `counter_id` DECIMAL(18, 0) NULL
- `old_amount` FLOAT NULL
- `new_amount` FLOAT NULL
- `new_exp_date` DATETIME NULL
- `old_exp_date` DATETIME NULL
- `sell_price` MONEY NULL
- `tax_price` MONEY NULL
- `buy_price` MONEY NULL
- `store_date` DATETIME NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `product_unit` DECIMAL(18, 0) NULL
- `notes` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Product_description` · 250 rows

_PK: pd_id_

- `pd_id` DECIMAL(18, 0) NOT NULL
- `pd_code` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `pd_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `pd_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 📦 `Product_groups` · 437 rows

_PK: group_id_

- `group_id` DECIMAL(18, 0) NOT NULL
- `group_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `group_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `group_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 📦 `Product_online_Changes` · 0 rows

_PK: no declared key_

- `product_change_id` DECIMAL(18, 0) NULL
- `product_id` DECIMAL(18, 0) NULL
- `class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `sell_price_old` MONEY NULL
- `buy_price_old` MONEY NULL
- `tax_price_old` MONEY NULL
- `unit1_2_old` DECIMAL(18, 0) NULL
- `unit1_3_old` DECIMAL(18, 0) NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `tax_price` MONEY NULL
- `unit1_2` DECIMAL(18, 0) NULL
- `unit1_3` DECIMAL(18, 0) NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL

### 📦 `Product_price_change` · 90 rows

_PK: price_change_id_

- `price_change_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `product_id` DECIMAL(18, 0) NULL
- `counter_id` DECIMAL(18, 0) NULL
- `old_buy_price` MONEY NULL
- `old_tax_price` MONEY NULL
- `new_buy_price` MONEY NULL
- `new_tax_price` MONEY NULL
- `product_amount` DECIMAL(18, 0) NULL
- `unit_id` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 📦 `Product_units` · 26 rows

_PK: unit_id_

- `unit_id` DECIMAL(18, 0) NOT NULL
- `unit_code` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `unit_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `unit_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### ✅ `Products` · 53,639 rows

_PK: product_id_

- `product_id` DECIMAL(18, 0) NOT NULL
- `product_code` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_fast_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `product_int_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `product_name_ar` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `product_name_en` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `product_scientific_name` NVARCHAR(200) COLLATE "Arabic_CI_AS" NULL
- `product_drug` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `company_id` DECIMAL(18, 0) NULL
- `product_has_expire` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `site_id` DECIMAL(18, 0) NULL
- `product_buy_number` DECIMAL(18, 0) NULL
- `product_big_number` DECIMAL(18, 0) NULL
- `product_small_number` DECIMAL(18, 0) NULL
- `sell_price` MONEY NULL
- `product_disc1` DECIMAL(10, 0) NULL
- `product_disc2` DECIMAL(18, 0) NULL
- `tax_price` MONEY NULL
- `buy_price` MONEY NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_unit1` DECIMAL(18, 0) NULL
- `product_unit2` DECIMAL(18, 0) NULL
- `product_unit3` DECIMAL(18, 0) NULL
- `product_unit1_2` DECIMAL(18, 0) NULL
- `product_unit1_3` DECIMAL(18, 0) NULL
- `group_id` DECIMAL(18, 0) NULL
- `pd_id` DECIMAL(18, 0) NULL
- `product_print_barcode` INTEGER NOT NULL
- `product_allow_disc` INTEGER NULL
- `product_max_disc` FLOAT NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `up_date` DATETIME NULL
- `up_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(300) COLLATE "Arabic_CI_AS" NULL
- `product_minus` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_made` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code1` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_int_code2` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_int_code3` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_int_code4` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_sale_unit` DECIMAL(18, 0) NULL
- `product_unit1_sale` DECIMAL(18, 0) NULL
- `unit2_sell_price` MONEY NULL
- `unit3_sell_price` MONEY NULL
- `sell_clause` MONEY NULL
- `unit2_sell_price_clause` MONEY NULL
- `unit3_sell_price_clause` MONEY NULL
- `amount_zero` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code5` VARCHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code6` VARCHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code7` VARCHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code8` VARCHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code9` VARCHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code10` VARCHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code11` VARCHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code12` VARCHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code13` VARCHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code14` VARCHAR(1) COLLATE "Arabic_CI_AS" NULL
- `no_print_name` CHAR(1) COLLATE "Arabic_CI_AS" NULL

### 📦 `Products_online` · 0 rows

_PK: no declared key_

- `product_id` DECIMAL(18, 0) NOT NULL
- `product_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `product_fast_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `product_int_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `product_name_ar` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `product_name_en` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `product_scientific_name` NVARCHAR(200) COLLATE "Arabic_CI_AS" NULL
- `product_drug` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `company_id` DECIMAL(18, 0) NULL
- `product_has_expire` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `site_id` DECIMAL(18, 0) NULL
- `product_buy_number` DECIMAL(18, 0) NULL
- `product_big_number` DECIMAL(18, 0) NULL
- `product_small_number` DECIMAL(18, 0) NULL
- `sell_price` MONEY NULL
- `product_disc1` DECIMAL(18, 0) NULL
- `product_disc2` DECIMAL(18, 0) NULL
- `tax_price` MONEY NULL
- `buy_price` MONEY NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_unit1` DECIMAL(18, 0) NULL
- `product_unit2` DECIMAL(18, 0) NULL
- `product_unit3` DECIMAL(18, 0) NULL
- `product_unit1_2` DECIMAL(18, 0) NULL
- `product_unit1_3` DECIMAL(18, 0) NULL
- `group_id` DECIMAL(18, 0) NULL
- `pd_id` DECIMAL(18, 0) NULL
- `product_print_barcode` INTEGER NOT NULL
- `product_allow_disc` INTEGER NULL
- `product_max_disc` FLOAT NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `up_date` DATETIME NULL
- `up_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(300) COLLATE "Arabic_CI_AS" NULL
- `product_minus` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_made` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_int_code1` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_int_code2` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_int_code3` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_int_code4` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `product_sale_unit` DECIMAL(18, 0) NULL
- `product_unit1_sale` DECIMAL(18, 0) NULL
- `unit2_sell_price` MONEY NULL
- `unit3_sell_price` MONEY NULL
- `amount_zero` CHAR(1) COLLATE "Arabic_CI_AS" NULL

### ✅ `Purchase_details` · 132,664 rows

_PK: details_id, purchase_id_

- `details_id` DECIMAL(18, 0) NOT NULL
- `purchase_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `exp_date` DATETIME NULL
- `amount` FLOAT NULL
- `bouns` FLOAT NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `gain_price` MONEY NULL
- `tax_price` MONEY NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `back_amount` FLOAT NULL
- `back_price` MONEY NULL
- `back_bouns` DECIMAL(18, 0) NULL
- `back_tax_price` MONEY NULL
- `back_details_1` MONEY NULL
- `back_details_2` MONEY NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `co_tax_price` MONEY NULL

### ✅ `Purchase_header` · 12,807 rows

_PK: purchase_id_

- `purchase_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `order_id` DECIMAL(18, 0) NULL
- `class` VARCHAR(2) COLLATE "Arabic_CI_AS" NULL
- `product_number` INTEGER NULL
- `total_bill` MONEY NULL
- `bill_disc_per` FLOAT NULL
- `bill_disc_money` MONEY NULL
- `bill_other_expenses` MONEY NULL
- `cashier_id` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `bill_number` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `bill_date` DATETIME NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `total_back` MONEY NULL
- `total_after_back` MONEY NULL
- `notes` TEXT(16) COLLATE "Arabic_CI_AS" NULL
- `gf_id` DECIMAL(18, 0) NULL
- `back_number` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `sell_back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `man_back_details` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `customer_id` DECIMAL(18, 0) NULL
- `bill_tax` MONEY NULL

### 📦 `Run_Backup` · 5 rows

_PK: job_id_

- `job_id` DECIMAL(18, 0) NOT NULL
- `job_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `job_bath` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `every_hour` INTEGER NULL
- `del_backup` INTEGER NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 📦 `Sale_classes` · 2 rows

_PK: no declared key_

- `sale_class_id` DECIMAL(18, 0) NOT NULL
- `sale_class_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `sale_class_name` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Sales_delivery_del_details` · 49 rows

_PK: details_id, sales_delivery_id_

- `details_id` DECIMAL(18, 0) NOT NULL
- `sales_delivery_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `exp_date` DATETIME NULL
- `amount` FLOAT NOT NULL
- `sale_unit` INTEGER NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `disc_money` MONEY NULL
- `disc_per` DECIMAL(18, 0) NULL
- `total_sell` MONEY NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 📦 `Sales_delivery_del_header` · 15 rows

_PK: sales_delivery_id_

- `sales_delivery_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `customer_id` DECIMAL(18, 0) NULL
- `class` INTEGER NULL
- `product_number` INTEGER NULL
- `total_bill` MONEY NULL
- `total_after_disc` MONEY NULL
- `total_bill_net` MONEY NULL
- `total_disc_per` DECIMAL(18, 0) NULL
- `total_disc_money` MONEY NULL
- `customer_disc_per` DECIMAL(18, 0) NULL
- `bill_cash` MONEY NULL
- `cashier_id` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(200) COLLATE "Arabic_CI_AS" NULL
- `bill_other_expenses` MONEY NULL
- `gf_id` DECIMAL(18, 0) NULL
- `contract_id` DECIMAL(18, 0) NULL
- `major_customer_part` MONEY NULL
- `bill_number` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `bill_date` DATETIME NULL
- `compu_name` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `cashier_disk_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `sale_class` INTEGER NULL
- `ticket_name` CHAR(100) COLLATE "Arabic_CI_AS" NULL
- `ticket_id` CHAR(50) COLLATE "Arabic_CI_AS" NULL
- `ticket_num` CHAR(50) COLLATE "Arabic_CI_AS" NULL

### 📦 `Sales_delivery_details` · 0 rows

_PK: details_id, sales_delivery_id_

- `details_id` DECIMAL(18, 0) NOT NULL
- `sales_delivery_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `exp_date` DATETIME NULL
- `amount` FLOAT NOT NULL
- `sale_unit` INTEGER NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `disc_money` MONEY NULL
- `disc_per` DECIMAL(18, 0) NULL
- `total_sell` MONEY NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `back_amount` FLOAT NULL
- `back_price` MONEY NULL
- `back_unit` INTEGER NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 📦 `Sales_delivery_header` · 0 rows

_PK: sales_delivery_id_

- `sales_delivery_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `customer_id` DECIMAL(18, 0) NULL
- `class` INTEGER NULL
- `product_number` INTEGER NULL
- `total_bill` MONEY NULL
- `total_after_disc` MONEY NULL
- `total_bill_net` MONEY NULL
- `total_disc_per` DECIMAL(18, 0) NULL
- `total_disc_money` MONEY NULL
- `customer_disc_per` DECIMAL(18, 0) NULL
- `bill_cash` MONEY NULL
- `cashier_id` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(200) COLLATE "Arabic_CI_AS" NULL
- `bill_other_expenses` MONEY NULL
- `gf_id` DECIMAL(18, 0) NULL
- `contract_id` DECIMAL(18, 0) NULL
- `major_customer_part` MONEY NULL
- `bill_number` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `bill_date` DATETIME NULL
- `compu_name` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `cashier_disk_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `sale_class` INTEGER NULL
- `ticket_name` CHAR(100) COLLATE "Arabic_CI_AS" NULL
- `ticket_id` CHAR(50) COLLATE "Arabic_CI_AS" NULL
- `ticket_num` CHAR(50) COLLATE "Arabic_CI_AS" NULL

### ✅ `Sales_details` · 317,848 rows

_PK: details_id, sales_id_

- `details_id` DECIMAL(18, 0) NOT NULL
- `sales_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `exp_date` DATETIME NULL
- `amount` FLOAT NOT NULL
- `sale_unit_change` DECIMAL(18, 0) NULL
- `sale_unit` INTEGER NULL
- `sell_price` MONEY NOT NULL
- `buy_price` MONEY NULL
- `disc_money` MONEY NULL
- `disc_per` DECIMAL(18, 3) NULL
- `total_sell` MONEY NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `back_amount` FLOAT NULL
- `back_unit_change` DECIMAL(18, 0) NULL
- `back_price` MONEY NULL
- `back_unit` INTEGER NULL
- `back_gf_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `sales_details_id` DECIMAL(18, 0) NOT NULL

### 📦 `Sales_details_Temp` · 0 rows

_PK: no declared key_

- `details_id` DECIMAL(18, 0) NOT NULL
- `sales_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `exp_date` DATETIME NULL
- `amount` FLOAT NOT NULL
- `sale_unit_change` DECIMAL(18, 0) NULL
- `sale_unit` INTEGER NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `disc_money` MONEY NULL
- `disc_per` DECIMAL(18, 0) NULL
- `total_sell` MONEY NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `back_amount` FLOAT NULL
- `back_unit_change` DECIMAL(18, 0) NULL
- `back_price` MONEY NULL
- `back_unit` INTEGER NULL
- `back_gf_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### ✅ `Sales_header` · 160,640 rows

_PK: sales_id_

- `sales_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `customer_id` DECIMAL(18, 0) NULL
- `class` INTEGER NULL
- `product_number` INTEGER NULL
- `bill_money_befor` MONEY NULL
- `total_bill` MONEY NULL
- `total_after_disc` MONEY NULL
- `total_bill_net` MONEY NULL
- `total_disc_per` DECIMAL(18, 3) NULL
- `total_disc_money` MONEY NULL
- `total_product_disc` MONEY NULL
- `customer_disc_per` DECIMAL(18, 0) NULL
- `bill_cash` MONEY NULL
- `cashier_id` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(200) COLLATE "Arabic_CI_AS" NULL
- `bill_other_expenses` MONEY NULL
- `gf_id` DECIMAL(18, 0) NULL
- `contract_id` DECIMAL(18, 0) NULL
- `major_customer_part` MONEY NULL
- `bill_number` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `bill_date` DATETIME NULL
- `compu_name` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `cashier_disk_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `cust_name` VARCHAR(75) COLLATE "Arabic_CI_AS" NULL
- `sale_class` INTEGER NULL
- `network_id` DECIMAL(18, 0) NULL
- `network_money` MONEY NULL
- `money_change` MONEY NULL
- `delivery_man_id` DECIMAL(8, 0) NULL
- `ticket_name` CHAR(100) COLLATE "Arabic_CI_AS" NULL
- `ticket_id` CHAR(50) COLLATE "Arabic_CI_AS" NULL
- `ticket_num` CHAR(50) COLLATE "Arabic_CI_AS" NULL

### 📦 `Sales_header_Temp` · 0 rows

_PK: no declared key_

- `sales_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `customer_id` DECIMAL(18, 0) NULL
- `class` INTEGER NULL
- `product_number` INTEGER NULL
- `bill_money_befor` MONEY NULL
- `total_bill` MONEY NULL
- `total_after_disc` MONEY NULL
- `total_bill_net` MONEY NULL
- `total_disc_per` DECIMAL(18, 0) NULL
- `total_disc_money` MONEY NULL
- `total_product_disc` MONEY NULL
- `customer_disc_per` DECIMAL(18, 0) NULL
- `bill_cash` MONEY NULL
- `cashier_id` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(200) COLLATE "Arabic_CI_AS" NULL
- `bill_other_expenses` MONEY NULL
- `gf_id` DECIMAL(18, 0) NULL
- `contract_id` DECIMAL(18, 0) NULL
- `major_customer_part` MONEY NULL
- `bill_number` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `bill_date` DATETIME NULL
- `compu_name` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `cashier_disk_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `cust_name` VARCHAR(75) COLLATE "Arabic_CI_AS" NULL
- `ticket_name` CHAR(100) COLLATE "Arabic_CI_AS" NULL
- `ticket_id` CHAR(50) COLLATE "Arabic_CI_AS" NULL
- `ticket_num` CHAR(50) COLLATE "Arabic_CI_AS" NULL

### 📦 `Shortcoming` · 9,403 rows

_PK: id_

- `id` DECIMAL(18, 0) NOT NULL
- `class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_id` DECIMAL(18, 0) NULL
- `general` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `notes` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `store_id` DECIMAL(18, 0) NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `amount` FLOAT NULL

### 📦 `Sites` · 221 rows

_PK: site_id_

- `site_id` DECIMAL(18, 0) NOT NULL
- `site_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `site_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `site_full_name` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `site_major` DECIMAL(18, 0) NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 📦 `Start_stock_details` · 4 rows

_PK: details_id, sstock_id_

- `details_id` DECIMAL(18, 0) NOT NULL
- `sstock_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `exp_date` DATETIME NULL
- `amount` FLOAT NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `gain_price` MONEY NULL
- `tax_price` MONEY NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL
- `update_uid` DECIMAL(18, 0) NULL
- `update_date` DATETIME NULL
- `unit_id` DECIMAL(18, 0) NULL
- `unit_change` DECIMAL(18, 0) NULL

### 📦 `Start_stock_header` · 3 rows

_PK: sstock_id_

- `sstock_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `product_number` INTEGER NULL
- `total_bill` MONEY NULL
- `cashier_id` DECIMAL(18, 0) NULL
- `notes` TEXT(16) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `insert_date` DATETIME NULL
- `update_uid` DECIMAL(18, 0) NULL
- `update_date` DATETIME NULL

### 📦 `Store_convert_details` · 0 rows

_PK: details_id, store_convert_id_

- `details_id` DECIMAL(18, 0) NOT NULL
- `store_convert_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NULL
- `counter_id` DECIMAL(18, 0) NULL
- `amount` FLOAT NULL
- `exp_date` DATETIME NULL
- `unit_id` DECIMAL(18, 0) NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `insert_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Store_convert_header` · 0 rows

_PK: store_convert_id_

- `store_convert_id` DECIMAL(18, 0) NOT NULL
- `from_store_id` DECIMAL(18, 0) NULL
- `to_store_id` DECIMAL(18, 0) NULL
- `total_sell_price` MONEY NULL
- `total_buy_price` MONEY NULL
- `product_number` INTEGER NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Stores` · 2 rows

_PK: store_id_

- `store_id` DECIMAL(18, 0) NOT NULL
- `store_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `store_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `store_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `start_update_date` DATETIME NULL

### 📦 `Temp_Purchase_details` · 39 rows

_PK: details_id, temp_purchase_id_

- `details_id` DECIMAL(18, 0) NOT NULL
- `temp_purchase_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NULL
- `exp_date` DATETIME NULL
- `amount` FLOAT NULL
- `bouns` FLOAT NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `gain_price` MONEY NULL
- `tax_price` MONEY NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Temp_Purchase_header` · 2 rows

_PK: temp_purchase_id_

- `temp_purchase_id` DECIMAL(18, 0) NOT NULL
- `store_id` DECIMAL(18, 0) NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `class` VARCHAR(2) COLLATE "Arabic_CI_AS" NULL
- `product_number` INTEGER NULL
- `total_bill` MONEY NULL
- `bill_disc_per` FLOAT NULL
- `bill_disc_money` MONEY NULL
- `bill_other_expenses` MONEY NULL
- `bill_number` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `bill_date` DATETIME NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `bill_tax` MONEY NULL

### ✅ `Tuning_accounts` · 872 rows

_PK: Tuning_accounts_id_

- `Tuning_accounts_id` DECIMAL(18, 0) NOT NULL
- `class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `who_class` INTEGER NULL
- `who_id` DECIMAL(18, 0) NULL
- `Tuning_accounts_reason_id` DECIMAL(18, 0) NULL
- `Tuning_accounts_money` MONEY NULL
- `notes` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 📦 `Tuning_accounts_reason` · 6 rows

_PK: Tuning_accounts_reason_id_

- `Tuning_accounts_reason_id` DECIMAL(18, 0) NOT NULL
- `Tuning_accounts_reason_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `Tuning_accounts_reason_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### ✅ `Vendor` · 92 rows

_PK: vendor_id_

- `vendor_id` DECIMAL(18, 0) NOT NULL
- `vendor_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `vendor_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `vendor_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `tel` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `mobile` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `address` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `company_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `vendor_max_money` MONEY NULL
- `vendor_current_money` MONEY NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `vendor_start_money` MONEY NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `emp_tel` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `emp_tel_details` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `emp_area_manegar` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `emp_area_manegar_details` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `emp_deliv` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `emp_deliv_details` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `emp_get_money` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `emp_get_money_details` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `ven_notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `ven_return` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL

### 📦 `barcode_temp` · 2 rows

_PK: no declared key_

- `co_tel1` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_name1` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `barcode1` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `name1` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `code1` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `exp1` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `sell1` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_tel2` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_name2` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `barcode2` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `name2` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `code2` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `exp2` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `sell2` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_tel3` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_name3` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `barcode3` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `name3` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `code3` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `exp3` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `sell3` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_tel4` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_name4` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `barcode4` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `name4` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `code4` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `exp4` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `sell4` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_tel5` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_name5` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `barcode5` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `name5` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `code5` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `exp5` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `sell5` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_tel6` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `co_name6` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `barcode6` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `name6` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `code6` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `exp6` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `sell6` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL

### 📦 `co_inf` · 1 rows

_PK: no declared key_

- `id` DECIMAL(10, 0) NOT NULL
- `com_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `com_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `idl` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `ide` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `owner` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `manegar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `tel` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `fax` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `address` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `up_date` DATETIME NULL
- `uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `s_print_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `s_intro` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `s_co_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `s_co_tel` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `s_finish` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `s_idl` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `s_ide` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `s_cust` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `s_emp` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `mini_money` MONEY NULL
- `num_of_copy` INTEGER NULL
- `bar_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `bar_tel` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `p_bar_name` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `p_bar_tel` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `bar_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `bar_size` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `syndicate_id` DECIMAL(18, 0) NULL
- `branch_id` INTEGER NULL
- `master_branch_id` INTEGER NULL
- `logo` IMAGE NULL
- `main_eg1` IMAGE NULL
- `main_eg2` IMAGE NULL
- `online_product_id` DECIMAL(18, 0) NULL
- `product_price_update_id` DECIMAL(18, 0) NULL
- `product_update_id` DECIMAL(18, 0) NULL
- `no_decimal` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `no_exp` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `auto_unsaved` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `trans_id` DECIMAL(18, 0) NULL

### ✅ `company_Owner` · 2 rows

_PK: coow_id_

- `coow_id` DECIMAL(18, 0) NOT NULL
- `coow_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `coow_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `coow_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `tel` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `mobile` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `address` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `coow_current_money` MONEY NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `coow_start_money` MONEY NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 📦 `customer_contracts` · 0 rows

_PK: contract_id_

- `contract_id` DECIMAL(18, 0) NOT NULL
- `customer_id` DECIMAL(18, 0) NULL
- `contract_code` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `contract_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `max_bill_money` MONEY NULL
- `bill_disc` DECIMAL(18, 2) NULL
- `customer_pay_rate` DECIMAL(18, 2) NULL
- `customer_pay_value` MONEY NULL
- `bill_disc_rule` INTEGER NULL
- `company_pay_rule` INTEGER NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `product_disc` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `local_product_disc` DECIMAL(18, 2) NULL
- `imported_product_disc` DECIMAL(18, 2) NULL
- `insert_date` DATETIME NULL
- `insert_uid` DECIMAL(18, 0) NULL
- `update_date` DATETIME NULL
- `update_uid` DECIMAL(18, 0) NULL

### 📦 `dtproperties` · 0 rows

_PK: id, property_

- `id` INTEGER NOT NULL
- `objectid` INTEGER NULL
- `property` VARCHAR(64) COLLATE "Arabic_CI_AS" NOT NULL
- `value` VARCHAR(255) COLLATE "Arabic_CI_AS" NULL
- `uvalue` NVARCHAR(255) COLLATE "Arabic_CI_AS" NULL
- `lvalue` IMAGE NULL
- `version` INTEGER NOT NULL

### 📦 `installment` · 0 rows

_PK: no declared key_

- `cu_id` DECIMAL(18, 0) NOT NULL
- `cu_name` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `cu_code` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `cu_tel` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `cu_address` VARCHAR(200) COLLATE "Arabic_CI_AS" NULL
- `cu_man_name` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `cu_man_code` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `cu_man_tel` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `cu_man_address` VARCHAR(200) COLLATE "Arabic_CI_AS" NULL
- `cu_total` MONEY NULL
- `cu_start` MONEY NULL
- `cu_end` MONEY NULL
- `cu_month_num` INTEGER NULL
- `cu_month_money` MONEY NULL
- `cu_sth_id` DECIMAL(18, 0) NULL
- `cu_emp` DECIMAL(18, 0) NULL
- `cu_current_credit` MONEY NULL
- `insert_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `notes` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL

### 📦 `installment_state` · 0 rows

_PK: no declared key_

- `id` DECIMAL(18, 0) NOT NULL
- `details_id` DECIMAL(18, 0) NOT NULL
- `cu_id` DECIMAL(18, 0) NOT NULL
- `state` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `pay_month` DATETIME NULL
- `installment_value` MONEY NULL
- `insert_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 📦 `sysdiagrams` · 0 rows

_PK: diagram_id_

- `name` NVARCHAR(128) COLLATE "Arabic_CI_AS" NOT NULL
- `principal_id` INTEGER NOT NULL
- `diagram_id` INTEGER NOT NULL
- `version` INTEGER NULL
- `definition` VARBINARY NULL

### 📦 `user_login` · 7,434 rows

_PK: lu_id_

- `lu_id` DECIMAL(18, 0) NOT NULL
- `u_id` DECIMAL(18, 0) NULL
- `start_time` DATETIME NULL
- `end_time` DATETIME NULL
- `compu_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL

### 📦 `versions` · 18 rows

_PK: no declared key_

- `ver_id` DECIMAL(18, 0) NOT NULL
- `ver_code` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 📦 `zz_fix_backup_20260730` · 4 rows

_PK: no declared key_

- `tbl` VARCHAR(64) COLLATE "Arabic_CI_AS" NULL
- `key_desc` VARCHAR(64) COLLATE "Arabic_CI_AS" NULL
- `col` VARCHAR(64) COLLATE "Arabic_CI_AS" NULL
- `old_value` NVARCHAR(400) COLLATE "Arabic_CI_AS" NULL
- `backed_up` DATETIME NULL

### 📦 `zz_quarantine_purchase_details` · 553 rows

_PK: no declared key_

- `branch_id` DECIMAL(18, 0) NOT NULL
- `details_id` DECIMAL(18, 0) NOT NULL
- `purchase_id` DECIMAL(18, 0) NOT NULL
- `product_id` DECIMAL(18, 0) NOT NULL
- `counter_id` DECIMAL(18, 0) NOT NULL
- `exp_date` DATETIME NULL
- `amount` FLOAT NULL
- `bouns` FLOAT NULL
- `sell_price` MONEY NULL
- `buy_price` MONEY NULL
- `gain_price` MONEY NULL
- `tax_price` MONEY NULL
- `back` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `back_amount` FLOAT NULL
- `back_price` MONEY NULL
- `back_bouns` FLOAT NULL
- `back_tax_price` MONEY NULL
- `insert_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `co_tax_price` MONEY NULL
- `host_header_bill_date` DATETIME NULL
- `host_header_insert_date` DATETIME NULL
- `quarantined_at` DATETIME NOT NULL
