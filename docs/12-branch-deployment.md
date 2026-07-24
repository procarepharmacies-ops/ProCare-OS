# Branch Deployment Guide — Main, Elsanta, Mshala

**Purpose:** Configure each branch's POS terminals, mobile app, and connection to the correct data source.

---

## Branch Strategy (Weeks 1–12 Pilot)

| Branch | Data Source | POS Status | Mobile | Terminals | Manager |
|--------|-------------|-----------|--------|-----------|---------|
| **MAIN** | eStock (192.168.1.2) | No change | No | Legacy | [Name] |
| **ELSANTA** | ProCare (192.168.1.10) | Live | Limited | 3-5 | [Name] |
| **MSHALA** | ProCare (192.168.1.10) | Live | Full | 3-5 | [Name] |

---

## Branch Configuration Templates

### Main Branch (eStock, No Changes)

**Location:** Main pharmacy (primary)  
**Manager:** [Name] — [Phone] — [Email]

**Infrastructure:**
- POS terminals: Continue using existing eStock software
- Database: Continue using eStock on 192.168.1.2
- Network: No changes required
- Backups: eStock backup unchanged

**Monitoring:**
- Daily sales recorded on eStock only
- Used as control for Elsanta + Mshala comparison
- No data sync to ProCare (read-only snapshot only)

**Escalation:** If issues on Elsanta/Mshala discovered, compare metrics against Main to isolate problem

---

### Elsanta Branch (ProCare Pilot)

**Location:** [Address]  
**Manager:** [Name] — [Phone] — [Email]  
**Terminal Count:** 3–5 POS terminals  
**Daily Revenue:** $[Amount]

#### A. Terminal Configuration

**Hardware Requirements:**
- OS: Windows 10/11 or Linux
- CPU: Dual-core 2+ GHz
- RAM: 4+ GB
- Storage: 20+ GB free
- Network: Ethernet (preferred) or WiFi 802.11ac
- Internet: Stable 20+ Mbps (shared with other terminals)

**Network Setup (on each terminal):**

```bash
# 1. Test connectivity
ping 192.168.1.10          # ProCare Dev
ping 192.168.1.2           # Mshala (eStock, for comparison)

# 2. Test SQL connectivity
sqlcmd -S 192.168.1.10 -U procare_app -P <pwd> -Q "SELECT @@VERSION"

# 3. Test API
curl http://192.168.1.10:8000/api/health

# If all pass: ✅ Terminal ready
```

**Software Installation:**

```bash
# 1. Download backend code
git clone https://github.com/procarepharmacies-ops/procare-os.git
cd procare-os

# 2. Install dependencies
pip install -r src/backend/requirements.txt
npm install --prefix src/frontend

# 3. Build frontend
cd src/frontend && npm run build && cd ../..

# 4. Configure connection
cp config/connections.example.json config/connections.json
# Edit config/connections.json: set procare_database server to 192.168.1.10

# 5. Start backend (in background)
nohup python src/backend/run.py > /var/log/procare-backend.log 2>&1 &

# 6. Start frontend (in background)
cd src/frontend && nohup npm start > /var/log/procare-frontend.log 2>&1 &
# Access POS: http://localhost:3000
```

**Initialization (First Time):**

```bash
# 1. Verify backend connected to ProCare
curl http://127.0.0.1:8000/api/health | jq '.data_backend'
# Expected: "procare"

# 2. Verify branch is set to "elsanta"
curl http://127.0.0.1:8000/api/branches | jq '.[] | select(.code == "ELSANTA")'

# 3. Load dashboard
Open browser: http://localhost:3000
# Should show KPIs for Elsanta branch only

# 4. Create test shift
Cashier opens shift: Cashier #1, $500 float
Expected: Shift opened successfully

# 5. Create test sale
POS: Scan product → Qty 2 → Payment: Cash → Process
Expected: Sale created, stock deducted

# 6. Close test shift
Cashier closes shift: Actual cash $502 (sale revenue)
Expected: Variance $2 (correct)
```

**Daily Startup (Cashiers):**

```
08:00 AM
1. Terminal boots automatically (systemd/Windows scheduler)
2. Backend + frontend start automatically
3. Open browser: http://localhost:3000
4. Dashboard loads → See yesterday's KPIs
5. Cashier logs in with credentials
6. First shift opens
→ Ready for business
```

**Daily Shutdown (End of Business):**

```
19:00 (or end of shift)
1. All cashiers close their shifts
2. Manager verifies reconciliation on dashboard
3. Dashboard → Export daily report (email to finance)
4. Terminal can shut down (services stop gracefully)
→ Data backed up automatically
```

**Troubleshooting (Elsanta):**

| Issue | Check | Fix |
|-------|-------|-----|
| "Cannot connect to ProCare" | `ping 192.168.1.10` | Network issue → contact IT |
| "Connection refused:8000" | `curl http://127.0.0.1:8000/api/health` | Backend crashed → restart |
| "Database login failed" | Check credentials in connections.json | Verify password with DBA |
| "Slow response (>5s)" | Check terminal CPU/RAM usage | Close other apps, restart |
| "Stock deduction not showing" | Refresh dashboard after sale | Should sync within 10s |

---

### Mshala Branch (ProCare Pilot + Mobile)

**Location:** [Address]  
**Manager:** [Name] — [Phone] — [Email]  
**Terminal Count:** 3–5 POS terminals  
**Mobile Devices:** 5–10 (iOS/Android)  
**Daily Revenue:** $[Amount]

#### A. POS Terminal Configuration

Same as **Elsanta** (see above).

#### B. Mobile App Deployment

**iOS:**

```bash
# 1. Development team builds signed app
cd src/mobile
flutter build ios --release

# 2. Deploy via TestFlight or direct install
# App name: "ProCare OS"
# Bundle ID: com.procarepharmacies.procare_os

# 3. Install on 5–10 devices
# Configure: Settings → API_BASE = http://192.168.1.10:8000

# 4. Employee login
Username: [Employee ID]
Password: [PIN]
Branch: Mshala
→ Tasks list displays (stocktake, order verification, returns)
```

**Android:**

```bash
# 1. Build APK
flutter build apk --release

# 2. Deploy to devices
adb install -r build/app/outputs/flutter-app/release/app-release.apk

# 3. Install on 5–10 devices
# Same login & configuration as iOS

# 4. Grant permissions (first run)
→ Camera (for barcode scanning)
→ Storage (for offline sync)
```

**Daily Mobile Operations:**

```
08:00 AM
1. Employee opens ProCare app
2. Logs in with employee ID + PIN
3. Sees tasks: "Stocktake — Aisle A–C", "Order verification — Vendor ABC", etc.

During day:
- Scan product barcode → See current stock + expiry dates
- Submit stocktake: "Aisle A: Product X is 23 units, not 25" → Recorded to ProCare
- Verify order: "Vendor ABC order received: 100 qty" → Linked to purchase order

19:00 PM (End of day)
1. Mobile app syncs final data to ProCare
2. Manager approves submitted changes
→ Stock counts updated in POS
```

**Mobile Troubleshooting:**

| Issue | Check | Fix |
|-------|-------|-----|
| "Cannot connect to API" | WiFi connected? `ping 192.168.1.10` | Restart app, check network |
| "Barcode scanner not working" | Camera permission granted? | Settings → ProCare → Allow Camera |
| "Stocktake not saving" | See "Pending" status in app | Sync manually: Settings → Sync Now |
| "Offline mode" | Network disconnected? | App will auto-sync when online |

---

## Pre-Go-Live Setup (Each Branch)

### Checklist (Print & Sign)

**Elsanta Manager: _______________________ Date: _______**

- [ ] 3–5 POS terminals networked and tested
- [ ] Backend + frontend running on each terminal
- [ ] Connections verified (ProCare Dev 192.168.1.10)
- [ ] Test sale created and reconciled
- [ ] 3–5 cashiers trained on new POS
- [ ] Daily reconciliation procedure posted
- [ ] Escalation contacts posted
- [ ] Backup/rollback procedure understood

**Mshala Manager: _______________________ Date: _______**

- [ ] 3–5 POS terminals networked and tested
- [ ] Backend + frontend running on each terminal
- [ ] Connections verified (ProCare Dev 192.168.1.10)
- [ ] Test sale created and reconciled
- [ ] 5–10 mobile devices deployed and tested
- [ ] 5–10 employees trained on mobile app
- [ ] Barcode scanning working
- [ ] 3–5 cashiers trained on new POS
- [ ] Daily reconciliation procedure posted
- [ ] Escalation contacts posted
- [ ] Backup/rollback procedure understood

**Main Manager: _______________________ Date: _______**

- [ ] No changes to current eStock setup
- [ ] Aware of parallel testing (providing control data)
- [ ] Daily comparison process understood
- [ ] Escalation contacts known

---

## Daily Reconciliation Flow

### 07:00 AM (Before Opening)

**All branches:**
```bash
# 1. System health check
curl http://192.168.1.10:8000/api/health

# 2. Database backup verification (automated)
# Status: ✅ Backup from last night completed

# 3. Load yesterday's summary
curl http://192.168.1.10:8000/api/dashboard/summary?branch=[elsanta|mshala|main]

# 4. Compare to eStock (if Elsanta/Mshala)
# ProCare sales == eStock sales ± 0.1%
```

### 19:30 (Evening Reconciliation)

**Elsanta Manager:**
```bash
# 1. All cashier shifts closed
curl http://192.168.1.10:8000/api/alerts/debtors  # Check credit holds

# 2. Export daily report
Dashboard → Export → procare_elsanta_20260724.csv

# 3. Send to finance
Email: finance@procarepharmacies.com
Subject: "Elsanta Daily Report — July 24"
Attachment: procare_elsanta_20260724.csv

# 4. Check for alerts
curl http://192.168.1.10:8000/api/alerts/low-stock?branch=elsanta
curl http://192.168.1.10:8000/api/alerts/expiry?branch=elsanta
→ If critical: Message manager + finance
```

**Mshala Manager:**
```bash
# Same as Elsanta, plus:

# 5. Mobile app sync verification
# Check: All employee submissions synced to ProCare
curl http://192.168.1.10:8000/api/etl/status | jq '.last_mobile_sync'

# 6. Stocktake reconciliation
# Manager reviews: Submitted counts vs. system counts
# Approve or dispute each discrepancy
```

**Main Manager:**
```bash
# 1. eStock daily summary captured
# 2. Share with finance for comparison against Elsanta/Mshala
# 3. No data entry to ProCare (read-only snapshot only)
```

**Finance (EOD):**
```bash
# 1. Receive reports from all three branches
# 2. Compare:
#    - Elsanta (ProCare) vs. Main (eStock)
#    - Mshala (ProCare) vs. Main (eStock)
# 3. Reconcile ledger entries
# 4. Log any discrepancies in INCIDENTS.md
# 5. Weekly report to CFO
```

---

## Week 1 Critical Hours (08:00–12:00)

**Branch Managers:** Stay on-site for first 4 hours

**On-call Dev Team:** Monitor backend logs in real-time

**Monitoring:**
```bash
# Terminal 1: Backend logs
tail -f /var/log/procare-backend.log

# Terminal 2: API health (every 5 min)
watch -n 300 'curl -s http://192.168.1.10:8000/api/health | jq .'

# Terminal 3: Branch dashboard (every 15 min)
watch -n 900 'curl -s http://192.168.1.10:8000/api/dashboard/summary?branch=elsanta'
```

**Alert thresholds (escalate immediately):**
- API error (5xx): > 5 in 5 min → call dev lead
- Database unreachable: → call DBA
- Cashier shift fails to open/close: → call dev lead
- Stock shows negative: → call DBA (data corruption)
- Customer balance error: → call finance lead

---

## Post-Pilot Transition (Week 12 → Week 13)

Once Main branch cutover is approved:

### Elsanta → Production
- Configuration remains same (ProCare 192.168.1.10)
- Mobile app → Production mode
- Daily backups continue
- SLA: 99% uptime

### Mshala → Production
- Same as Elsanta

### Main → Cutover
- See [`docs/06-roadmap.md`](06-roadmap.md) Phase 3 for cutover procedure

---

**Questions? Contact:** [Dev Lead Phone]  
**Emergencies (24/7):** [On-Call Number]
