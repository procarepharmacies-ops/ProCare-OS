# ProCare Dev Setup — Database Configuration (192.168.1.10)

**Target:** Set up the ProCare OS database on ProCare Dev machine, seed initial data from eStock, and enable live connection.

**Timeline:** 1-2 hours (depending on data volume)

---

## Prerequisites

- **SQL Server 2019+** running on 192.168.1.10
- **SQL Server Management Studio (SSMS)** or `sqlcmd` CLI available
- **Network access:** From your dev machine to 192.168.1.10:1433
- **eStock connection:** 192.168.1.2 with read-only credentials (from Phase 1)
- **Backend code:** Phase 2 code deployed and tested locally

---

## Step 1: Create Database & Schema

### 1.1 Connect to ProCare Dev (192.168.1.10)

Open **SQL Server Management Studio** and connect:
- **Server name:** `192.168.1.10` (or `192.168.1.10,1433` if non-standard port)
- **Authentication:** Windows Auth (if on domain) or SQL Server Auth (if local user)
- **Login:** Your DBA account (must have `CREATE DATABASE` permission)

### 1.2 Run setup script

In SSMS, open `sql/setup-procare-dev.sql` and execute it:

```sql
-- This will:
-- 1. Drop existing 'ProCare' database (if present)
-- 2. Create fresh 'ProCare' database
-- 3. Create schema (tables, indexes, FKs)
-- 4. Create logins: procare_readonly (read-only), procare_app (read/write)
-- 5. Seed branches, jobs, sale_classes
-- 6. Verify table creation
```

**Expected output:**
```
ProCare database created successfully!
TABLE_NAME
----------
branches
cashier_shifts
customers
employees
job
... (20+ tables)
```

**Note:** Update passwords in the script before running:
- Line 22: `ChangeMe@123` → your actual password for `procare_readonly`
- Line 28: `ChangeMe@123` → your actual password for `procare_app`

### 1.3 Verify schema

Query the database to confirm tables exist:

```sql
USE ProCare;
SELECT COUNT(*) as TableCount FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo';
-- Expected: ~20
```

---

## Step 2: Create SQL Logins & Secure Access

### 2.1 eStock read-only login

On **Mshala (192.168.1.2)**, create a dedicated read-only login:

```sql
USE [master];
GO

CREATE LOGIN [procare_readonly] WITH PASSWORD = N'YourSecurePassword123!';
GO

USE [stock];
GO

CREATE USER [procare_readonly] FROM LOGIN [procare_readonly];
ALTER ROLE [db_datareader] ADD MEMBER [procare_readonly];
GO

-- Verify
EXECUTE AS LOGIN = 'procare_readonly';
SELECT USER_NAME();
GO
```

### 2.2 ProCare application login

On **ProCare Dev (192.168.1.10)**, verify the login was created:

```sql
USE [master];
GO

-- List logins
SELECT name, create_date FROM sys.server_principals 
WHERE type = 'S' AND name LIKE 'procare%';
GO

-- Verify procare_app can connect
USE ProCare;
EXECUTE AS USER = 'procare_app';
SELECT USER_NAME(), DB_NAME();
GO
```

### 2.3 Enable TCP/IP on SQL Server

On ProCare Dev, enable remote connections:

1. Open **SQL Server Configuration Manager**
2. Navigate to **SQL Server Network Configuration** → **Protocols for MSSQL...** (your instance name)
3. Right-click **TCP/IP** → **Enable**
4. Properties → **IP Addresses** tab → ensure at least one IP address is configured (e.g., 192.168.1.10, port 1433)
5. Restart SQL Server service

---

## Step 3: Configure Backend Connection

### 3.1 Update `config/connections.json`

Copy the template and fill in real credentials:

```bash
cp config/connections.example.json config/connections.json
```

Edit `config/connections.json`:

```json
{
  "network_host": "192.168.1.10",

  "estock_source": {
    "driver": "ODBC Driver 18 for SQL Server",
    "server": "192.168.1.2",
    "database": "stock",
    "username": "procare_readonly",
    "password": "YourSecurePassword123!",
    "encrypt": "yes",
    "trust_server_certificate": "yes"
  },

  "procare_database": {
    "driver": "ODBC Driver 18 for SQL Server",
    "server": "192.168.1.10",
    "database": "ProCare",
    "username": "procare_app",
    "password": "YourSecurePassword123!",
    "encrypt": "yes",
    "trust_server_certificate": "yes"
  },

  "branches": {
    "main": { "name_ar": "الرئيسي", "name_en": "Main" },
    "elsanta": { "name_ar": "السنتا", "name_en": "Elsanta", "pilot": true },
    "mshala": { "name_ar": "مشعل", "name_en": "Mshala", "pilot": true }
  }
}
```

**IMPORTANT:** `config/connections.json` is git-ignored. Never commit it.

### 3.2 Install SQL Server drivers (backend machine)

If running backend on a different machine, install the ODBC driver:

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt-get install odbc-mssql

# macOS
brew install msodbcsql18
```

**Windows:**
- Download "ODBC Driver 18 for SQL Server" from Microsoft
- Or run: `pip install pyodbc` (will auto-detect system ODBC drivers)

### 3.3 Test connection

From your backend machine, verify connectivity:

```bash
# Option 1: Python test
python -c "
import pyodbc
conn = pyodbc.connect(
    'Driver={ODBC Driver 18 for SQL Server};'
    'Server=192.168.1.10;'
    'Database=ProCare;'
    'UID=procare_app;'
    'PWD=YourSecurePassword123!;'
    'Encrypt=yes;'
    'TrustServerCertificate=yes'
)
print('Connected:', conn)
conn.close()
"

# Option 2: sqlcmd
sqlcmd -S 192.168.1.10 -U procare_app -P YourSecurePassword123! -d ProCare -Q "SELECT @@VERSION"
```

---

## Step 4: Seed Initial Data

### 4.1 Mirror from eStock (Phase 1 ETL)

Start the backend:

```bash
cd src/backend
python -m pip install -r requirements.txt  # if not done yet
python run.py
```

Verify health endpoint shows `"data_backend": "procare"`:

```bash
curl http://127.0.0.1:8000/api/health | jq .
```

Expected response:
```json
{
  "status": "ok",
  "data_backend": "procare",
  "databases_configured": {
    "procare": true,
    "estock": true,
    "titan": false
  }
}
```

### 4.2 Trigger mirror

Call the mirror endpoint to pull all products, customers, vendors, stock, sales from eStock:

```bash
# Trigger mirror (may take 5-15 minutes depending on data volume)
curl -X POST http://127.0.0.1:8000/api/etl/mirror

# Check status
curl http://127.0.0.1:8000/api/etl/status | jq .
```

Monitor the backend logs:
```
[INFO] ETL: Mirroring eStock → ProCare...
[INFO] ETL: Products: 53,474 inserted
[INFO] ETL: Customers: 1,197 inserted
[INFO] ETL: Vendors: 87 inserted
[INFO] ETL: Stock batches: 121,625 inserted
[INFO] ETL: Sales: 95,088 inserted (+ 4,359 returns)
[INFO] ETL: Mirror complete in 12m 34s
```

### 4.3 Verify data in ProCare Dev

On ProCare Dev, run a quick query:

```sql
USE ProCare;
GO

SELECT 'Products' as Metric, COUNT(*) as Count FROM products
UNION ALL
SELECT 'Customers', COUNT(*) FROM customers
UNION ALL
SELECT 'Vendors', COUNT(*) FROM vendors
UNION ALL
SELECT 'Stock batches', COUNT(*) FROM stock_batches
UNION ALL
SELECT 'Sales', COUNT(*) FROM sales
ORDER BY Metric;
GO
```

Expected output:
```
Metric            Count
Products          53474
Customers         1197
Vendors           87
Stock batches     121625
Sales             95088
```

---

## Step 5: Data Quality Reconciliation

### 5.1 Run reconciliation check

```bash
curl http://127.0.0.1:8000/api/etl/reconcile | jq .
```

Expected response:
```json
{
  "has_estock_source": true,
  "mode": "compare",
  "checks": {
    "sales_per_day": {
      "estock": 1001.74,
      "procare": 1001.74,
      "match": true
    },
    "stock_value_per_branch": {
      "estock": { "main": 2543210.50, "elsanta": 1876543.25 },
      "procare": { "main": 2543210.50, "elsanta": 1876543.25 },
      "match": true
    },
    "customer_balances_total": {
      "estock": 876543.21,
      "procare": 876543.21,
      "match": true
    },
    "vendor_payables_total": {
      "estock": 543210.75,
      "procare": 543210.75,
      "match": true
    }
  }
}
```

**All checks should match.** If not, check logs for data quality issues.

### 5.2 Sample live data

Test the dashboard KPIs against live ProCare data:

```bash
curl http://127.0.0.1:8000/api/dashboard/summary?branch=main | jq .

# Expected: Live KPIs from ProCare (not shadow DB)
```

---

## Step 6: Test Phase 2 POS Operations

### 6.1 Open a cashier shift

```bash
curl -X POST http://127.0.0.1:8000/api/pos/shift/open \
  -H "Content-Type: application/json" \
  -d '{
    "cashier_id": 1,
    "branch": "elsanta",
    "opening_float": 500
  }'

# Expected: 200 OK, { "shift_id": 1, "status": "open" }
```

### 6.2 Create a test sale

```bash
curl -X POST http://127.0.0.1:8000/api/pos/sale \
  -H "Content-Type: application/json" \
  -d '{
    "branch": "elsanta",
    "cashier_id": 1,
    "customer_id": null,
    "items": [
      { "product_id": 5, "qty_sold": 2 }
    ],
    "payment_method": "cash"
  }'

# Expected: 201 Created, { "sale_id": 1, "status": "completed", "total_amount": 100.00, ... }
```

### 6.3 Close the shift

```bash
curl -X POST http://127.0.0.1:8000/api/pos/shift/close \
  -H "Content-Type: application/json" \
  -d '{
    "shift_id": 1,
    "closing_float": 600
  }'

# Expected: 200 OK, { "variance": 0, "variance_pct": 0 }
```

---

## Step 7: Backup & Maintenance

### 7.1 Full backup

On ProCare Dev, create a full backup:

```sql
BACKUP DATABASE [ProCare]
TO DISK = N'D:\SQLBackups\ProCare_full_$(date).bak'
WITH FORMAT, INIT, COMPRESSION;
GO
```

### 7.2 Verify backup

```sql
RESTORE VERIFYONLY FROM DISK = N'D:\SQLBackups\ProCare_full_20260724.bak';
GO
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Cannot connect to 192.168.1.10:1433" | Check SQL Server is running on ProCare Dev; verify TCP/IP enabled in SQL Server Configuration Manager |
| "Login failed for user 'procare_app'" | Verify password in connections.json matches the password set in Step 2 |
| "No such table: products" | Verify setup-procare-dev.sql was executed completely; check table count in Step 4.3 |
| "Mirror failed: eStock unreachable" | Verify eStock is running on 192.168.1.2; check firewall allows 1433 traffic |
| "FEFO batch picking returns 0" | Run DBCC CHECKDB on ProCare; verify stock_batches has amount > 0 and exp_date in future |

---

## Checklist

- [ ] ProCare database created on 192.168.1.10
- [ ] Schema DDL applied (20+ tables)
- [ ] Logins created: procare_readonly, procare_app
- [ ] TCP/IP enabled on SQL Server
- [ ] ODBC drivers installed on backend machine
- [ ] config/connections.json filled with real credentials
- [ ] Backend can connect to ProCare (health check)
- [ ] eStock data mirrored (products, customers, vendors, stock, sales)
- [ ] Reconciliation passes (sales, stock value, balances all match)
- [ ] POS test sale created successfully
- [ ] Full backup completed
- [ ] Ready for Phase 2 pilot (Elsanta + Mshala)

---

**Next:** After this setup, Elsanta & Mshala branches are ready for 3-month parallel testing. See [`docs/09-phase-2-setup.md`](09-phase-2-setup.md) for pilot runbook.
