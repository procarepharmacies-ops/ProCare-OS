# ProCare OS — Production Deployment Checklist

**System Status:** Ready for pharmacy PC deployment (all phases complete, 474 tests passing)

---

## Pre-Deployment (Pharmacy PC Setup)

- [ ] **Windows PC Requirements**
  - [ ] Windows 7 or later
  - [ ] Python 3.11+ installed
  - [ ] Node.js 22+ installed (for frontend build)
  - [ ] SQL Server 2008 R2 Express+ (or SQLite for dev)
  - [ ] 2GB RAM minimum, 4GB recommended
  - [ ] 1GB free disk for database + app

- [ ] **Repository & Dependencies**
  - [ ] Clone: `git clone https://github.com/procarepharmacies-ops/ProCare-OS.git`
  - [ ] Backend: `cd src/backend && pip install -r requirements.txt`
  - [ ] Frontend: `cd ../frontend && npm install`

- [ ] **Configuration**
  - [ ] Copy `.env.example` → `.env` (repo root)
  - [ ] Set: `SYNC_ENABLED=0` (manual connect first)
  - [ ] Set: `AI_PROVIDER=gemini` (or hermes with OPENROUTER_API_KEY)
  - [ ] Database: SQLite (dev) or SQL Server (production)
  - [ ] Optional: `BRANCH_TIMEZONE` (default: server local)

- [ ] **Network & eStock Connection**
  - [ ] Download `deploy/ProCare-Connect-eStock.bat`
  - [ ] Fill `config/connections.json` with read-only eStock login
  - [ ] Test: Run the `.bat` script → "Connection OK" message
  - [ ] Verify: First sync completes (products, stock, customers)

---

## Startup Verification

- [ ] **Backend Start**
  ```bash
  cd src/backend && python run.py
  # Expected: "Uvicorn running on http://127.0.0.1:8100"
  ```

- [ ] **Frontend Start** (separate terminal)
  ```bash
  cd src/frontend && npm run dev
  # Expected: "ready - started server on 0.0.0.0:3100"
  ```

- [ ] **Health Check**
  - [ ] Open browser: `http://localhost:3000` (or pharmacy PC IP:3000)
  - [ ] Login: any test user (demo data seeded)
  - [ ] Dashboard loads, no errors in browser console

- [ ] **API Health Endpoint**
  - [ ] Visit: `http://localhost:3000/api/health`
  - [ ] Response: `{"status": "ok", "database": "sqlite|sqlserver", ...}`

---

## Functional Smoke Tests (Golden Path)

- [ ] **POS Sale**
  - [ ] Navigate to `/pos`
  - [ ] Search & add product to cart
  - [ ] Complete sale → invoice prints
  - [ ] Stock decreases correctly

- [ ] **Stocktaking (جرد)**
  - [ ] Navigate to `/stocktaking`
  - [ ] Create new count session
  - [ ] Record counts for 3-5 products
  - [ ] Post counts → stock adjusts, history logged

- [ ] **Prescriptions**
  - [ ] Navigate to `/prescriptions`
  - [ ] Add prescription (capture or paste)
  - [ ] Hand off to POS → appears in cart
  - [ ] Dispense & complete

- [ ] **Transfers**
  - [ ] Request transfer from another branch (if multi-branch)
  - [ ] Approve → stock moves
  - [ ] Receive confirmation

- [ ] **Sync Status**
  - [ ] `GET /api/sync/status` shows `running: false` (manual mode)
  - [ ] Enable continuous: set `SYNC_ENABLED=1` + restart backend
  - [ ] Status shows `running: true`, recent `last_sync_at`

---

## Bilingual & Accessibility

- [ ] **Arabic (RTL) Mode**
  - [ ] Language toggle in top-right corner
  - [ ] All text renders Arabic correctly (no broken chars)
  - [ ] Layout flips to RTL (search box moves right, nav on right)

- [ ] **Keyboard Navigation**
  - [ ] Tab through POS cart, can add/remove items
  - [ ] Enter completes sale from search box

- [ ] **Mobile/PWA** (Optional)
  - [ ] Open on mobile: pharmacy URL
  - [ ] Install prompt appears → "Add to Home Screen"
  - [ ] Works offline (cached assets load)

---

## Performance & Monitoring

- [ ] **Response Times**
  - [ ] Dashboard loads <500ms
  - [ ] POS search <200ms
  - [ ] Sale completion <1s

- [ ] **Database Health** (`GET /api/automation/db-health`)
  ```json
  {
    "severity": "ok",
    "db": { "data_mb": 50, "log_mb": 10, "pct_of_cap": 1 },
    "disk": { "free_gb": 100, "free_pct": 80 }
  }
  ```
  - [ ] Severity: "ok" or "info" (not "warning"/"critical")
  - [ ] Disk free >10GB
  - [ ] DB size <8GB (leaves 2GB buffer before 10GB cap)

- [ ] **Log Monitoring**
  - [ ] `.local-run/backend.log` exists, recent timestamps
  - [ ] No ERROR or CRITICAL lines (except startup)
  - [ ] Sync runs logged every 30s (if SYNC_ENABLED)

---

## Post-Deployment (Ongoing)

- [ ] **Watchdog Setup** (Unattended Server, Optional)
  ```bash
  # Copy to Windows Task Scheduler or Linux cron
  deploy/procare-watchdog.bat  # Windows
  deploy/procare-watchdog.sh   # Linux
  ```
  - Runs every 60s, restarts API if health check fails
  - OOM protection, SQL Server fallback check

- [ ] **Continuous Sync**
  - [ ] Set `SYNC_ENABLED=1` in `.env`
  - [ ] Set `SYNC_INTERVAL_SECONDS=30` (default)
  - [ ] Verify sync thread doesn't block sales
  - [ ] Monitor `GET /api/sync/status` for errors

- [ ] **Backup Strategy**
  - [ ] SQLite: daily copy of `.db` file to external drive
  - [ ] SQL Server: use built-in backup tool (hourly snapshots)
  - [ ] Test restore before deploying to production

- [ ] **Alert Subscriptions**
  - [ ] WhatsApp manager phone configured (`.env: MANAGER_PHONE`)
  - [ ] 8am CEO digest enabled (auto-sends daily summary)
  - [ ] Critical alerts go to manager (sync failures, DB health)

---

## Known Limitations & Workarounds

| Issue | Workaround | Priority |
|-------|-----------|----------|
| Employee daily time (92 rows) | Not mirrored — low value, attendance-only | Phase 8 |
| Cheque-due alerts | Both servers have 0 Checks rows — build when needed | Phase 8 |
| Cash_disk_close cross-branch | Fixed in PR #67 (v→ correct branch attribution) | ✅ |
| EMP_CONTROL permissions | 198 undocumented columns — needs eStock vendor docs | Phase 8 |

---

## Test Results Before Deployment

**Last Run:** `2026-08-23`
- Backend: ✅ Imports OK, 6 routes registered
- Frontend: ✅ Build clean, 26 pages prerendered, 102 kB JS
- Database: ✅ Schema created (seeded demo data)
- Tests: ✅ 474 passed, 0 failed, no regressions
- APIs: ✅ All endpoints respond

---

## Troubleshooting

**Backend won't start:**
- Check Python 3.11+ installed: `python --version`
- Check dependencies: `pip install -r requirements.txt`
- Check `.env` DB connection string (SQLite path or SQL Server server\instance)

**Frontend won't build:**
- Check Node 22+: `node --version`
- Clear cache: `rm -rf .next node_modules && npm install`

**Sync fails to connect eStock:**
- Verify read-only login in `config/connections.json`
- Run `deploy/ProCare-Connect-eStock.bat` to test
- Check logs: `.local-run/backend.log`

**Sales don't decrease stock:**
- Verify `FEFO_ENABLED=1` (default)
- Check stock_batches table has records (sync ran)
- Test on a product with >1 batch on hand

**Alerts not sending:**
- Verify `MANAGER_PHONE=+20...` in `.env` (WhatsApp format)
- Check WhatsApp credentials / API key configured
- Manually trigger: `GET /api/automation/db-health` with warning state

---

**Deployment sign-off:** ______________________ (Pharmacy Manager)
**Date:** ____________________
