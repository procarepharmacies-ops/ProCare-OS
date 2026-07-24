# Pilot Go-Live Readiness Checklist

**Document:** Print this out, have each team sign off on their section before go-live.

**Date:** ________  
**Go-Live Target:** Monday, ________ at 08:00 AM

---

## Section 1: Infrastructure (Sign-off: DevOps/DBA)

### Database
- [ ] ProCare database created on 192.168.1.10
- [ ] Schema applied (20+ tables verified)
- [ ] Logins created: `procare_readonly`, `procare_app`
- [ ] eStock mirrored completely (products, customers, stock, sales)
- [ ] Reconciliation passed (all checks: sales, stock value, balances, payables)
- [ ] Full backup completed and verified
- [ ] Daily backup scheduled
- [ ] Test restore from backup successful

### Network
- [ ] Network path 192.168.1.10:1433 reachable from Elsanta terminals
- [ ] Network path 192.168.1.10:1433 reachable from Mshala terminals
- [ ] Firewall: Port 1433 (SQL Server) open and tested
- [ ] Firewall: Port 8000 (backend API) open if backend is remote
- [ ] Latency test: < 100ms from terminals to ProCare Dev
- [ ] ODBC driver "18 for SQL Server" installed on all terminals

### Backups
- [ ] ProCare full backup location confirmed: __________
- [ ] Daily automated backup job configured: ✅ / ❌
- [ ] Backup restore test completed and logged
- [ ] Backup retention policy: __________ days

**Signed off by:** _________________ Date: _______

---

## Section 2: Application & Code (Sign-off: Dev Lead)

### Backend
- [ ] Phase 2 POS code deployed to production/staging
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Environment variables set: `ANTHROPIC_API_KEY`, `DATABASE_URL` (if used)
- [ ] API endpoints available:
  - [ ] GET /api/health
  - [ ] POST /api/pos/sale
  - [ ] POST /api/pos/return
  - [ ] POST /api/pos/shift/open
  - [ ] POST /api/pos/shift/close
  - [ ] GET /api/alerts/expiry
  - [ ] GET /api/alerts/low-stock
  - [ ] GET /api/etl/reconcile
- [ ] Backend service runs on startup (systemd/Windows Service configured)
- [ ] Backend logs to: __________
- [ ] Error alerting configured (Slack/email on 5xx errors)

### Frontend (POS)
- [ ] Next.js built and deployed to Elsanta/Mshala terminals
- [ ] Environment configured: `NEXT_PUBLIC_API_BASE=http://192.168.1.10:8000`
- [ ] POS UI loads without errors
- [ ] Branch selector shows "elsanta" or "mshala" (correct branch)
- [ ] Dashboard KPIs display live data
- [ ] Connection status shows "Online"

### Mobile App (Mshala)
- [ ] iOS build compiled and deployed to TestFlight or devices
- [ ] Android build compiled and deployed to devices
- [ ] App authenticates with employee credentials
- [ ] Tasks list displays
- [ ] Barcode scanning works
- [ ] API connection shows "Online"

**Code version/commit deployed:**
- Backend: __________
- Frontend: __________
- Mobile: __________

**Signed off by:** _________________ Date: _______

---

## Section 3: Testing (Sign-off: QA/Test Lead)

### Unit Tests
- [ ] Backend tests pass: `pytest tests/test_pos_phase2.py`
  - Result: ____ passed, ____ failed
- [ ] No critical test failures
- [ ] Code coverage ≥ 80%

### Integration Tests
- [ ] Test sale: POS → Stock deduction → Ledger entry → Customer balance
  - Result: ✅ Pass / ❌ Fail
- [ ] Test return: Sale reversal → Stock restored → Credit reversed
  - Result: ✅ Pass / ❌ Fail
- [ ] Test FEFO: Oldest-expiry batches picked first
  - Result: ✅ Pass / ❌ Fail
- [ ] Test credit: Over-limit customer blocked
  - Result: ✅ Pass / ❌ Fail
- [ ] Test shift reconciliation: Cash variance < 1%
  - Result: ✅ Pass / ❌ Fail

### Performance Tests
- [ ] API response time < 2s (p99): ✅ Pass / ❌ Fail
  - Measured: ____ ms (p99)
- [ ] Database query time < 1s (p99): ✅ Pass / ❌ Fail
- [ ] Concurrent users ≥ 5 per branch: ✅ Pass / ❌ Fail

### Smoke Test (Day-Before)
- [ ] Create test sale on Elsanta terminal: ✅ Success / ❌ Failed
- [ ] Verify stock deducted on ProCare: ✅ Yes / ❌ No
- [ ] Mobile app: Scan barcode on Mshala: ✅ Works / ❌ Failed
- [ ] Dashboard: Refresh and see live data: ✅ Yes / ❌ No

**Test environment:**
- Database: __________ (shadow/staging/prod)
- Data volume: __________ sales, __________ products

**Signed off by:** _________________ Date: _______

---

## Section 4: Training & Documentation (Sign-off: Operations Lead)

### Cashier Training
- [ ] Elsanta team trained (30 min session completed)
  - Attendees: __________, __________, __________
  - Date/Time: __________
- [ ] Mshala team trained (30 min session completed)
  - Attendees: __________, __________, __________
  - Date/Time: __________
- [ ] Managers briefed on pilot process and escalation
- [ ] Training materials (POS guide, troubleshooting) printed and posted

### Documentation
- [ ] Daily reconciliation procedure documented and posted
- [ ] Escalation contacts posted at each terminal
- [ ] Troubleshooting guide available (online + printed)
- [ ] Incident log template ready
- [ ] Rollback procedure documented and tested

### Contingency
- [ ] Rollback to eStock tested and verified
- [ ] Rollback procedure time estimate: __________ min
- [ ] Communication template for customers (if downtime)
- [ ] Manual workaround documented (if ProCare unavailable)

**Signed off by:** _________________ Date: _______

---

## Section 5: Monitoring & Alerts (Sign-off: DevOps)

### Monitoring Setup
- [ ] Backend health check: `curl http://192.168.1.10:8000/api/health` runs every 5 min
- [ ] Database health check: `SELECT @@VERSION` runs every 10 min
- [ ] Dashboard live at: __________
- [ ] Metrics exported to Grafana (if used)

### Alerting
- [ ] Slack channel created: __________ (for real-time alerts)
- [ ] Email alerts configured: __________
- [ ] Alert on:
  - [ ] API 5xx error (threshold: >5 in 5 min)
  - [ ] Database connection failed
  - [ ] Response time > 5s (p99)
  - [ ] Disk space < 10% available
  - [ ] Backup failed

### On-Call Schedule (Week 1)
- Monday: __________
- Tuesday: __________
- Wednesday: __________
- Thursday: __________
- Friday: __________

**Contact for critical issue (24/7):** __________

**Signed off by:** _________________ Date: _______

---

## Section 6: Finance & Audit (Sign-off: Finance Controller)

### Data Integrity
- [ ] Pre-pilot eStock snapshot captured (sales, stock, balances)
- [ ] Daily reconciliation process reviewed and approved
- [ ] General ledger: ProCare balances match eStock (to the penny)
- [ ] Customer ledger: ProCare balances match eStock (to the penny)
- [ ] Audit trail: All POS transactions logged with timestamp, cashier, customer

### Controls
- [ ] Customer credit limit enforced (no sales over limit)
- [ ] Cash/card payment split tracked correctly
- [ ] Returns create ledger reversal (no revenue loss)
- [ ] Discounts (if any) logged separately
- [ ] End-of-day reconciliation procedure approved

### Sign-Off Authority
- [ ] Finance controller approves go-live: ✅ Yes / ❌ No (see notes)
- [ ] Audit ready to verify pilot week 1 data: ✅ Yes / ❌ No

**Notes:**
________________________________________________________________________

**Signed off by:** _________________ Date: _______

---

## Final Go-Live Gate

### All Sections Complete?
- [ ] Infrastructure ✅
- [ ] Application & Code ✅
- [ ] Testing ✅
- [ ] Training & Documentation ✅
- [ ] Monitoring & Alerts ✅
- [ ] Finance & Audit ✅

### Executive Sign-Off

**Can we proceed with go-live on Monday, ________ at 08:00 AM?**

- **Dev Lead:** ✅ Yes / ❌ No  
  Signature: _________________ Date: _______

- **Operations Lead:** ✅ Yes / ❌ No  
  Signature: _________________ Date: _______

- **Finance Controller:** ✅ Yes / ❌ No  
  Signature: _________________ Date: _______

---

## If Any Section is ❌ (Not Ready)

**Do NOT proceed with go-live.**

1. Document which sections failed
2. Identify blockers
3. Create action items with owners and due dates
4. Reschedule go-live for next week
5. Update this checklist and re-run approvals

**Blockers identified:**
1. ________________________________________________________________________
2. ________________________________________________________________________
3. ________________________________________________________________________

**Rescheduled go-live date:** __________

---

**Print this document, fill it out completely, have all sections signed, and store in project archives.**

**On Monday morning at 07:30 AM, verify all boxes are checked. If any are not, STOP and do not proceed.**
