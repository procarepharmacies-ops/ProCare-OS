# Phase 3: Loyalty Tiers & CRM Engagement (برنامج الولاء)

**Objective:** Transform customer loyalty from flat-points to tiered engagement with RFM-based automation and WhatsApp campaigns.

**Timeline:** Single feature branch → tests → PR → merge

---

## Features Overview

### 1. Loyalty Tiers (برنامج الولاء المتدرج)

**Schema Changes:**
```python
# customers table additions
tier: str = "silver"  # "silver" | "gold" | "platinum" (computed monthly)
tier_spend_12m: float = 0.0  # rolling 12-month spend
birthday: date | None = None  # captured at POS opt-in
wa_opt_out: bool = False  # respect across all automation
```

**Tier Thresholds (configurable in settings):**
- Silver (فضي): 0–2,000 EGP → 1.0× points multiplier
- Gold (ذهبي): 2,000–10,000 EGP → 1.25× points multiplier
- Platinum (بلاتيني): 10,000+ EGP → 1.5× points multiplier

**Implementation:**
- `services/loyalty.py`: Add `tier_multiplier(customer) -> float` and `recompute_customer_tier(session, customer_id)` functions
- Nightly scheduler job: recompute tiers for all customers based on rolling 12-month LoyaltyTransaction sum
- POS `create_sale`: apply tier multiplier when awarding loyalty points
- Dashboard: tier distribution widget (pie chart: % silver/gold/platinum)
- Customers page: tier column + bulk edit tiers (CEO/manager only)

**Test Coverage:**
- `test_tier_multiplier_on_sale`: Sell to customer, verify points = amount × base_points × tier_multiplier
- `test_tier_promotion_workflow`: Customer crosses threshold, recompute job runs, next sale uses new multiplier
- `test_tier_demotion_on_return`: Large return lowers tier_spend_12m, tier drops, multiplier recalculates

---

### 2. RFM Segmentation (تقسيم العملاء حسب الإنفاق والتكرار)

**Segments (computed daily):**
- **VIP (محاور)**: Recency ≤30 days AND Frequency ≥12 AND Monetary ≥5,000
- **Regular (منتظم)**: Recency ≤60 AND Frequency ≥6 AND Monetary ≥1,000
- **At Risk (مهدد بالفقد)**: Recency >60 AND <180 AND Frequency ≥3
- **Dormant (خامل)**: Recency >180 OR never purchased

**Schema:**
```python
# customers table addition
rfm_segment: str = "regular"  # computed daily by scheduler
last_purchase_date: datetime | None = None  # denormalized for quick queries
```

**Implementation:**
- `services/crm.py` (new file): 
  - `compute_rfm_segments(session) -> dict[int, str]`
  - `segment_customers(session, segment: str) -> list[Customer]`
- Scheduler job: run daily, update `customers.rfm_segment` for all
- Customers page: segment filter chips with counts (VIP: 12 | Regular: 245 | At Risk: 34 | Dormant: 189)
- Drill-down: click segment chip to view customers in that segment

**Test Coverage:**
- `test_rfm_computation`: Seed customers with known purchase patterns, verify segments
- `test_segment_filters`: GET /api/crm/customers?segment=vip, verify list
- `test_rfm_updates_daily`: Run scheduler, check segment assignments changed correctly

---

### 3. WhatsApp Engagement Automation (الأتمتة عبر واتس أب)

**Campaigns (all fail-soft: WhatsApp down → log + continue):**

#### A. Tier-Up Congratulation (تهنئة بالترقية)
- **Trigger:** Scheduler finds customers promoted to higher tier
- **Message:** "تهانينا! وصلت إلى مستوى [الذهب] واحصل على نقاط أكثر 🌟"
- **Send:** Within 1 hour of tier recomputation
- **Config:** Enable/disable + template in settings

#### B. Birthday Offer (عرض عيد الميلاد)
- **Trigger:** Customer's birthday month + optional opt-in field captured at POS
- **Message:** "عيد ميلاد سعيد! استمتع بـ [خصم/نقاط إضافية] هدية منا 🎂"
- **Send:** On birthday date, or configurable offset (e.g., 3 days before)
- **Config:** Enable/disable + offer details

#### C. Points Expiry Nudge (نقاطك ستنتهي)
- **Trigger:** Loyalty points age >11 months (default, configurable)
- **Message:** "نقاطك تنتهي صلاحيتها قريباً! استخدمها الآن عند الشراء 🕒"
- **Send:** When expiry < 30 days
- **Config:** Threshold days

#### D. Win-Back Campaign (استعادة العملاء)
- **Trigger:** Dormant customers (>180 days idle)
- **Message:** "نشتاق إليك! تفضل بزيارتنا وادخل السحب على جوائز 🎁"
- **Send:** Weekly to dormant segment (throttled)
- **Config:** Enable/disable

**Implementation:**
- `services/campaigns.py` (new file):
  - `send_tier_up_notification(session, customer_id)`
  - `send_birthday_offer(session, customer_id)`
  - `send_expiry_nudge(session, customer_id)`
  - `send_winback_weekly(session)` — throttles to N messages/hour
- Scheduler: daily/weekly hooks for each campaign
- Dashboard: Campaign stats widget (sent/failed counts per campaign, success rate)
- Settings page: Campaign toggles + templates (bilingual)

**Throttling (critical for WhatsApp rate limits):**
- Max 100 messages/minute (WhatsApp business limit)
- Queue: if >100 pending, spread over time with exponential backoff on fail
- Logging: every send with timestamp, status, error (if failed)

**Test Coverage:**
- `test_tier_up_notification_sent`: Promote customer, verify WhatsApp call + mock confirmation
- `test_birthday_offer_scheduled`: Set birthday today, run scheduler, verify message queued
- `test_expiry_nudge_timing`: Set points age to 11.5 months, verify nudge triggers
- `test_winback_throttling`: Queue 200 dormant customers, verify sends spread (not all at once)

---

### 4. Campaign Manager (إدارة الحملات)

**UI Features:**
- Campaigns page (`/campaigns`):
  - Tier-up, birthday, expiry nudge, win-back toggles + template editors (bilingual AR/EN)
  - Campaign stats: sent today, success rate, failed (with retry button)
  - Manual test send: "Send to [customer #123]" for testing templates

**Schema:**
```python
# campaigns table (for tracking broadcasts, future use)
campaign_id: int
name: str  # "tier_up" | "birthday" | "expiry_nudge" | "winback"
enabled: bool
template_ar: str
template_en: str
sent_count: int
failed_count: int
last_run_at: datetime | None
```

**API Endpoints:**
- `GET /api/crm/campaigns` — list all campaigns with stats
- `POST /api/crm/campaigns/{name}/enable` — enable/disable
- `PATCH /api/crm/campaigns/{name}` — update templates
- `POST /api/crm/campaigns/{name}/test` — send test to one customer
- `GET /api/crm/campaigns/{name}/recent` — last 10 sends (timestamp, customer, status)

**Implementation:**
- `api/crm.py` (new file): campaign CRUD + send test
- Frontend: `/campaigns` page with rich template editors (TinyMCE or markdown)
- Settings: campaign toggles persist to config (or to DB, configurable)

**Test Coverage:**
- `test_campaign_toggle`: Enable campaign, verify next run picks it up
- `test_test_send`: POST /crm/campaigns/tier_up/test?customer_id=5, verify WhatsApp called
- `test_campaign_stats`: Send 50 messages (10 fail), verify stats show 40 sent + 10 failed

---

### 5. POS Integration (التكامل مع الكاشير)

**During Sale:**
- If `customer_id` not set (no loyalty account):
  - Nudge: "سجّل رقم العميل واكسب نقاط أكثر ✓"
  - Quick add: [+] opens mini-form to capture phone + (optional) birthday
  - If new customer: create, then apply loyalty points on this sale retroactively
- Loyalty display: "نقاطك: 250 | المستوى: [ذهب] (+25% نقاط)"

**During Return:**
- Clawback loyalty points (already implemented in Phase 2)
- Clawback tier contribution (if customer drops tier as a result, scheduled job recalculates)

**Implementation:**
- `api/sales.py:create_sale`: add optional `capture_customer_fields` dict (phone, birthday)
- `services/pos.py`: if customer created mid-sale, apply loyalty retroactively before commit
- Frontend `pos/page.js`: nudge UI + quick-add modal (bilingual)

---

## Database Schema Changes

Add to `db/models.py`:

```python
class Customer:
    # ... existing fields ...
    tier: str = "silver"  # tier computed nightly
    tier_spend_12m: float = 0.0  # rolling 12-month spend
    birthday: date | None = None  # optional, captured at POS
    wa_opt_out: bool = False  # respect globally
    rfm_segment: str = "regular"  # computed daily
    last_purchase_date: datetime | None = None  # denormalized

class Campaign:  # optional, for audit trail
    campaign_id: int = Column(Integer, primary_key=True)
    name: str  # "tier_up" | "birthday" | "expiry_nudge" | "winback"
    enabled: bool = True
    template_ar: str
    template_en: str
    sent_count: int = 0
    failed_count: int = 0
    last_run_at: datetime | None = None
```

**Migration:**
- `db/migrate.py`: Add `ensure_loyalty_tier_columns()` and `ensure_campaign_table()`
- Idempotent: check column/table existence before adding

---

## Scheduler Jobs (in `services/scheduler.py`)

1. **Nightly @ 2 AM:** `compute_loyalty_tiers(session)`
   - For each customer: sum LoyaltyTransaction.amount for past 12 months
   - Assign tier based on threshold
   - Log tier changes (for audit)

2. **Daily @ 8 AM:** `send_engagement_campaigns(session)`
   - Tier-up notifications (yesterday's promotions)
   - Birthday offers (today's birthdays)
   - Expiry nudges (threshold met)

3. **Weekly (Mon @ 9 AM):** `compute_rfm_segments(session)`
   - Recompute Recency/Frequency/Monetary for all customers
   - Update `rfm_segment` column

4. **Daily @ 10 AM:** `send_winback_campaign(session)` (throttled)
   - Get dormant segment
   - Queue messages (100/min throttle)
   - Log sends

---

## Frontend Changes

### New Pages
1. **`/crm/customers`** — Enhanced customer list
   - Tier column (badge: Silver/Gold/Platinum)
   - RFM segment filter chips
   - Bulk tier edit (CEO/manager)
   - Last purchase date
   - Birthday + opt-out flags

2. **`/crm/campaigns`** — Campaign manager
   - Campaign toggles (checkboxes per campaign)
   - Template editors (bilingual, RTL-safe markdown or plain text)
   - Stats: sent today / week / month, success rate
   - Manual test send button
   - Recent sends log (last 10 per campaign)

### Updates to Existing Pages
1. **POS (`/pos`):** 
   - Loyalty display: tier badge + points + multiplier (e.g., "250p · Gold (×1.25)")
   - Customer nudge: "No loyalty account? Add now +" → quick-add modal

2. **Dashboard (`/`):**
   - Tier distribution pie (% silver/gold/platinum)
   - Segment distribution (VIP / Regular / At Risk / Dormant counts)
   - Campaign stats widget (sent today, pending)

3. **i18n.js:** Add ~40 new keys (campaign names, tier names, automation descriptions)

---

## Implementation Checklist

### Backend
- [ ] `services/loyalty.py`: Add tier functions
- [ ] `services/crm.py`: RFM segmentation
- [ ] `services/campaigns.py`: Campaign sending + throttling
- [ ] `db/models.py`: Add tier/rfm/birthday/wa_opt_out columns + Campaign table
- [ ] `db/migrate.py`: Idempotent migration functions
- [ ] `api/crm.py`: Campaign CRUD endpoints
- [ ] `services/scheduler.py`: Add 4 new jobs
- [ ] `api/sales.py`: Customer capture during sale
- [ ] Tests: 15+ new test cases (tier, RFM, campaigns, sending, throttling)
- [ ] Run full suite: 196 → ~211 tests

### Frontend
- [ ] `/crm/customers` page (tier, segment, bulk edit)
- [ ] `/crm/campaigns` page (toggles, editors, stats, test send)
- [ ] POS nudge + quick-add modal
- [ ] Dashboard widgets (tier pie, segment counts, campaign stats)
- [ ] i18n: 40+ new keys (AR/EN)
- [ ] RTL testing: Arabic text in forms, badges, labels

### Deployment
- [ ] Commit + push to branch
- [ ] PR: describe tier logic, RFM rules, campaigns
- [ ] Test: all 211 tests pass
- [ ] Build: `next build` clean
- [ ] Merge to main

---

## Success Criteria

✅ Customers auto-promoted to Gold/Platinum when spend crosses threshold  
✅ Tier multiplier applied to loyalty points on next sale after promotion  
✅ RFM segments computed daily; filter works on customers page  
✅ Birthday offer sent on birthday (or +3 days if configured); opt-out respected  
✅ Tier-up, points-expiry, win-back messages throttled and logged  
✅ Campaign toggles enable/disable notifications  
✅ POS nudges customers with no loyalty account; quick-add modal captures phone+birthday  
✅ Dashboard shows tier distribution and segment health  
✅ All 211 tests pass; no regressions  
✅ `next build` clean; RTL tested

---

## Risk Mitigations

**WhatsApp Down:** Campaign jobs log error + create alert task; sales complete normally (no blocking)  
**High Volume:** Throttle at 100 msgs/min; queue failures with exponential backoff  
**Tier Miscalculation:** Recompute nightly is idempotent; manual re-run button if needed  
**Privacy:** `wa_opt_out` checked on every send; birthday optional field; clear consent messaging

---

## Notes for Claude

- Use existing `services/whatsapp.py` builders; don't rebuild
- Leverage existing auth_guard() for role-based endpoints (CEO/manager for campaigns)
- Fail-soft by default: WhatsApp errors logged + alert task, never break checkout
- Bilingual from day one: all messages, UI, validation in AR + EN
- Test isolation: clear Campaign table before each test (like IncentiveLedger in Phase 2)
- Scheduler is production-ready from prior phases; just add new jobs
- FEFO: not affected; loyalty is post-sale, not inventory-related
