# ProCare OS — Product Vision & Backlog (eStock parity + AI pharmacy)

> Captured 2026-07-14 from the owner's brief. This is the authoritative backlog.
> Source spec for eStock parity: `D:\AgenticOS_Brain\Projects\procarepharmacy\estok_reports`
> (120 reports, 104 tables, decompiled exe + DB + screen videos).

---

## A. eStock-structured navigation + reports (the backbone)

Reorganize ProCare's menus to mirror eStock, with **every report filed under the
menu it belongs to**:

| Menu | Reports (from the 120) | Count |
|------|------------------------|-------|
| **المبيعات Sales** | daily sales, by product/company/customer/cashier, visa/network, returns-unsaved, delivery, hourly, totals-rate | 49 |
| **المشتريات Purchases** | purchase details, by vendor, order-buy, bonus, tax, buy-history, returns | 10 |
| **المخازن Inventory** | products, stock, expiry (`product_exp`), shortcoming/نواقص, sites, stock-update, movements, over/short stock | 25 |
| **الخزينة/المالية Finance** | treasury, banks, cash-drawer close (cashier/network), income, tuning, dividends | 18 |
| **الموظفين Employees** | salary, commission, deduction, cash advance, attendance | 6 |
| **الفروع Branches** | branch sales-product, money-convert, orders, history | 4 |
| **الموردين Vendors** | vendor data, history | 3 |

**Per menu, add two AI panels:**
1. **AI Analysis (predictive)** — trends, forecasts, anomalies for that domain (via Hermes local / Gemini). e.g. Sales → demand forecast & slow-mover alert; Purchases → reorder & price-trend; Inventory → expiry risk & dead stock.
2. **OTC list for pharmacist** — the over-the-counter items relevant to that view, for fast counter reference.

Every report: **filterable** (date / vendor / branch / value / any relevant axis) and **exportable to PDF + Excel with ProCare branding**. In all-branches views, **each row is branch-tagged**.

---

## B. POS enhancements

- **Loyalty at checkout**: show the customer's **points balance** during the sale; allow **redeeming points for a 5% discount** on selected items, for **selected customers** only.
  (ProCare already has `loyalty_points` + a loyalty service — extend the POS UI to surface balance + redeem, and a customer/product eligibility flag.)

---

## C. Drug data & naming authority

- **Egyptian Drug Authority (هيئة الدواء المصرية)** integration: pull official drug **prices**, **correct names**, and **circulars/notices (منشورات)** into the system; refresh prices/names automatically.
- **On add-product, auto-name & code:**
  - **Medicines → Drug-Eye** (Titan) for correct scientific/trade name + local data (already mirrored: `titan_drugs`).
  - **Cosmetics → Amazon** for better product name + **international barcode/code**.
- Reference library the owner will provide: **prescription photos**, **pharmaceutical compounding books**, epidemiology/pharmacology texts — ingest for the prescription-reader training + a clinical knowledge base (feeds the AI assistant / clinical advisory).

---

## D. Clinical & care programs (formulation-based)

- **Hair-care / skin-care / slimming programs** built on **compounding formulas** + the pharmacy's **InBody device** readings (body composition) → personalized regimen + product basket.
- **Compounding module**: formula → ingredients → cost → label.

---

## E. Chronic-care CRM (proactive refills)

- **Segment customers by chronic disease** inferred from their **dispensing history** (drug → condition mapping: e.g. metformin→diabetes, amlodipine→hypertension).
- **Proactive free delivery**: 3 days before a chronic patient's supply runs out, **call/WhatsApp** them and deliver free.
  (Uses sale history + typical days-of-supply per drug; ties into the WhatsApp service already present.)

---

## F. Additional AI/pharmacy ideas (proposed — expand with Firecrawl research)

- **Drug-interaction & dose checker** at dispensing (safety) — from the compounding/clinical KB.
- **Substitution engine** by scientific name (already seeded via Titan) surfaced at POS when out of stock.
- **Near-expiry auto-discount** to move stock before it expires (FEFO-aware).
- **Demand forecasting** per product for purchasing (seasonality + trend).
- **Cold-chain/insulin-fridge** temperature log + alert.
- **Controlled-substance register** compliance report (Egyptian narcotics law).
- **Insurance/contract claims** tracking (contracts already in schema).
- **Basket analysis** (what sells together) → counter upsell prompts.
- **Doctor prescribing-habits** analytics (already have doctor-habits) → targeted detailing.

> To research/validate market features: use the `firecrawl-*` skills (need MCP
> auth first via `/mcp`), e.g. competitive-intel on Egyptian pharmacy software,
> Egyptian Drug Authority price-list source, InBody API.

---

## Phasing (build order)

1. **Data first** — live mirror from the Elsanta head-office server so every
   report shows real eStock numbers (sales/purchases/treasury already reconciled
   in the ETL). *Nothing else matters until the numbers are right.*
2. **eStock nav + reports framework** — domain menus, a reusable Report shell
   (table + filters + PDF/Excel export + branch tags), then fill reports by
   priority (daily sales → purchases-by-vendor → cash-by-branch → expiry → …).
3. **Per-menu AI Analysis + OTC panels.**
4. **POS loyalty redeem.**
5. **Drug Authority + Drug-Eye/Amazon naming on add-product.**
6. **Chronic-care CRM + proactive refills.**
7. **Care programs (InBody + compounding).**

Each phase ships behind the fail-soft rules in CLAUDE.md and stays bilingual RTL.
