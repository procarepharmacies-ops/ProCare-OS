# Pilot Go-Live — Elsanta + Mshala (3-Month Parallel Testing)

**Timeline:** Week 1 (this week) — execute Steps 1–4 below

**Goal:** Both branches reading/writing to ProCare, running in parallel with eStock for validation

---

## Pre-Go-Live Checklist

Before any terminal touches ProCare, verify:

### Infrastructure
- [ ] ProCare Dev database created & seeded (docs/10-procare-dev-setup.md completed)
- [ ] eStock data mirrored to ProCare (reconciliation passed)
- [ ] Network: Elsanta & Mshala terminals can reach 192.168.1.10:1433
- [ ] Firewall: Port 1433 (SQL Server) open between branches and ProCare Dev
- [ ] ODBC driver: "ODBC Driver 18 for SQL Server" installed on all terminal machines
- [ ] Backup: Full backup of ProCare DB + daily backup scheduled

### Application
- [ ] Backend code deployed to ProCare Dev or dev machine (Python 3.11+)
- [ ] API endpoints wired: `/api/pos/sale`, `/api/pos/shift/*`, etc.
- [ ] POS frontend ready (Next.js, compiled & deployed)
- [ ] Mobile app deployed to Mshala devices (iOS/Android)
- [ ] SSL certificates: If required, installed on backend (HTTPS for production)

### Testing
- [ ] Unit tests pass: `pytest tests/test_pos_phase2.py` (all 21)
- [ ] Integration tests: POS sale → stock deduction → ledger entry → customer balance
- [ ] FEFO validation: Oldest-expiry batches picked first
- [ ] Credit validation: Over-limit prevention working
- [ ] Cashier reconciliation: Cash variance < 1% across 10 test shifts
- [ ] Performance: API response time < 2s for all operations (p99)

### Operations
- [ ] Daily reconciliation process documented
- [ ] Escalation contacts defined (dev team, store managers, finance)
- [ ] Rollback procedure tested & ready
- [ ] Monitoring dashboard live (Grafana or custom)
- [ ] Alerting configured (Slack/email on errors)

---

## Step 1: Pre-Pilot Data Sync (Day 1 Morning)

### 1.1 Final eStock snapshot

On **Mshala (192.168.1.2)**, create a snapshot of current state:

```sql
USE [stock];
GO

-- Capture current state for reconciliation
SELECT 'Sales (last 7 days)' as Metric,
       COUNT(*) as Count,
       SUM(total_net) as Total
FROM Sales_header
WHERE bill_date >= DATEADD(day, -7, GETDATE());

SELECT 'Stock value by branch' as Metric, COUNT(*), SUM(amount * sell_price)
FROM Branches_Product_Amount;

SELECT 'Customer balances' as Metric, SUM(customer_current_money)
FROM Customer;

SELECT 'Vendor payables' as Metric, SUM(vendor_current_money)
FROM Vendor;
```

**Save these numbers.** You'll compare ProCare to these at pilot end.

### 1.2 Final ProCare mirror

On backend, run mirror one more time to pull any recent eStock changes:

```bash
curl -X POST http://127.0.0.1:8000/api/etl/mirror
```

Verify reconciliation passes:

```bash
curl http://127.0.0.1:8000/api/etl/reconcile | jq '.checks'
```

### 1.3 Lock eStock (Elsanta + Mshala only)

On Mshala, create a view that enforces read-only mode for the two pilot branches (optional, but recommended):

```sql
USE [stock];
GO

-- Log showing pilot mode activated
INSERT INTO audit_log (event, branch, timestamp)
VALUES ('PILOT_MODE_ACTIVE: Elsanta & Mshala moving to ProCare. eStock read-only for these branches.',
        'MAIN,ELSANTA,MSHALA', GETDATE());
```

**Note:** Main branch continues using eStock; only Elsanta & Mshala read from ProCare.

---

## Step 2: Terminal Deployment (Day 1 Afternoon)

### 2.1 Elsanta branch configuration

On the **Elsanta POS terminal**, configure:

**Network:**
- Test connection to ProCare Dev: `ping 192.168.1.10` and `sqlcmd -S 192.168.1.10 -U procare_app -P <pwd> -Q "SELECT @@VERSION"`

**Application (Next.js frontend):**
```bash
# On dev machine, build optimized bundle
cd src/frontend
npm run build

# Copy to Elsanta terminal (via USB, network share, or CI/CD):
# .next/ → /opt/procare-pos/frontend/.next/
# Verify by accessing: http://localhost:3000
```

**Environment:**
```bash
# On Elsanta POS terminal
export NEXT_PUBLIC_API_BASE=http://192.168.1.10:8000
# or if backend runs locally: http://127.0.0.1:8000
```

**Start POS:**
```bash
cd /opt/procare-pos/frontend
npm start  # or: pm2 start npm -- run start
```

Verify dashboard loads and shows branch = "elsanta"

### 2.2 Mshala branch configuration

On **Mshala manager device**, deploy mobile app:

**iOS:**
- Build: `cd src/mobile && flutter build ios`
- Deploy via TestFlight or internal install
- Configure: API_BASE = `http://192.168.1.10:8000`

**Android:**
- Build: `flutter build apk`
- Copy APK to devices
- Install via `adb install app-release.apk`

**Verify:** Open app, login with employee credentials, see tasks list

---

## Step 3: Day 1 End-of-Day Checks (Evening)

### 3.1 Verify data integrity

**On ProCare Dev:**
```sql
USE ProCare;
GO

-- Check no duplicate data in stock
SELECT product_id, branch_id, COUNT(*) as batch_count
FROM stock_batches
GROUP BY product_id, branch_id
HAVING COUNT(*) > 10
ORDER BY batch_count DESC;
-- Expected: ~1 per product per branch (most products have 1 batch per branch)

-- Check all sales have a cashier
SELECT COUNT(*) as orphaned_sales
FROM sales
WHERE cashier_id IS NULL AND is_return = 0;
-- Expected: 0
```

### 3.2 Run smoke test on POS

On **Elsanta terminal:**
```bash
# Test 1: Open shift
curl -X POST http://192.168.1.10:8000/api/pos/shift/open \
  -d '{"cashier_id":1,"branch":"elsanta","opening_float":500}' \
  -H "Content-Type: application/json"
# Expected: 201, shift_id returned

# Test 2: Create a test sale
curl -X POST http://192.168.1.10:8000/api/pos/sale \
  -d '{"branch":"elsanta","cashier_id":1,"customer_id":null,"items":[{"product_id":1,"qty_sold":1}],"payment_method":"cash"}' \
  -H "Content-Type: application/json"
# Expected: 201, sale_id returned

# Test 3: Check stock deducted
curl http://192.168.1.10:8000/api/inventory/lookup?q=product_id:1&branch=elsanta | jq '.qty_on_hand'
# Expected: decreased by 1 from pre-test value

# Test 4: Close shift
curl -X POST http://192.168.1.10:8000/api/pos/shift/close \
  -d '{"shift_id":1,"closing_float":501}' \
  -H "Content-Type: application/json"
# Expected: 200, variance = 1 (or close to it)
```

**On Mshala mobile app:**
```
- Login: employee ID + PIN
- View tasks: should show stocktake, order verification, returns
- Scan barcode: should return product info + current stock
- Submit stocktake: should record to ProCare
```

### 3.3 Rollback test (optional, but recommended)

If anything fails, verify you can roll back:

```bash
# Restore ProCare from pre-test backup
sqlcmd -S 192.168.1.10 -U sa -P <pwd> \
  -Q "RESTORE DATABASE ProCare FROM DISK = 'D:\Backups\ProCare_pre_test.bak' WITH REPLACE"

# Revert terminals to eStock
# - Elsanta: reconfigure frontend to connect to eStock POS (if separate)
# - Mshala: disable mobile app, use manual processes
```

**Log the result:** Either "Rollback successful" or "Needs investigation"

---

## Step 4: Week 1 Go-Live (Monday Morning)

### 4.1 Manager briefing

**Elsanta & Mshala store managers must understand:**

1. **What's changing:** New ProCare POS replaces eStock (cashiers use different terminal)
2. **Branch switching:** Main still uses eStock; Elsanta & Mshala use ProCare
3. **Parallel validation:** We're comparing ProCare against eStock daily for 3 months
4. **Escalation:** If something breaks, call dev team immediately (do NOT retry)
5. **No manual entry:** All sales must go through ProCare (no workarounds)

### 4.2 Cashier training (30 min per branch)

**Elsanta team:**
- Show new POS interface (looks similar to eStock, but slightly different)
- Demo: Open shift → scan product → enter qty → payment → close shift
- Show common errors: insufficient stock, customer over limit
- Practice run: 10 test sales

**Mshala team:**
- Same as Elsanta
- Plus: Mobile app for stocktake & order verification

### 4.3 Go-live: 08:00 AM

**Elsanta:**
- First cashier opens shift on ProCare POS
- First customer transaction recorded to ProCare
- Monitor backend logs for errors

**Mshala:**
- First cashier opens shift on ProCare POS
- Mobile app: Employee does first stocktake
- Monitor reconciliation

**Main (control):**
- Continues using eStock (no changes)
- Managers compare daily sales with Elsanta & Mshala

### 4.4 First 4 hours (critical monitoring)

Keep a team member on-call to watch:

```bash
# Terminal 1: Live backend logs
tail -f /var/log/procare-backend.log

# Terminal 2: Health monitor (every 5 min)
watch -n 5 'curl -s http://192.168.1.10:8000/api/health | jq .'

# Terminal 3: Dashboard (every 15 min)
watch -n 900 'curl -s http://192.168.1.10:8000/api/dashboard/summary?branch=elsanta | jq .kpis'
```

**Alert on:**
- API errors (5xx)
- Database connection failures
- Slow queries (>5s)
- Stock discrepancies (negative amounts)
- Customer balance errors

---

## Daily Reconciliation (Weeks 1–12)

### 4.5 Daily closing procedure (each branch)

**At end of business (Elsanta & Mshala):**

```bash
# 1. Close all cashier shifts
curl -X POST http://192.168.1.10:8000/api/pos/shift/close \
  -d '{"shift_id":<last_shift_id>,"closing_float":<actual_cash>}' \
  -H "Content-Type: application/json"

# 2. Reconcile customer balances
curl http://192.168.1.10:8000/api/alerts/debtors | jq '.data | length'
# Expected: same count as yesterday (or explained growth)

# 3. Check expiry alerts
curl http://192.168.1.10:8000/api/alerts/expiry?branch=elsanta | jq '.d7 | length'
# Monitor trend: should decline as stock ages
```

### 4.6 End-of-day comparison (eStock vs ProCare)

**On Mshala (eStock):**
```sql
SELECT 'eStock: Sales today', COUNT(*), SUM(total_net) FROM Sales_header WHERE bill_date = CAST(GETDATE() AS DATE);
SELECT 'eStock: Low stock', COUNT(*) FROM Branches_Product_Amount WHERE amount < min_stock;
```

**On ProCare Dev:**
```sql
SELECT 'ProCare: Sales today (Elsanta)', COUNT(*), SUM(total_net) FROM sales WHERE branch_id = 2 AND CAST(sale_date AS DATE) = CAST(GETDATE() AS DATE);
SELECT 'ProCare: Low stock (Elsanta)', COUNT(*) FROM stock_batches WHERE branch_id = 2 AND amount < min_stock;
```

**Compare the two and log discrepancies.**

### 4.7 Weekly reconciliation report

Every Friday, compile:
```
Week of [DATE]:
- Elsanta: X sales, Y revenue, Z cash variance
- Mshala: X sales, Y revenue, Z cash variance
- eStock (Main): X sales, Y revenue
- Discrepancies vs eStock: [list or "none"]
- Issues encountered: [list or "none"]
- Rollback incidents: [count]
- Mobile app uptime: X%
```

**Send to:** Dev team, finance, store managers

---

## Success Criteria (End of Week 1)

- [ ] Both branches created first sale on ProCare (not on eStock)
- [ ] Daily sales figures match eStock within 0.1% (by branch)
- [ ] No data loss or corruption
- [ ] Cash reconciliation passes (variance < 1%)
- [ ] Cashier reconciliation: < 5% discrepancies resolved same-day
- [ ] Customer credit working: over-limit blocks sales
- [ ] FEFO: Oldest batches picked first (100% compliance)
- [ ] Mobile app uptime ≥ 95%
- [ ] No critical errors (database corruption, data loss, hangs)

**If not met:** Activate rollback, fix, retry following week

---

## 3-Month Parallel Testing (Weeks 2–12)

See [`docs/09-phase-2-setup.md`](09-phase-2-setup.md) for full testing strategy.

**Key milestones:**
- **Week 2:** Daily reconciliation stable
- **Week 4:** 30-day data validation (0 discrepancies)
- **Week 8:** Stress test (2x normal volume)
- **Week 12:** Sign-off from finance + operations

**Then:** Phase 3 — Main branch cutover

---

## Rollback Procedure (If Needed)

If critical issue discovered:

**Immediate (first 4 hours):**
1. Stop ProCare POS on affected branch
2. Revert terminals to eStock
3. Notify customers (if any transactions incomplete)
4. Restore ProCare DB from pre-issue backup

**Investigation (hours 4–24):**
1. Identify root cause (code bug, data corruption, etc.)
2. Fix in development environment
3. Test against shadow DB
4. Get approval from product team

**Re-deploy (next day or later):**
1. Re-run pre-go-live checklist
2. Deploy fixed code
3. Resume parallel testing

**Log:** Record incident in [`INCIDENTS.md`](INCIDENTS.md) for post-mortem

---

## Monitoring Dashboard (Live)

Set up a Grafana dashboard or simple HTML page showing:

```
┌─────────────────────────────────────┐
│ ProCare Pilot — Live Metrics         │
├─────────────────────────────────────┤
│ Elsanta:  5 sales today, $2,450     │
│ Mshala:   8 sales today, $3,100     │
│ Main (eStock): 12 sales, $5,200     │
│                                     │
│ ProCare vs eStock: +0.02% variance  │
│ API health: ✅ All endpoints        │
│ Database: ✅ OK                     │
│ Last sync: 2 min ago               │
└─────────────────────────────────────┘
```

Update every 15 minutes.

---

## Contacts & Escalation

| Role | Name | Phone | Email |
|------|------|-------|-------|
| Dev Lead | [TBD] | [TBD] | [TBD] |
| Finance Lead | [TBD] | [TBD] | [TBD] |
| Elsanta Manager | [TBD] | [TBD] | [TBD] |
| Mshala Manager | [TBD] | [TBD] | [TBD] |
| DevOps/DBA | [TBD] | [TBD] | [TBD] |

**Escalation path:**
1. Issue detected → call Dev Lead
2. Data corruption → call DBA + Dev Lead
3. Critical error (>1h down) → call DevOps + Finance Lead
4. Loss of transaction → rollback + post-mortem

---

**Ready?** Start with Step 1 (Pre-Pilot Data Sync).

