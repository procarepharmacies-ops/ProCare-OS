# Weekly Staff Schedule — Deployment Guide

**Version:** 1.0  
**Date:** 2026-09-12  
**Status:** Ready for Production Deployment

---

## Overview

The ProCare weekly staff schedule has been redesigned for peak-hour coverage optimization, government work accommodation, and cross-branch seamless coverage. This guide covers:

1. **One-time initial distribution** to all staff
2. **Automated recurring reminders** configured in the scheduler
3. **PDF document generation** for printing and archival
4. **WhatsApp Cloud API setup** (optional; click-to-chat fallback works without it)

---

## Phase 1: Environment Setup

### Option A: WhatsApp Cloud API (Recommended for Production)

To enable direct WhatsApp messaging, configure these environment variables in `.env`:

```bash
# WhatsApp Business Account credentials (from Meta Business Manager)
WHATSAPP_TOKEN=your_meta_access_token_here
WHATSAPP_PHONE_ID=your_phone_number_id_here

# Optional: Branch timezone for cron jobs (default: server local time)
BRANCH_TIMEZONE="Africa/Cairo"

# Automation enable flag (default: 0)
AUTOMATION_ENABLED=1
```

**Validation:**
```bash
curl -X GET "https://graph.facebook.com/v20.0/{PHONE_ID}" \
  -H "Authorization: Bearer {TOKEN}"
# Should return 200 with phone number details
```

### Option B: Click-to-Chat Fallback

Without credentials, the system generates WhatsApp links (`wa.me/...`) that staff can click to open WhatsApp with pre-filled messages. **No additional setup needed** — this works immediately.

---

## Phase 2: Initial Distribution (One-Time)

### 2.1 Generate PDFs

**Weekly Schedule (for all staff):**
```bash
# Open in browser:
./docs/ProCare-Weekly-Schedule-Branded.html

# Print to PDF (Ctrl+P / Cmd+P → "Save as PDF")
# Filename: ProCare_Weekly_Schedule_[Date].pdf
```

**Um Adham Daily Checklist (for cleaning staff):**
```bash
# Open in browser:
./docs/Um-Adham-Daily-Checklist.html

# Print to PDF and post at cleaning station or give to Um Adham
# Filename: Um_Adham_Daily_Checklist_[Date].pdf
```

### 2.2 Manual Send: First-Time Schedule Broadcast

**Backend API (if running locally):**
```python
from app.services import whatsapp
from app.db.models import Employee
from sqlalchemy.orm import Session

# Send weekly schedule to all staff
msg = whatsapp.weekly_schedule_message()
result = whatsapp.notify_staff_group(msg)
print(f"Sent to {result['sent']}/{result['total']} staff")
```

**Or via curl (if REST endpoint available):**
```bash
curl -X POST http://localhost:8100/api/staff/broadcast \
  -H "Content-Type: application/json" \
  -d '{
    "message_type": "weekly_schedule",
    "to": "all_staff"
  }'
```

**Or manually via WhatsApp:**
1. Copy message from `whatsapp.weekly_schedule_message()`
2. Paste into WhatsApp staff group chat
3. Each staff member can print and sign acknowledgment

---

## Phase 3: Automated Recurring Jobs

### Configured Schedules

The scheduler automatically runs these jobs (all times in branch timezone):

| Job | Frequency | Time | Description |
|-----|-----------|------|-------------|
| **shift_reminder_daily** | Every day | 9:00 PM | Send tomorrow's shift schedule to staff group |
| **weekly_schedule_share** | Saturday | 8:00 AM | Send full weekly schedule to staff group |
| **um_adham_checklist** | Sat-Thu | 10:00 AM | Send daily cleaning checklist to Um Adham |

### Monitoring

**Check job status:**
```bash
# In the backend container/process:
# GET /api/automation/scheduler-status

curl http://localhost:8100/api/automation/scheduler-status
# Returns: {
#   "enabled": true,
#   "jobs": [
#     {"id": "shift_reminder_daily", "next_run": "2026-09-12T21:00:00"},
#     {"id": "weekly_schedule_share", "next_run": "2026-09-13T08:00:00"},
#     {"id": "um_adham_checklist", "next_run": "2026-09-12T10:00:00"}
#   ]
# }
```

**View last run results:**
```bash
curl http://localhost:8100/api/automation/last-results
# Returns job execution history + success/failure status
```

**Backend logs:**
```bash
tail -f .local-run/backend.log | grep -E "shift_reminder|weekly_schedule|um_adham"
```

---

## Phase 4: Staff Acknowledgment & Sign-Off

### Method 1: Printed Schedule Forms

1. **Print** `ProCare-Weekly-Schedule-Branded.html` (5-10 copies)
2. **Post** at each branch entrance + staff room
3. **Each staff member signs** with date indicating they reviewed the schedule
4. **File** copies for payroll/attendance records

### Method 2: WhatsApp Group Confirmation

1. Manager sends schedule message to staff group
2. Each staff member replies with ✅ emoji to confirm receipt
3. Screenshot confirmation as archive

### Method 3: Digital SOP Form

If available in your system, have each staff member sign the attendance policy:
- File: `operations/sop-attendance.md` (digital) or `docs/attendance-policy-SOP-002.html` (PDF)

---

## Phase 5: Testing Checklist

Before going live:

- [ ] **Environment variables set** (WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, BRANCH_TIMEZONE)
- [ ] **Backend service running** (`python run.py` or Docker compose up)
- [ ] **Scheduler started** (check logs: "Automation scheduler started with X jobs")
- [ ] **Test initial broadcast** — send weekly schedule message manually and verify receipt
- [ ] **Test Um Adham checklist** — trigger manually and confirm format/content
- [ ] **Check automation status** — curl `/api/automation/scheduler-status` shows all jobs
- [ ] **PDFs generate** — print both HTML documents to PDF, verify formatting
- [ ] **Staff receipt** — all staff confirm via WhatsApp ✅ or printed form signature
- [ ] **Verify timezone** — cron jobs fire at expected local times (use logs)

---

## Phase 6: Day-to-Day Operations

### Daily Reminders (Automatic)

**9:00 PM daily:**
- Staff group receives tomorrow's shift schedule
- Format: Each staff member listed with their shift time
- Use case: Staff can plan evening, prepare for next day

**10:00 AM (Sat-Thu):**
- Um Adham receives her daily cleaning checklist
- Format: 3-phase plan (Morning/Midday/Evening) with task breakdown
- Use case: Structured daily workflow + task tracking

**Saturday 8:00 AM:**
- Full weekly schedule broadcast to all staff
- Format: Complete 7-day schedule for both branches
- Use case: Weekly reference + planning

### Manual Overrides

If you need to send messages outside the schedule:

**Send schedule immediately (e.g., after a change):**
```python
from app.services import whatsapp
msg = whatsapp.weekly_schedule_message()
whatsapp.notify_staff_group(msg)  # Send to all
```

**Send to a specific staff member:**
```python
from app.services import whatsapp
from app.db.models import Employee
from sqlalchemy.orm import Session

with Session(engine) as session:
    staff = session.query(Employee).filter_by(name_en="Um Adham").first()
    if staff and staff.phone:
        msg = whatsapp.um_adham_daily_checklist_message()
        whatsapp.send_text(staff.phone, msg)
```

---

## Phase 7: Troubleshooting

### Issue: Messages not sending

**Check 1: WhatsApp credentials**
```bash
echo $WHATSAPP_TOKEN
echo $WHATSAPP_PHONE_ID
# If empty, CloudAPI mode is disabled; using click-to-chat fallback
```

**Check 2: Scheduler running**
```bash
curl http://localhost:8100/api/automation/scheduler-status
# Should show: {"enabled": true, "jobs": [...]}
```

**Check 3: Phone numbers valid**
```bash
# Backend logs should show which phones failed
tail -f .local-run/backend.log | grep "normalize_phone\|send_text"
```

**Check 4: Rate limiting**
- Meta WhatsApp Cloud API has rate limits
- If many messages fail, check Meta Business Manager dashboard for account status

### Issue: Jobs not firing at expected time

**Check timezone:**
```bash
echo $BRANCH_TIMEZONE
# Should be a valid IANA timezone (e.g., "Africa/Cairo", "UTC")
```

**Check APScheduler logs:**
```bash
tail -f .local-run/backend.log | grep -i "apscheduler\|cron"
```

**Manually trigger a job (for testing):**
```python
from app.services.scheduler import (
    _run_shift_reminder,
    _run_um_adham_daily_checklist
)
_run_shift_reminder()  # Should send immediately
_run_um_adham_daily_checklist()  # Should send immediately
```

### Issue: "Um Adham not found" in logs

**Check employee records:**
```python
from app.db.models import Employee
from sqlalchemy.orm import Session

with Session(engine) as session:
    em = session.query(Employee).filter(
        Employee.name_en.ilike("%adham%")
    ).all()
    for e in em:
        print(f"{e.name_en} ({e.name_ar}): {e.phone}")
```

**If not found:** Ensure Um Adham's employee record exists with either:
- `name_en` contains "Um Adham" OR
- `name_ar` contains "أم أدهم"

---

## Phase 8: Escalation Matrix

| Issue | Owner | Resolution Time | Contact |
|-------|-------|-----------------|---------|
| Schedule changes needed | Manager | <1 hour | Update via `weekly_schedule.md` + resend broadcast |
| Um Adham not receiving checklist | HR | <2 hours | Verify phone number in employee record |
| WhatsApp Cloud API down | IT | <4 hours | Revert to click-to-chat or manual distribution |
| Timezone issues (jobs firing wrong time) | DevOps | <2 hours | Check `BRANCH_TIMEZONE` env var + APScheduler logs |

---

## Files Reference

| File | Purpose | Owner |
|------|---------|-------|
| `operations/weekly-schedule.md` | Master schedule + staff profiles | Manager |
| `docs/ProCare-Weekly-Schedule-Branded.html` | PDF-ready staff schedule | IT |
| `docs/Um-Adham-Daily-Checklist.html` | PDF-ready daily checklist | IT |
| `docs/attendance-policy-SOP-002.html` | Attendance policy PDF | HR |
| `src/backend/app/services/whatsapp.py` | WhatsApp integration | Developer |
| `src/backend/app/services/scheduler.py` | Automated jobs | Developer |
| `.env` | Configuration (git-ignored) | DevOps |

---

## Success Criteria

✅ **All staff receive initial weekly schedule** (printed or digital)  
✅ **Automated jobs run without errors** (check logs daily for first week)  
✅ **Um Adham receives daily checklist** at 10 AM (Mon-Thu)  
✅ **Staff confirm understanding** via signature or WhatsApp ✅  
✅ **No missed shifts or coverage gaps** (monitor attendance daily)  
✅ **Zero manual message sends needed** after week 1 (jobs are reliable)

---

## Rollback Plan

If automation issues occur:

1. **Disable scheduler** (set `AUTOMATION_ENABLED=0`)
2. **Revert to manual distribution** (send messages via WhatsApp group)
3. **Keep PDFs updated** for printed backup
4. **Diagnose root cause** (check logs, timezone, credentials)
5. **Re-enable once fixed**

---

**Deployment Date:** _________________  
**Approved By:** _________________  
**Tested By:** _________________  

---

*For support or updates, contact the ProCare IT team.*
