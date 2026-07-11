# ProCare OS — Task Plan (B.L.A.S.T.)

> Working memory: phases, goals, checklists. `CLAUDE.md` is the constitution;
> `findings.md` holds research; `progress.md` holds the run log.

## North Star
eStock-parity pharmacy operating system: the pharmacy runs its whole day
(sales, inventory, جرد, prescriptions, approvals, reports) from ProCare on the
pharmacy Windows PC, continuously mirroring the real eStock database, fully
bilingual (Arabic RTL first).

---

## Phase 0 — Foundation ✅ (merged to main, PRs #13–#15)
- [x] Windows 500 fix (safe seed + optional dotenv)
- [x] Multi-provider LLM registry (anthropic/gemini/ollama/claude-cli, fail-soft)
- [x] WhatsApp automation (invoices, returns, manager alerts)
- [x] Out-of-stock substitution → transfer request → approval workflow
- [x] Prescription capture → review → POS sale
- [x] Professional daily ops tasks (priority/category/auto-assign)
- [x] Dashboard drill-down (product insight modal, clickable rows)
- [x] eStock connector batch script (`deploy/ProCare-Connect-eStock.bat`)

## Phase 1 — eStock parity: الجرد + search (BUILT — pending PR + pharmacy-PC verify)
**B — Blueprint**
- [x] Data schema for stocktaking defined (see CLAUDE.md → Data Schemas)
- [x] Discovery answers confirmed by owner (defaults approved via continue)
- [x] Blueprint approved

**A — Architect**
- [x] `stock_counts` + `stock_count_lines` models (create_all-safe, no column migrations needed)
- [x] Service `services/stocktaking.py`: create (full/periodic/partial), count sheet,
      record counts, post adjustments (atomic, audit trail), cancel, variance report,
      top-movers scope for periodic counts
- [x] API `api/stocktaking.py` registered under `/api/stocktaking`
- [x] Search: prefix-first ranking in `inventory.list_products` (one letter → all
      products starting with it, AR/EN/code, then contains-matches)
- [x] POS: Enter adds top match to cart; match-count hint under search box
- [x] Tests: `test_stocktaking.py` (create→count→post→stock adjusted; idempotency;
      closed-session guard; variance math), search-ranking test
- [x] Frontend: `/stocktaking` page (sessions list, count sheet, variance report,
      post/cancel), nav entry, i18n keys (AR/EN)
- [x] Verify dashboard second-click drill-down end-to-end (works in this build;
      pharmacy PC needs pull + rebuild)

**S — Stylize**
- [x] Count sheet printable (window.print on the sheet view) (A4, RTL) like eStock's count report
- [x] Variance report totals styled (shortage red / overage green)

**T — Trigger**
- [x] pytest green (160/160) + `next build` clean
- [ ] Commit per feature, push branch, PR to main
- [ ] Owner pulls on pharmacy PC, restarts, verifies with real data

## Phase 2 — eStock parity round 2 (BUILT — same PR #17)
- [x] Units وحدة كبرى/صغرى: model + migration + ETL + POS unit selling + inventory display
- [x] Stagnant items الأصناف الراكدة: report endpoint + inventory view + جرد scope
- [x] Cross-branch availability in POS (out-of-stock rows show other branch's stock)
- [x] fix: branch-scoped sync wipe vs pending transfer requests (NULL-batch lines)

## Phase 3 — eStock parity round 3 (owner's full list, 2026-07-11)
**BUILT this round:**
- [x] P0 Backups: service (SQLite copy / SQL Server BACKUP), auto on startup (24h)
      + before any full sync wipe (6h throttle) + POST /api/backup + Settings UI
- [x] P1 Product classification: dosage_form/is_otc/uses columns + migration,
      filters on items screen (form/OTC/place/price-sort) + إضافة صنف جديد form
- [x] P2 POS invoice profit (مكسب الفاتورة) — manager/CEO only
- [x] P3 كشكول النواقص وخطة الشراء: priority (رصيد صفر ← طلب عميل ← تحت الحد),
      transfer-first rule with حوّل الآن button, consolidated multi-branch order
      under the 80% budget (GET /purchasing/plan, /plan/consolidated)
- [x] P5 Vendor account: متوسط الخصم في التفاصيل, كشف حساب مورد (bills+payments,
      running balance), صرف لمورد from branch treasury (atomic, balance drops)
- [x] P6 Grouped رئيسي/فرعي sidebar (6 sections)

**Already existed (verified, no rebuild):** treasury vouchers صرف/توريد + تحويل
نقدي بين الفروع + أرصدة الفروع; تقفيل درج الكاشير (cash shifts); كشف حساب عميل;
أداء الفروع بالسنوات (performance.overview); ميزان مراجعة + قائمة دخل
(accounting); قاعدة 80% (autopurchase.daily_budget).

**Next (not yet built):**
- [ ] P4 Transfer receive review (استلام الإذن بتأكيد الصلاحية والكمية قبل الترحيل)
- [ ] Vendor page UI: show statement + pay button (backend endpoints ready)
- [ ] Customer 360 screen (كل العمليات + الأدوية + العنوان + النقاط + رسائل) — statement/loyalty exist, needs one screen
- [ ] Chart of accounts screen (شجرة الحسابات) فوق دفتر القيود الموجود
- [ ] Purchase entry extra fields (تسوية/خصم نقدي) — purchases come from eStock sync; local entry form exists؟ review
- [ ] Barcode-scanner count sheet; small-unit price override; Gemini/ollama keys
