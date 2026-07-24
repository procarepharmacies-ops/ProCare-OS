# eStock schema dump + ProCare coverage

- **Total tables:** 112
- **Mirrored by ProCare's ETL:** 20
- **Not yet mirrored:** 92

## Coverage gap (tables ProCare does NOT read)

- `Account_Tree` (10 cols) — 119 rows
- `Back_purchase_details` (11 cols) — 807 rows
- `Back_purchase_header` (11 cols) — 169 rows
- `Branch_money_convert` (11 cols) — 1,111 rows
- `Branch_money_order` (12 cols) — 1,111 rows
- `Branch_order_details` (16 cols) — 61,975 rows
- `Branch_order_header` (14 cols) — 8,237 rows
- `Branches` (52 cols) — 2 rows
- `Branches_Cash_disk_close` (14 cols) — 7,095 rows
- `Branches_Product_Amount` (16 cols) — 122,371 rows
- `Branches_Product_amount_Change` (18 cols) — 1,045,526 rows
- `Branches_Vendor` (18 cols) — 0 rows
- `Branches_back_purchase_details` (14 cols) — 819 rows
- `Branches_back_purchase_header` (12 cols) — 336 rows
- `Branches_cash_depots` (13 cols) — 15 rows
- `Branches_company_edit` (13 cols) — 16 rows
- `Branches_convert_details` (16 cols) — 61,975 rows
- `Branches_convert_header` (12 cols) — 8,237 rows
- `Branches_customer` (29 cols) — 0 rows
- `Branches_description_edit` (9 cols) — 0 rows
- `Branches_employee_edit` (56 cols) — 76 rows
- `Branches_group_edit` (9 cols) — 10 rows
- `Branches_mail` (10 cols) — 241 rows
- `Branches_products_edit` (53 cols) — 31,074 rows
- `Branches_shortcoming` (13 cols) — 20,877 rows
- `Branches_stores` (10 cols) — 3 rows
- `Branches_unit_edit` (9 cols) — 1 rows
- `Cash_disk_close` (14 cols) — 3,566 rows
- `Checks` (17 cols) — 0 rows
- `Co_bank` (10 cols) — 2 rows
- `Companys` (11 cols) — 1,210 rows
- `Customer_Area` (9 cols) — 9 rows
- `Customer_Class` (5 cols) — 2 rows
- `DB_online_update_Error` (7 cols) — 8 rows
- `EMP_CONTROL` (198 cols) — 45 rows
- `Employee_absence_money` (6 cols) — 2 rows
- `Employee_commission` (6 cols) — 0 rows
- `Employee_daily_time` (13 cols) — 90 rows
- `Employee_deduction` (6 cols) — 19 rows
- `Employee_over_commission` (6 cols) — 33 rows
- `Employee_work_time` (11 cols) — 2,137 rows
- `Flag` (3 cols) — 55 rows
- `Gedo_Financial` (16 cols) — 173,793 rows
- `Gedo_Vendors` (11 cols) — 20,591 rows
- `Gedo_branches` (10 cols) — 8,763 rows
- `Gedo_customers` (11 cols) — 117,567 rows
- `Gedo_employee` (10 cols) — 612 rows
- `Gedo_installment` (10 cols) — 0 rows
- `Jobs` (8 cols) — 8 rows
- `News_bar` (9 cols) — 0 rows
- `Order_details` (11 cols) — 590 rows
- `Order_header` (8 cols) — 7 rows
- `Product_Changes` (15 cols) — 35,890 rows
- `Product_Dose` (7 cols) — 69 rows
- `Product_Vendor` (12 cols) — 42,299 rows
- `Product_amount_Change` (16 cols) — 526,418 rows
- `Product_amount_reg_update` (18 cols) — 45,330 rows
- `Product_amount_update` (17 cols) — 3,392 rows
- `Product_description` (7 cols) — 250 rows
- `Product_groups` (7 cols) — 437 rows
- `Product_online_Changes` (15 cols) — 0 rows
- `Product_price_change` (12 cols) — 90 rows
- `Product_units` (7 cols) — 26 rows
- `Products_online` (47 cols) — 0 rows
- `Run_Backup` (7 cols) — 4 rows
- `Sale_classes` (5 cols) — 2 rows
- `Sales_delivery_del_details` (16 cols) — 49 rows
- `Sales_delivery_del_header` (31 cols) — 15 rows
- `Sales_delivery_details` (20 cols) — 0 rows
- `Sales_delivery_header` (31 cols) — 0 rows
- `Sales_details_Temp` (23 cols) — 0 rows
- `Sales_header_Temp` (33 cols) — 0 rows
- `Shortcoming` (12 cols) — 9,304 rows
- `Sites` (8 cols) — 221 rows
- `Start_stock_details` (16 cols) — 4 rows
- `Start_stock_header` (10 cols) — 3 rows
- `Store_convert_details` (11 cols) — 0 rows
- `Store_convert_header` (9 cols) — 0 rows
- `Stores` (8 cols) — 2 rows
- `Temp_Purchase_details` (12 cols) — 3 rows
- `Temp_Purchase_header` (15 cols) — 1 rows
- `Tuning_accounts` (9 cols) — 872 rows
- `Tuning_accounts_reason` (8 cols) — 6 rows
- `barcode_temp` (42 cols) — 2 rows
- `co_inf` (42 cols) — 1 rows
- `customer_contracts` (18 cols) — 0 rows
- `dtproperties` (7 cols) — 0 rows
- `installment` (20 cols) — 0 rows
- `installment_state` (10 cols) — 0 rows
- `sysdiagrams` (5 cols) — 0 rows
- `user_login` (5 cols) — 7,219 rows
- `versions` (4 cols) — 18 rows

## All tables

### 🔲 `Account_Tree` · 119 rows

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

### ✅ `Back_Sales_details` · 8,764 rows

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

### 🔲 `Back_purchase_details` · 807 rows

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

### 🔲 `Back_purchase_header` · 169 rows

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

### ✅ `Back_sales_header` · 6,906 rows

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

### 🔲 `Branch_money_convert` · 1,111 rows

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

### 🔲 `Branch_money_order` · 1,111 rows

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

### 🔲 `Branch_order_details` · 61,975 rows

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

### 🔲 `Branch_order_header` · 8,237 rows

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

### 🔲 `Branches` · 2 rows

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

### 🔲 `Branches_Cash_disk_close` · 7,095 rows

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

### 🔲 `Branches_Product_Amount` · 122,371 rows

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

### 🔲 `Branches_Product_amount_Change` · 1,045,526 rows

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

### 🔲 `Branches_Vendor` · 0 rows

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

### 🔲 `Branches_back_purchase_details` · 819 rows

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

### 🔲 `Branches_back_purchase_header` · 336 rows

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

### 🔲 `Branches_cash_depots` · 15 rows

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

### 🔲 `Branches_company_edit` · 16 rows

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

### 🔲 `Branches_convert_details` · 61,975 rows

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

### 🔲 `Branches_convert_header` · 8,237 rows

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

### 🔲 `Branches_customer` · 0 rows

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

### 🔲 `Branches_description_edit` · 0 rows

- `pd_edit_id` DECIMAL(18, 0) NOT NULL
- `insert_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `pd_id` DECIMAL(18, 0) NULL
- `pd_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `pd_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `pd_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 🔲 `Branches_employee_edit` · 76 rows

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

### 🔲 `Branches_group_edit` · 10 rows

- `group_edit_id` DECIMAL(18, 0) NOT NULL
- `insert_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `group_id` DECIMAL(18, 0) NULL
- `group_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `group_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `group_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 🔲 `Branches_mail` · 241 rows

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

### 🔲 `Branches_products_edit` · 31,074 rows

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

### ✅ `Branches_purchase_details` · 266,433 rows

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

### ✅ `Branches_purchase_header` · 25,170 rows

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

### ✅ `Branches_sales_details` · 499,364 rows

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

### ✅ `Branches_sales_header` · 254,335 rows

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

### 🔲 `Branches_shortcoming` · 20,877 rows

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

### 🔲 `Branches_stores` · 3 rows

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

### 🔲 `Branches_unit_edit` · 1 rows

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

### 🔲 `Cash_disk_close` · 3,566 rows

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

### 🔲 `Checks` · 0 rows

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

### 🔲 `Co_bank` · 2 rows

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

### 🔲 `Companys` · 1,210 rows

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

### ✅ `Customer` · 4,544 rows

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

### 🔲 `Customer_Area` · 9 rows

- `area_id` DECIMAL(18, 0) NOT NULL
- `area_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `area_name_ar` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `area_name_en` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### 🔲 `Customer_Class` · 2 rows

- `customer_class_id` DECIMAL(18, 0) NOT NULL
- `class_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `class_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 🔲 `DB_online_update_Error` · 8 rows

- `error_id` DECIMAL(18, 0) NOT NULL
- `trans_id` DECIMAL(18, 0) NOT NULL
- `table_id` INTEGER NULL
- `trans_type` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `trans` TEXT(16) COLLATE "Arabic_CI_AS" NULL
- `ex` TEXT(16) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 🔲 `EMP_CONTROL` · 45 rows

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

### ✅ `Employee` · 45 rows

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

### 🔲 `Employee_absence_money` · 2 rows

- `emp_id` DECIMAL(18, 0) NOT NULL
- `emp_absence_money` MONEY NULL
- `month_salary` DATETIME NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### ✅ `Employee_cash_advance` · 127 rows

- `cash_advance_id` DECIMAL(18, 0) NOT NULL
- `emp_id` DECIMAL(18, 0) NOT NULL
- `cash_advance` MONEY NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `type` CHAR(1) COLLATE "Arabic_CI_AS" NULL

### 🔲 `Employee_commission` · 0 rows

- `emp_id` DECIMAL(18, 0) NOT NULL
- `emp_commission` MONEY NULL
- `month_salary` DATETIME NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 🔲 `Employee_daily_time` · 90 rows

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

### 🔲 `Employee_deduction` · 19 rows

- `emp_id` DECIMAL(18, 0) NOT NULL
- `emp_deduction` MONEY NULL
- `month_salary` DATETIME NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 🔲 `Employee_over_commission` · 33 rows

- `emp_id` DECIMAL(18, 0) NOT NULL
- `emp_over_commission` MONEY NULL
- `month_salary` DATETIME NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### ✅ `Employee_salary` · 373 rows

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

### 🔲 `Employee_work_time` · 2,137 rows

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

### 🔲 `Flag` · 55 rows

- `f_id` DECIMAL(18, 0) NOT NULL
- `f_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `f_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL

### ✅ `Gedo_Dividends_paied` · 32 rows

- `dividends_id` DECIMAL(18, 0) NOT NULL
- `coow_id` DECIMAL(18, 0) NULL
- `yaer_id` INTEGER NULL
- `gf_id` DECIMAL(18, 0) NULL
- `paied_money` MONEY NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 🔲 `Gedo_Financial` · 173,793 rows

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

### 🔲 `Gedo_Vendors` · 20,591 rows

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

### 🔲 `Gedo_branches` · 8,763 rows

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

### 🔲 `Gedo_customers` · 117,567 rows

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

### 🔲 `Gedo_employee` · 612 rows

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

### 🔲 `Gedo_installment` · 0 rows

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

### 🔲 `Jobs` · 8 rows

- `job_id` DECIMAL(18, 0) NOT NULL
- `job_code` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `job_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `job_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 🔲 `News_bar` · 0 rows

- `id` DECIMAL(18, 0) NOT NULL
- `news_id` DECIMAL(18, 0) NULL
- `news` VARCHAR(300) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `syndicate_id` DECIMAL(18, 0) NULL
- `company_id` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `news_insert_date` DATETIME NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `deleted_date` DATETIME NULL

### 🔲 `Order_details` · 590 rows

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

### 🔲 `Order_header` · 7 rows

- `order_id` DECIMAL(18, 0) NOT NULL
- `order_class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `vendor_id` DECIMAL(18, 0) NULL
- `product_number` INTEGER NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `buy_money` MONEY NULL
- `product_money` MONEY NULL

### ✅ `Product_Amount` · 66,549 rows

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

### 🔲 `Product_Changes` · 35,890 rows

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

### 🔲 `Product_Dose` · 69 rows

- `dose_id` DECIMAL(18, 0) NOT NULL
- `dose_code` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `dose_name_ar` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `dose_name_en` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` DECIMAL(18, 0) NULL

### 🔲 `Product_Vendor` · 42,299 rows

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

### 🔲 `Product_amount_Change` · 526,418 rows

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

### 🔲 `Product_amount_reg_update` · 45,330 rows

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

### 🔲 `Product_amount_update` · 3,392 rows

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

### 🔲 `Product_description` · 250 rows

- `pd_id` DECIMAL(18, 0) NOT NULL
- `pd_code` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `pd_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `pd_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 🔲 `Product_groups` · 437 rows

- `group_id` DECIMAL(18, 0) NOT NULL
- `group_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `group_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `group_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 🔲 `Product_online_Changes` · 0 rows

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

### 🔲 `Product_price_change` · 90 rows

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

### 🔲 `Product_units` · 26 rows

- `unit_id` DECIMAL(18, 0) NOT NULL
- `unit_code` VARCHAR(10) COLLATE "Arabic_CI_AS" NULL
- `unit_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `unit_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### ✅ `Products` · 53,534 rows

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

### 🔲 `Products_online` · 0 rows

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

### ✅ `Purchase_details` · 131,295 rows

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

### ✅ `Purchase_header` · 12,669 rows

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

### 🔲 `Run_Backup` · 4 rows

- `job_id` DECIMAL(18, 0) NOT NULL
- `job_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `job_bath` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `every_hour` INTEGER NULL
- `del_backup` INTEGER NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL

### 🔲 `Sale_classes` · 2 rows

- `sale_class_id` DECIMAL(18, 0) NOT NULL
- `sale_class_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `sale_class_name` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 🔲 `Sales_delivery_del_details` · 49 rows

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

### 🔲 `Sales_delivery_del_header` · 15 rows

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

### 🔲 `Sales_delivery_details` · 0 rows

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

### 🔲 `Sales_delivery_header` · 0 rows

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

### ✅ `Sales_details` · 313,822 rows

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

### 🔲 `Sales_details_Temp` · 0 rows

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

### ✅ `Sales_header` · 158,366 rows

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

### 🔲 `Sales_header_Temp` · 0 rows

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

### 🔲 `Shortcoming` · 9,304 rows

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

### 🔲 `Sites` · 221 rows

- `site_id` DECIMAL(18, 0) NOT NULL
- `site_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `site_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `site_full_name` VARCHAR(150) COLLATE "Arabic_CI_AS" NULL
- `site_major` DECIMAL(18, 0) NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL

### 🔲 `Start_stock_details` · 4 rows

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

### 🔲 `Start_stock_header` · 3 rows

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

### 🔲 `Store_convert_details` · 0 rows

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

### 🔲 `Store_convert_header` · 0 rows

- `store_convert_id` DECIMAL(18, 0) NOT NULL
- `from_store_id` DECIMAL(18, 0) NULL
- `to_store_id` DECIMAL(18, 0) NULL
- `total_sell_price` MONEY NULL
- `total_buy_price` MONEY NULL
- `product_number` INTEGER NULL
- `notes` VARCHAR(100) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 🔲 `Stores` · 2 rows

- `store_id` DECIMAL(18, 0) NOT NULL
- `store_code` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `store_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `store_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `active` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(9) COLLATE "Arabic_CI_AS" NULL
- `start_update_date` DATETIME NULL

### 🔲 `Temp_Purchase_details` · 3 rows

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

### 🔲 `Temp_Purchase_header` · 1 rows

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

### 🔲 `Tuning_accounts` · 872 rows

- `Tuning_accounts_id` DECIMAL(18, 0) NOT NULL
- `class` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `who_class` INTEGER NULL
- `who_id` DECIMAL(18, 0) NULL
- `Tuning_accounts_reason_id` DECIMAL(18, 0) NULL
- `Tuning_accounts_money` MONEY NULL
- `notes` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL

### 🔲 `Tuning_accounts_reason` · 6 rows

- `Tuning_accounts_reason_id` DECIMAL(18, 0) NOT NULL
- `Tuning_accounts_reason_name_ar` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `Tuning_accounts_reason_name_en` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `deleted` CHAR(1) COLLATE "Arabic_CI_AS" NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `update_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
- `update_date` DATETIME NULL

### ✅ `Vendor` · 91 rows

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

### 🔲 `barcode_temp` · 2 rows

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

### 🔲 `co_inf` · 1 rows

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

### 🔲 `customer_contracts` · 0 rows

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

### 🔲 `dtproperties` · 0 rows

- `id` INTEGER NOT NULL
- `objectid` INTEGER NULL
- `property` VARCHAR(64) COLLATE "Arabic_CI_AS" NOT NULL
- `value` VARCHAR(255) COLLATE "Arabic_CI_AS" NULL
- `uvalue` NVARCHAR(255) COLLATE "Arabic_CI_AS" NULL
- `lvalue` IMAGE NULL
- `version` INTEGER NOT NULL

### 🔲 `installment` · 0 rows

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

### 🔲 `installment_state` · 0 rows

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

### 🔲 `sysdiagrams` · 0 rows

- `name` NVARCHAR(128) COLLATE "Arabic_CI_AS" NOT NULL
- `principal_id` INTEGER NOT NULL
- `diagram_id` INTEGER NOT NULL
- `version` INTEGER NULL
- `definition` VARBINARY NULL

### 🔲 `user_login` · 7,219 rows

- `lu_id` DECIMAL(18, 0) NOT NULL
- `u_id` DECIMAL(18, 0) NULL
- `start_time` DATETIME NULL
- `end_time` DATETIME NULL
- `compu_name` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL

### 🔲 `versions` · 18 rows

- `ver_id` DECIMAL(18, 0) NOT NULL
- `ver_code` VARCHAR(50) COLLATE "Arabic_CI_AS" NULL
- `insert_date` DATETIME NULL
- `insert_uid` VARCHAR(20) COLLATE "Arabic_CI_AS" NULL
