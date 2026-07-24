# ProCare Dev Setup — Quick Start (5 min overview)

**Goal:** Set up ProCare database on 192.168.1.10, seed from eStock, enable live connection.

## 1. Run SQL Setup Script (on ProCare Dev)

```sql
-- Open SQL Server Management Studio
-- Connect to: 192.168.1.10
-- Execute: sql/setup-procare-dev.sql
-- Time: ~2 min
```

**What it does:**
- Creates `ProCare` database
- Creates schema (20+ tables: branches, products, customers, stock, sales, etc.)
- Creates logins: `procare_readonly` (read-only) and `procare_app` (read/write)
- Seeds branches (MAIN, ELSANTA, MSHALA)

## 2. Update Connection Config

```bash
# On your dev machine (where backend runs)
cp config/connections.example.json config/connections.json

# Edit config/connections.json with:
# estock_source.username = procare_readonly
# estock_source.password = <password from Step 1>
# procare_database.username = procare_app
# procare_database.password = <password from Step 1>
# procare_database.server = 192.168.1.10
```

## 3. Verify Database Connection

```bash
cd src/backend
python run.py

# In another terminal:
curl http://127.0.0.1:8000/api/health | jq .

# Expected: "data_backend": "procare" (not "demo")
```

## 4. Seed Data from eStock

```bash
# Trigger mirror (5-15 min depending on data volume)
curl -X POST http://127.0.0.1:8000/api/etl/mirror

# Verify
curl http://127.0.0.1:8000/api/etl/status | jq .
```

## 5. Verify Reconciliation

```bash
curl http://127.0.0.1:8000/api/etl/reconcile | jq .

# All checks should match between eStock and ProCare
```

## 6. Test POS (Optional)

```bash
# Open shift
curl -X POST http://127.0.0.1:8000/api/pos/shift/open \
  -d '{"cashier_id":1,"branch":"elsanta","opening_float":500}' \
  -H "Content-Type: application/json"

# Create sale
curl -X POST http://127.0.0.1:8000/api/pos/sale \
  -d '{"branch":"elsanta","cashier_id":1,"customer_id":null,"items":[{"product_id":5,"qty_sold":2}],"payment_method":"cash"}' \
  -H "Content-Type: application/json"

# Close shift (returns variance)
curl -X POST http://127.0.0.1:8000/api/pos/shift/close \
  -d '{"shift_id":1,"closing_float":600}' \
  -H "Content-Type: application/json"
```

---

**Full details:** See [`docs/10-procare-dev-setup.md`](docs/10-procare-dev-setup.md)

**Troubleshooting:** See "Troubleshooting" section in the full guide.

**Time estimate:** 1-2 hours (depending on data volume and network speed)
