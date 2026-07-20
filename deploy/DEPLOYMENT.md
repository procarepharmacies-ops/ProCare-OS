# ProCare OS - Deployment Guide

## Option 1: Pharmacy PC (Windows) — PRIMARY ⭐

**This is the recommended deployment for the pharmacy location.**

### Prerequisites
- Windows 10/11
- Git installed
- Node.js 22+ (`node --version`)
- Python 3.11+ (`python --version`)
- Access to eStock database (SQL Server at 192.168.1.2)

### First-Time Setup

```powershell
cd C:\Users\ahmed\ProCare-OS
git clone https://github.com/procarepharmacies-ops/ProCare-OS.git .

# Configure eStock connection
copy config\connections.example.json config\connections.json
# Edit config\connections.json with your eStock credentials (read-only login)

# Backend setup
cd src\backend
python -m pip install -r requirements.txt
python run.py
# Listen on http://localhost:8000

# Frontend setup (in another terminal)
cd src\frontend
npm install
npm run dev
# Navigate to http://localhost:3000
```

### Daily Startup

```powershell
# Terminal 1: Backend
cd C:\Users\ahmed\ProCare-OS\src\backend
python run.py

# Terminal 2: Frontend
cd C:\Users\ahmed\ProCare-OS\src\frontend
npm run dev
```

### Production Build (Windows PC)

```powershell
cd C:\Users\ahmed\ProCare-OS
git pull origin main

# Backend: production mode
cd src\backend
python run.py  # Uses .env settings

# Frontend: optimized build
cd ..\frontend
npm run build
npm start  # Runs on :3000 production
```

### eStock Continuous Sync

**One-time setup:**
```powershell
cd C:\Users\ahmed\ProCare-OS
deploy\ProCare-Connect-eStock.bat
```

This script:
1. Validates eStock credentials (read-only login)
2. Runs a full historical load
3. Enables continuous sync (configurable interval)
4. Sets up daily pre-backup snapshot

---

## Option 2: Docker Compose (Linux/Mac/Cloud)

**For centralized deployment or cloud hosting.**

### Prerequisites
- Docker & Docker Compose installed
- SQL Server accessible (or use docker image)
- 2GB+ disk space

### Quick Start

```bash
docker compose up -d --build
# UI: http://localhost:3000
# API: http://localhost:3000/api (proxied)
# Backend health: http://localhost:8000/health
```

### Environment Configuration

Create `.env` in repo root:
```bash
# Backend
SYNC_ENABLED=1
SYNC_INTERVAL_SECONDS=30
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-...
DB_ENGINE=sqlite  # or "sqlserver" for production

# eStock mirror (read-only)
ESTOCK_HOST=192.168.1.2
ESTOCK_DB=stock
ESTOCK_USER=readonly_user
ESTOCK_PASSWORD=password

# WhatsApp (optional)
WHATSAPP_ENABLED=1
WHATSAPP_TOKEN=
WHATSAPP_PHONE_ID=

# Pharmacy PC defaults
DEFAULT_LANGUAGE=ar
DEFAULT_THEME=dark
```

### Persistent Data

```bash
# Data volumes are created automatically:
# - procare_db: SQLite database (dev) or SQL Server backups
# - procare_logs: Backend/frontend logs

# Manual backup:
docker compose exec backend cp procare.db /backup/procare-$(date +%Y%m%d).db
```

---

## Option 3: Cloudflare Pages (Optional CDN)

**For optional worldwide CDN caching and static site hosting.**

### Setup

1. **Authenticate with Cloudflare:**
   ```bash
   npm install -g wrangler
   wrangler login
   ```

2. **Configure `wrangler.toml`:**
   - Set your Cloudflare Account ID
   - Configure KV namespace for caching (optional)
   - Update API_BASE to point to your backend

3. **Deploy frontend:**
   ```bash
   npm run build
   wrangler pages deploy dist/
   ```

4. **Result:**
   - Frontend cached globally on Cloudflare edge
   - API requests still route to your backend (http://localhost:8000 or cloud VM)
   - No pharmacy data leaves your infrastructure

### Cloudflare Workers (Optional API Proxy)

For API caching at the edge:
```bash
wrangler deploy --env production
```

This adds optional:
- Request caching (products, reports, health checks)
- Request deduplication
- Rate limiting per IP
- CDN failover

**Note:** All sensitive operations (sales, transfers, auth) bypass cache and go directly to backend.

---

## Monitoring & Maintenance

### Health Check Endpoint

```bash
curl http://localhost:3000/api/health
```

Response shows:
- Sync status (enabled/disabled, last run)
- AI assistant configuration
- Database connection
- eStock mirror connection

### Logs

**Backend:**
```bash
tail -f .local-run/backend.log
```

**Frontend:**
```bash
Browser console: F12 → Console tab
```

**Docker:**
```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### Backup Management

**Manual backup:**
```bash
POST /api/backup  # Triggers immediate backup
GET /api/backup/list  # Lists recent backups
```

**Auto-backup schedule:**
- Startup: one backup created
- Pre-sync: one backup if sync will wipe data
- Daily: if not backed up in last 24 hours
- Keep: last 30 backups only

### Performance Tuning

For high-volume days:

**Backend:**
```python
# src/backend/app/config.py
DB_POOL_SIZE = 20  # Increase from 10
DB_MAX_OVERFLOW = 40
```

**Frontend:**
```javascript
// src/frontend/next.config.mjs
module.exports = {
  swcMinify: true,
  compress: true,
}
```

---

## Troubleshooting

### Backend won't start

```bash
# Check logs
tail -f .local-run/backend.log

# Verify eStock connection
python -c "from app.services.etl import health_check; print(health_check())"

# Reset database (dev only)
rm procare.db
python run.py  # Reseed
```

### Frontend build fails

```bash
rm -rf src/frontend/node_modules .next
npm install
npm run build
```

### Sync not running

```bash
# Check sync status
curl http://localhost:8000/api/sync/status

# Manual full load
curl -X POST http://localhost:8000/api/etl/run

# Verify eStock credentials
cat config/connections.json  # Check read-only login
```

### High memory usage

```bash
# Check process
ps aux | grep python  # Backend memory
ps aux | grep node    # Frontend memory

# Reduce DB connections in development
export DB_POOL_SIZE=5
python run.py
```

---

## Security Checklist

- [ ] `.env` is git-ignored (contains API keys)
- [ ] eStock login is read-only (never write)
- [ ] Cloudflare API key not in code
- [ ] WhatsApp token rotated quarterly
- [ ] Backups stored securely (off-site for production)
- [ ] HTTPS enabled on pharmacy PC (self-signed cert okay)
- [ ] Firewall blocks external access to :8000 (frontend only)

---

## Support & Rollback

### If deployment fails

1. Check backend logs: `.local-run/backend.log`
2. Verify database: `sqlite3 procare.db ".tables"`
3. Restore from backup: `cp backup.db procare.db`
4. Restart backend: `python run.py`

### Version history

```bash
git log --oneline -10
git checkout <commit>  # Revert to stable version
```

### Emergency backup

```bash
# On pharmacy PC
copy procare.db \\network\backup\procare-$(date /T).db
# Or cloud storage
aws s3 cp procare.db s3://procare-backups/$(date +%Y%m%d).db
```

---

**Version:** 2026-07-12  
**Status:** Production Ready ✅  
**Next Review:** 2026-08-12
