# Phase 2 Setup — Parallel Testing on Elsanta + Mshala

**Duration:** 3 months of parallel testing on ProCare Dev (192.168.1.10)  
**Pilot branches:** Elsanta + Mshala (read/write on ProCare OS)  
**Production branch:** Main (stays on eStock until cutover)  
**Endpoints:** Elsanta & Mshala POS terminals, employee mobile app

---

## 1. ProCare Database Setup (ProCare Dev, 192.168.1.10)

### 1.1 Create the ProCare database

On **192.168.1.10**, using SQL Server Management Studio (SSMS) or sqlcmd:

```sql
-- Create the ProCare OS database
CREATE DATABASE [ProCare];
GO

USE [ProCare];
GO

-- Run the clean schema (from sql/procare-schema.sql in this repo)
-- Execute the full schema DDL here
-- This creates all tables, indexes, FK constraints, check constraints
```

**Key schema elements:**
- `branches` (code, name_ar, name_en) — Main, Elsanta, Mshala
- `products` (code, name_ar, name_en, scientific_name, prices, barcodes)
- `stock_batches` (product_id, branch_id, batch_id, amount, exp_date)
- `sales` + `sale_lines` (with branch_id, cashier_id, customer_id, FEFO batch picking)
- `purchases` + `purchase_lines` (vendor tracking)
- `customers` (credit_limit, current_balance, mobile)
- `ledger_entries` (branch_id on every row)
- All with FOREIGN KEYS, NOT NULL constraints, proper indexes

See [`sql/procare-schema.sql`](../sql/procare-schema.sql) for the full DDL.

### 1.2 Seed initial data

**Option A: Mirror from eStock (Phase 1 complete)**
- Fill in `config/connections.json` with:
  - `estock_source`: read-only login on 192.168.1.2 (Mshala)
  - `procare_database`: read/write login on 192.168.1.10 (ProCare Dev)
- Run the backend: `python run.py`
- Trigger mirror: `POST /api/etl/mirror`
- This populates ProCare with all products, customers, vendors, stock, sales history from eStock

**Option B: Direct SQL restore** (if you have a recent ProCare backup)
- Restore directly to 192.168.1.10

### 1.3 Create dedicated SQL logins

For **eStock (read-only, Mshala 192.168.1.2)**:
```sql
-- On Mshala
CREATE LOGIN [procare_readonly] WITH PASSWORD = 'strong_password';
USE [stock];
CREATE USER [procare_readonly] FROM LOGIN [procare_readonly];
ALTER ROLE [db_datareader] ADD MEMBER [procare_readonly];
-- Verify: EXEC sp_helprolemember 'db_datareader';
```

For **ProCare (read/write, ProCare Dev 192.168.1.10)**:
```sql
-- On ProCare Dev
CREATE LOGIN [procare_app] WITH PASSWORD = 'strong_password';
USE [ProCare];
CREATE USER [procare_app] FROM LOGIN [procare_app];
ALTER ROLE [db_owner] ADD MEMBER [procare_app];
```

### 1.4 Enable the backend connection

Update `config/connections.json`:
```json
{
  "network_host": "192.168.1.10",
  "estock_source": {
    "server": "192.168.1.2",
    "database": "stock",
    "username": "procare_readonly",
    "password": "strong_password"
  },
  "procare_database": {
    "server": "192.168.1.10",
    "database": "ProCare",
    "username": "procare_app",
    "password": "strong_password"
  },
  "branches": {
    "main": { "name_ar": "الرئيسي", "name_en": "Main" },
    "elsanta": { "name_ar": "السنتا", "name_en": "Elsanta", "pilot": true },
    "mshala": { "name_ar": "مشعل", "name_en": "Mshala", "pilot": true }
  }
}
```

Start the backend:
```bash
cd src/backend
python -m pip install -r requirements.txt
python run.py
```

Verify via `/api/health`:
```bash
curl http://127.0.0.1:8000/api/health | jq .
# Should show: "data_backend": "procare", "databases_configured": {...}
```

---

## 2. Phase 2 Implementation — POS Write Path

### 2.1 Core POS operations to implement

**In `src/backend/app/`:**

#### 2.1.1 `pos.py` — POS transaction engine
```python
def create_sale(branch_id, cashier_id, customer_id, line_items, payment_method, credit_amount=0):
    """
    Atomic sale creation.
    
    Args:
      branch_id: 'main' | 'elsanta' | 'mshala'
      cashier_id: employee ID
      customer_id: customer ID (or None for cash)
      line_items: [{ product_id, batch_id, qty_sold, price_override }]
      payment_method: 'cash' | 'credit' | 'mixed'
      credit_amount: amount charged to customer credit (if payment_method='credit'|'mixed')
    
    Returns:
      { sale_id, branch_id, sale_date, total, lines_count, status }
    
    Logic:
      1. BEGIN TRANSACTION
      2. Validate: customer credit_limit, stock availability (FEFO), prices
      3. Create sales record (header)
      4. For each line_item:
         - Reserve batch (stock_movements: type='sale_reserved')
         - Create sale_line
      5. Deduct stock (stock_movements: type='sale_deduction')
      6. Update customer balance (if credit)
      7. Create ledger entries (branch ledger, GL revenue/COGS, customer ledger)
      8. COMMIT
      9. Return receipt JSON
    """
    pass

def create_return(sale_id, lines_to_return, reason):
    """Reverse a prior sale (advisory: manager approval first)."""
    pass

def get_sale_receipt(sale_id):
    """Fetch a completed sale with all lines (for reprint or customer copy)."""
    pass
```

#### 2.1.2 `stock_ops.py` — FEFO batch picking & stock deduction
```python
def reserve_batch_fefo(product_id, branch_id, qty, sale_id):
    """
    FEFO (First Expire First Out) batch picker.
    
    Logic:
      - Query stock_batches WHERE product_id=X AND branch_id=Y 
        AND exp_date > TODAY AND amount > 0
        ORDER BY exp_date ASC (earliest first)
      - Allocate qty across batches (greedy: exhaust earliest first)
      - Create stock_movements records (type='sale_reserved')
      - Return [{ batch_id, qty_allocated, exp_date }]
    """
    pass

def deduct_stock(branch_id, movements):
    """Apply reserved movements to stock (type='sale_deduction')."""
    pass
```

#### 2.1.3 `credit_mgmt.py` — Customer credit tracking
```python
def check_credit_available(customer_id, amount):
    """Check if customer has enough credit_limit - current_balance."""
    pass

def charge_credit(customer_id, amount, sale_id, reason):
    """Charge a sale to customer credit (creates ledger entry)."""
    pass

def get_customer_balance(customer_id):
    """Current balance, over_limit flag, days_overdue."""
    pass
```

#### 2.1.4 `cashier_ops.py` — Cashier shift tracking
```python
def open_cashier_shift(cashier_id, branch_id, opening_float):
    """Create a shift record (opening_float, opening_time)."""
    pass

def close_cashier_shift(shift_id, closing_float, notes):
    """Close a shift; reconcile against sales ledger."""
    pass

def get_cashier_performance(cashier_id, date_from, date_to):
    """Bills count, total revenue, avg basket, cash variance."""
    pass
```

### 2.2 API endpoints (expand `src/backend/app/api/routes.py`)

```python
# POS write operations (Phase 2)
@router.post("/pos/sale")
async def create_sale_endpoint(request: CreateSaleRequest):
    """
    POST /api/pos/sale
    {
      "branch": "elsanta",
      "cashier_id": 42,
      "customer_id": null,  # cash sale
      "items": [
        { "product_id": 5, "batch_id": 1001, "qty": 2, "price": 50.00 },
        { "product_id": 7, "batch_id": 1005, "qty": 1, "price": 75.00 }
      ],
      "payment_method": "cash",
      "credit_amount": 0
    }
    """
    # Validate branch is pilot (elsanta | mshala)
    # Call pos.create_sale(...)
    # Return 201 with receipt

@router.get("/pos/receipt/{sale_id}")
async def get_receipt(sale_id: int):
    """Fetch a sale receipt."""
    pass

@router.post("/pos/return")
async def create_return_endpoint(request: CreateReturnRequest):
    """Reverse a sale."""
    pass

@router.post("/pos/shift/open")
async def open_shift(request: OpenShiftRequest):
    """Cashier opens a shift."""
    pass

@router.post("/pos/shift/close")
async def close_shift(request: CloseShiftRequest):
    """Cashier closes a shift."""
    pass

@router.get("/pos/cashier/{cashier_id}/shift")
async def get_current_shift(cashier_id: int, branch: str):
    """Current active shift for a cashier."""
    pass
```

### 2.3 Branch-aware write validation

All write operations must:
1. Validate `branch` parameter is in pilot (`elsanta` | `mshala`)
2. Prevent writes to `main` (stays on eStock)
3. Enforce ProCare DB as system of record for pilot branches

```python
def _validate_pilot_branch(branch):
    """Ensure branch is a Phase-2 pilot."""
    pilot_branches = {"elsanta", "mshala"}
    if branch not in pilot_branches:
        raise ValueError(f"Branch '{branch}' is not a Phase-2 pilot. Write operations allowed only on {pilot_branches}.")
```

---

## 3. Employee Mobile App (Phase 2, Mshala focus)

### 3.1 Mobile requirements

- **Platform:** iOS/Android (React Native or Flutter)
- **Connectivity:** Works offline; syncs when connected
- **Features:**
  - Login (employee ID + PIN)
  - View assigned tasks (stocktake, order verification, returns processing)
  - Scan products/barcodes (low-stock alerts, expiry checks)
  - Create stock movements (transfers between counters, expiry locks)
  - View KPIs dashboard (today's sales, branch performance)
  - Submit photos (damage reports, shelf compliance)

### 3.2 Backend API for mobile

Add endpoints in `src/backend/app/api/routes.py`:

```python
@router.post("/mobile/login")
async def mobile_login(employee_id: int, pin: str, device_id: str):
    """Authenticate + return JWT token."""
    pass

@router.get("/mobile/tasks")
async def get_mobile_tasks(employee_id: int, branch: str):
    """Assigned tasks (stock count, order checks, returns)."""
    pass

@router.post("/mobile/scan")
async def process_barcode_scan(barcode: str, branch: str):
    """Return product info + current stock + expiry status."""
    pass

@router.post("/mobile/stocktake")
async def submit_stocktake(data: StocktakeReport):
    """Submit a stock count for reconciliation."""
    pass

@router.get("/mobile/sync")
async def sync_data(last_sync: datetime, branch: str):
    """Incremental sync of products, prices, stock, KPIs."""
    pass
```

---

## 4. Testing Strategy (3 months)

### 4.1 Pre-pilot validation

- ✅ **Schema validation:** All FKs, indexes, non-NULL constraints in place
- ✅ **Data migration:** Initial seed from eStock complete; reconcile
- ✅ **Connection test:** Both eStock (read-only) and ProCare (read/write) accessible
- ✅ **POS API test:** Create sale → deduct stock → update ledger (all in one transaction)
- ✅ **FEFO logic test:** Verify earliest-expiry batches picked first
- ✅ **Customer credit test:** Over-limit prevention; balance updates

### 4.2 Live pilot rollout (Week 1)

- **Elsanta:** Go-live on Monday. Cashiers use ProCare POS. All sales recorded to ProCare DB.
- **Mshala:** Go-live Wednesday. Employees use mobile app for stock ops + POS.

### 4.3 Parallel validation (Weeks 2–12)

- **Daily reconciliation:** eStock sales vs. ProCare (Elsanta + Mshala). Must match to the decimal.
- **Stock accuracy:** Pick FEFO batches, verify oldest are used first.
- **Customer credit:** Over-limit flags, collection reports.
- **Ledger balance:** GL revenue, branch ledger, GL balances reconcile.
- **Performance:** Response time < 2s for all operations (p99).

### 4.4 Success criteria

- ✅ Zero discrepancies between eStock and ProCare (sales, stock, ledger) after 30 days
- ✅ FEFO compliance: 100% of sales use earliest-expiry batches
- ✅ Mobile app used daily on Mshala; > 95% uptime
- ✅ No lost transactions or data corruption

---

## 5. Rollback Plan

If critical issues discovered during 3-month pilot:

1. **Immediate:** Elsanta + Mshala stop all POS writes (read-only mode)
2. **Diagnosis:** Reconcile ProCare ↔ eStock; identify data divergence
3. **Recovery:** If < 1 day divergence, restore ProCare from daily backup + re-run Phase 1 mirror
4. **Revert:** Cashiers return to eStock POS temporarily
5. **Root cause:** Fix in code, re-test on shadow DB, resume pilot after sign-off

---

## 6. Handoff to Phase 3 (Post-pilot)

After 3-month validation:

1. **Backup:** Full backup of ProCare (Elsanta + Mshala data)
2. **Main cutover:** Run Phase 1 mirror for Main branch; seed ProCare with all Main data
3. **Final reconciliation:** All 3 branches on ProCare; verify totals match eStock
4. **Go-live:** All terminals + mobile use ProCare; eStock retired
5. **Post-go-live support:** Monitor for 2 weeks; handle any edge cases

---

## Checklist

- [ ] ProCare database created on 192.168.1.10
- [ ] Schema DDL applied (procare-schema.sql)
- [ ] Dedicated SQL logins created (procare_readonly, procare_app)
- [ ] config/connections.json filled with real credentials
- [ ] Backend connected and seeded (via /api/etl/mirror or direct restore)
- [ ] /api/health shows `"data_backend": "procare"`
- [ ] Phase 2 code implemented (pos.py, stock_ops.py, credit_mgmt.py, cashier_ops.py)
- [ ] POS API endpoints tested (POST /api/pos/sale, etc.)
- [ ] FEFO batch-picking logic verified on shadow DB
- [ ] Mobile API endpoints ready (login, tasks, scan, sync)
- [ ] Elsanta POS terminals configured & tested
- [ ] Mshala mobile app deployed & tested
- [ ] Daily reconciliation process documented
- [ ] Rollback procedure documented & tested
- [ ] Go/no-go sign-off before live pilot

---

**Next:** Implement Phase 2 code. See [`docs/06-roadmap.md`](06-roadmap.md) for timeline.
