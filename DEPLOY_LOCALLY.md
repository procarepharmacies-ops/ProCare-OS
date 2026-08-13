# ProCare OS — Local Deployment on Pharmacy PC

**Status:** Configuration files created with your credentials.
- ✅ `config/connections.json` — Configured with Elsanta/Mashala eStock + ProCare database
- ✅ `.env` — Production settings (AUTH_ENABLED=true, SYNC_ENABLED=true, SYNC_INTERVAL_SECONDS=30)

## Deploy on Your Pharmacy PC/Server

You MUST deploy from the **pharmacy's local network** where SQL Server is accessible.

### Option 1: Windows Batch Script (Recommended for Pharmacy PC)

Create file: `C:\ProCare\start-production.bat`

```batch
@echo off
REM ProCare OS Production Startup
REM Run from the ProCare repository directory

cd /d %~dp0
if not exist "config\connections.json" (
    echo ERROR: config\connections.json not found
    echo Copy from the cloud deployment and fill with real credentials
    pause
    exit /b 1
)

echo Starting ProCare OS Production Backend...
cd src\backend
python run.py
```

### Option 2: Docker Compose (Cleanest)

```bash
cd /home/user/ProCare-OS
docker compose build --no-cache
docker compose up -d
```

**Verify deployment:**
```bash
curl http://localhost:8000/api/health
curl http://localhost:3000/api/health
```

### Option 3: Python Direct (Development Mode)

```bash
cd src/backend
pip install -r requirements.txt
python run.py
```

---

## What Happens on First Run

1. **Database initialization** (~10 seconds)
   - Creates ProCare database tables (idempotent)
   - Ensures all columns exist

2. **Seeding** (~5 seconds)
   - Creates demo branches (Elsanta, Mas-hala)
   - Creates demo users (CEO, manager, cashier)

3. **Full eStock Sync** (5-30 minutes depending on data volume)
   - Reads from Elsanta (196.202.93.37)
   - Reads from Mas-hala (192.168.1.2)
   - Imports:
     * Products (53K+)
     * Customers (5K+)
     * Sales history (412K+ on Elsanta)
     * Stock batches
     * Vendors
     * Employees

4. **Continuous Sync** (every 30 seconds)
   - Incremental syncs
   - No blocking to pharmacy operations

---

## Testing Live Features (Once Running)

### 1. Test Real Data
- Navigate to: http://localhost:3000/login
- Login as CEO (default creds from seed)
- Go to Dashboard → should show real Elsanta/Mas-hala data

### 2. Test Autopurchase & Reorder Proposals
- **Dashboard** → Decision Cards
  - Should show stockout-risk cards from real forecast
  - Click "Create PO" → creates purchase order
- **Purchasing** → PO list
  - Auto-created POs visible with forecast-driven quantities

### 3. Test Prescription Reader
- **Prescriptions** → Capture
  - Upload a prescription image
  - AI reads and suggests products
  - Add to cart → shows cross-sell suggestions
  - Complete sale → loyalty points credited

### 4. Test Forecasting
- **Analytics** → Forecast
  - Shows per-product demand forecast (30-day)
  - Stockout dates calculated
  - Risk severity (critical/warning/ok)

### 5. Test Employee Performance
- **Employees** → Performance
  - Shows per-employee sales, attachment rate, conversion %
  - Incentive points tracked
  - Leaderboard with medals (🥇🥈🥉)

### 6. Test Loyalty & Engagement
- **Customers** → Create/edit customer
  - Capture phone + birthday
  - On next sale: loyalty points earned
- **Dashboard** → Loyalty Tiers
  - Track tier progression (Standard → Silver → Gold → VIP)

### 7. Test Marketing & Social
- **Marketing** → Content Calendar
  - Create post → AI copywriter generates bilingual copy
  - Schedule across FB/IG/WhatsApp
- **Promo Codes**
  - Create % or fixed-EGP discount codes
  - Redeem at POS

---

## Configuration on Pharmacy PC

Your `config/connections.json` is configured with:

**Elsanta eStock (WAN 196.202.93.37)**
```json
{
  "username": "AHMEDPHARM22",
  "password": "Egstart211078$",
  "store_branch_map": {"1": "ELSANTA", "2": "ELSANTA"}
}
```

**Mas-hala eStock (LAN 192.168.1.2)**
```json
{
  "username": "ahmedibrahim",
  "password": "Egstart211078$",
  "store_branch_map": {"1": "MASHALA"}
}
```

**ProCare Database (192.168.1.2)**
```json
{
  "username": "procare_app",
  "password": "Procare@2026",
  "database": "ProCare"
}
```

---

## Troubleshooting

### "SSL routines::unsupported protocol" / health says `sqlite` on a 2008 host

Driver 18 (OpenSSL 3) refuses the TLS 1.0 handshake that SQL Server 2008 needs,
so both the eStock read and ProCare's own co-hosted DB fail to connect.
`TrustServerCertificate=yes` does not fix it — see
`deploy/SQL-SERVER-2008-ELSANTA.md` §1.1 for the per-platform fix. Docker
deployments (Option 2) already carry the patch.

### "Cannot connect to eStock"
- Verify network: `ping 196.202.93.37` (Elsanta) and `ping 192.168.1.2` (Mas-hala)
- Verify credentials in `config/connections.json`
- Check SQL Server is running: `sqlcmd -S 192.168.1.2 -U procare_app -P Procare@2026 -Q "SELECT 1"`

### "AUTH_ENABLED=true but can't login"
- Verify eStock is configured (auth auto-enables when eStock + ProCare DB both exist)
- Default CEO login created by seed (check `.local-run/backend.log`)
- Try demo password: check seed.py for defaults

### "Sync running but data not appearing"
- Check `/api/sync/status` — shows last run timestamp
- Verify `/api/health` returns `{"status": "ok"}`
- Check logs: `.local-run/backend.log` for sync errors

### "Database full (95% of 10GB)"
- Old SQL Server Express is at 10GB limit
- Archive old sales (>6 months)
- Or upgrade to SQL Server Standard (unlimited)

---

## Production Go-Live Checklist

- [ ] Backend running (http://localhost:8000/api/health returns 200)
- [ ] Frontend accessible (http://localhost:3000 loads)
- [ ] Sync status shows "running" + recent timestamp
- [ ] Dashboard displays real Elsanta/Mas-hala data
- [ ] POS search works (product autocomplete in Arabic/English)
- [ ] Dashboards load in <500ms
- [ ] Decision cards showing forecast-driven suggestions
- [ ] CEO digest WhatsApp setup (manager receives 8am summary)
- [ ] Backups automated (nightly to backup server)
- [ ] Watchdog monitoring deployed
- [ ] Staff trained on new screens
- [ ] Demo data removed (or segregated to test branch)

**Once all checked: System is LIVE and ready for production use.**

---

## Files to Deploy

Copy these from the cloud to your pharmacy PC:

1. **Full repository**: `/home/user/ProCare-OS/` → `C:\ProCare\` (Windows) or `/opt/procare/` (Linux)
2. **config/connections.json** — Already configured with your credentials
3. **.env** — Already configured for production
4. **docker-compose.yml** — For Docker deployment (if using)

**DO NOT commit credentials to git.** Both `config/connections.json` and `.env` are git-ignored (safe).

---

**Next: Copy the repository to your pharmacy server and run `python run.py` (or `docker compose up -d`).**
