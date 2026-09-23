# ProCare OS — Environment Configuration Guide

**Version:** 1.0  
**Date:** 2026-09-12

---

## Quick Reference

The `.env` file (git-ignored) controls all ProCare runtime behavior. Copy `.env.example` to `.env` and fill in values as needed.

```bash
cp .env.example .env
# Edit .env with your credentials and settings
```

---

## Section 1: AI Provider Configuration

Choose ONE AI provider for prescription reading and insights. All default to **free tiers**.

### Option A: Gemini Pro (Recommended — Google)

1. Go to https://aistudio.google.com/apikey
2. Click **Create API Key in new project**
3. Copy the key

```bash
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
# AI_MODEL=gemini-2.5-pro  # (optional; auto-selected if unset)
```

### Option B: Hermes (Nous Research via OpenRouter)

1. Go to https://openrouter.ai/keys
2. Create a new key
3. Copy the key

```bash
AI_PROVIDER=hermes
OPENROUTER_API_KEY=sk-or-v1-...
```

### Option C: Claude API (Paid)

1. Go to https://console.anthropic.com/account/keys
2. Create an API key
3. Copy the key

```bash
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### Option D: No AI (Offline Keyword Router)

Leave all keys blank; pharmacy works with keyword-based suggestions only.

```bash
# No AI_PROVIDER or key = offline mode
```

---

## Section 2: eStock Continuous Sync

Mirror the real eStock database in the background.

```bash
SYNC_ENABLED=1                    # 1 = enable background sync (default 0)
SYNC_INTERVAL_SECONDS=30          # Sync every 30 seconds (adjust as needed)
```

**Setup:**
1. Fill in `config/connections.json` with your **read-only** eStock credentials
2. Run the Windows batch script: `deploy/ProCare-Connect-eStock.bat`
3. The script tests the connection, then enables SYNC_ENABLED automatically

---

## Section 3: Automation & Scheduler Configuration

**CRITICAL FOR WEEKLY SCHEDULE:** These settings enable automated staff reminders and daily operations.

```bash
AUTOMATION_ENABLED=1                    # 1 = enable all scheduler jobs
BRANCH_TIMEZONE=Africa/Cairo            # IANA timezone name (for cron schedules)
DB_SIZE_CAP_MB=10240                    # Alert threshold for SQL Server Express
```

### Timezone Examples

- Egypt: `Africa/Cairo` (UTC+2)
- Syria: `Asia/Damascus` (UTC+3)
- Saudi Arabia: `Asia/Riyadh` (UTC+3)
- London: `Europe/London` (UTC+0 / BST)
- Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

### Automated Jobs (when AUTOMATION_ENABLED=1)

| Job | Frequency | Time | Action |
|-----|-----------|------|--------|
| `shift_reminder_daily` | Every day | 9:00 PM | Send tomorrow's shift schedule to staff group |
| `weekly_schedule_share` | Saturday only | 8:00 AM | Send full weekly schedule to all staff |
| `um_adham_checklist` | Sat-Thu | 10:00 AM | Send cleaning checklist to Um Adham (أم أدهم) |
| `ceo_digest` | Every day | 8:00 AM | Send CEO manager alert (if configured) |
| `db_health` | Hourly | Top of hour | Monitor database + disk space |

---

## Section 4: WhatsApp Automation Configuration

**Two options:** direct Cloud API or click-to-chat (no credentials needed).

### Option A: WhatsApp Cloud API (Production-Recommended)

**Prerequisites:**
1. Meta Business Manager account (https://business.facebook.com)
2. WhatsApp Business Account created in Business Manager
3. System User with `whatsapp_business_messaging` permission

**Steps:**

1. **Get your Phone Number ID:**
   - In Business Manager → WhatsApp → Phone Numbers
   - Copy the Phone Number ID (a 15-16 digit number)

2. **Create a System User Access Token:**
   - Settings → Users → System Users
   - Create a new System User (e.g., "ProCare Automation")
   - Generate an access token with `whatsapp_business_messaging` permission
   - Copy the token (it won't be shown again; save it securely)

3. **Fill in `.env`:**

```bash
AUTOMATION_ENABLED=1
BRANCH_TIMEZONE=Africa/Cairo
WHATSAPP_TOKEN=your_access_token_here
WHATSAPP_PHONE_ID=your_phone_number_id_here
MANAGER_PHONE=+201012345678          # Optional: for manager alerts (international format)
```

**Validation:**

```bash
curl -X GET "https://graph.facebook.com/v20.0/{PHONE_ID}" \
  -H "Authorization: Bearer {TOKEN}"

# Should return 200 with phone number details
```

### Option B: Click-to-Chat Fallback (No Setup Required)

Leave `WHATSAPP_TOKEN` and `WHATSAPP_PHONE_ID` empty:

```bash
AUTOMATION_ENABLED=1
BRANCH_TIMEZONE=Africa/Cairo
# WHATSAPP_TOKEN=              # (leave empty)
# WHATSAPP_PHONE_ID=            # (leave empty)
```

**Result:** System generates WhatsApp links (`wa.me/...`) that staff can click to open WhatsApp with pre-filled messages. **Works immediately, no API key needed.**

---

## Section 5: Firecrawl (Optional Web Scraping)

For advanced product data scraping (future phase).

```bash
# FIRECRAWL_API_KEY=fc-xxxxxxxx
# FIRECRAWL_NO_TELEMETRY=1
```

---

## Complete `.env` Example

```bash
# --- AI provider ---
AI_PROVIDER=gemini
GEMINI_API_KEY=AIzaSyD...

# --- eStock sync ---
SYNC_ENABLED=1
SYNC_INTERVAL_SECONDS=30

# --- Automation (REQUIRED for weekly schedule) ---
AUTOMATION_ENABLED=1
BRANCH_TIMEZONE=Africa/Cairo
DB_SIZE_CAP_MB=10240

# --- WhatsApp (option A: Cloud API, or leave empty for click-to-chat) ---
WHATSAPP_TOKEN=your_access_token
WHATSAPP_PHONE_ID=1234567890123456
MANAGER_PHONE=+201012345678
```

---

## Deployment Checklist

Before deploying to production:

- [ ] `.env` file created (copy from `.env.example`)
- [ ] AI provider credentials filled in (or intentionally left blank)
- [ ] SYNC_ENABLED and SYNC_INTERVAL_SECONDS set (or leave 0 if no eStock)
- [ ] AUTOMATION_ENABLED=1
- [ ] BRANCH_TIMEZONE set to your pharmacy location
- [ ] WHATSAPP credentials filled in (or left empty for click-to-chat)
- [ ] Backend starts cleanly: `python run.py` → no errors in logs
- [ ] Health check: `curl http://localhost:8100/api/health` → `{"status": "ok"}`
- [ ] Scheduler running: `curl http://localhost:8100/api/automation/scheduler-status` → shows all jobs
- [ ] Test a schedule notification manually (see `SCHEDULE-DEPLOYMENT-GUIDE.md`)

---

## Troubleshooting

**Problem:** Backend starts but automations aren't running

**Check:**
```bash
curl http://localhost:8100/api/automation/scheduler-status
# Should show: {"enabled": true, "jobs": [{"id": "shift_reminder_daily", ...}]}
```

**Likely cause:** `AUTOMATION_ENABLED=0` or not set. Set it to `1`.

---

**Problem:** WhatsApp messages not sending

**Check:**
```bash
curl -X GET "https://graph.facebook.com/v20.0/{PHONE_ID}" \
  -H "Authorization: Bearer {TOKEN}"
# If 400 or 401: token or phone ID is invalid

# Check logs:
tail -f .local-run/backend.log | grep -i whatsapp
```

**Likely cause:** Expired token or wrong phone ID. Regenerate in Business Manager.

---

**Problem:** Cron jobs firing at wrong times

**Check:**
```bash
echo $BRANCH_TIMEZONE
# Should print your IANA timezone (e.g., Africa/Cairo)
# If empty: jobs fire in server-local time
```

**Likely cause:** BRANCH_TIMEZONE not set. Add it to `.env`.

---

## References

- **Schedule deployment:** `deploy/SCHEDULE-DEPLOYMENT-GUIDE.md`
- **Attendance policy:** `operations/sop-attendance.md`
- **Weekly schedule:** `operations/weekly-schedule.md`
- **eStock connectivity:** `config/connections.example.json`
- **WhatsApp messages:** `src/backend/app/services/whatsapp.py`
- **Scheduler jobs:** `src/backend/app/services/scheduler.py`

---

*Last updated: 2026-09-12*  
*Owned by: DevOps / Pharmacy Manager*
