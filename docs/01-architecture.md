# ProCare OS — Architecture

ProCare OS is a **standalone system with its own clean SQL Server database** — the new system of
record for Procare Pharmacies (two branches: **Main / الرئيسي** and **Elsanta / السنتا**). It reads
from the legacy eStock database and Titan/Drug‑Eye **only during the transition**, then becomes fully
independent and eStock is retired.

This independence is deliberate (owner's words): *"I want my own software independently."* The legacy
eStock database (`stock`, version `stock_phy_ver1.8.0.0`, on LAN host `192.168.1.2`) holds ~53,474
products, 95,088 sales (183,906 lines), 1,197 customers, and 87 vendors across 2 branches — but it has
**zero stored procedures, zero functions, no foreign keys, and 8 broken views**; all business logic
lives inside the eStock `.exe`. ProCare rebuilds that logic in versioned, testable code over a database
that is correct from day one. See [`02-eStock-database-reference.md`](02-eStock-database-reference.md)
for the full source audit and [`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md) for the
data‑quality problems being fixed.

## Three‑phase strategy (context)

| Phase | What runs | eStock role |
|-------|-----------|-------------|
| **Phase 1 — Mirror & validate** | ProCare reads the original eStock DB read‑only, mirrors data into its own clean DB, and reconciles totals. | Source of truth (read‑only). |
| **Phase 2 — Parallel pilot** | ProCare runs **in parallel on one branch** to test against reality. **Elsanta is the recommended pilot.** | Still authoritative; ProCare cross‑checked against it. |
| **Phase 3 — Cutover** | ProCare is the **sole production system** across Main + Elsanta. ETL is decommissioned. | **Retired.** |

See [`06-roadmap.md`](06-roadmap.md) for the phased rollout and [`00-CONCLUSION.md`](00-CONCLUSION.md)
for the executive summary.

## High‑level picture

```
                         ┌─────────────────────────────────────────────┐
   Manager phone  ─────► │              ProCare OS                      │
   Counter PC     ─────► │                                              │
   (Main + Elsanta)      │   Web UI (React / Next.js)                   │
   over the LAN          │   • Arabic default (RTL) • English optional  │
                         │   • Light default • Dark mode optional       │
                         │   • Branch switcher: Main / Elsanta / All    │
                         │        │                                     │
                         │        ▼                                     │
                         │   FastAPI backend (Python 3.12)              │
                         │   ├── Dashboard / reports API                │
                         │   ├── Sales / inventory / purchasing / HR    │
                         │   ├── AI assistant (Arabic, NL → read‑SQL)   │
                         │   ├── Automation scheduler (APScheduler)     │
                         │   ├── Drug service (Titan / Drug‑Eye)        │
                         │   ├── Multi‑branch (Main + Elsanta)          │
                         │   └── Notifications (WhatsApp / SMTP email)  │
                         │        │                                     │
                         │        ▼                                     │
                         │   ╔══════════════════════════════╗           │
                         │   ║  ProCare OWN database (SQL)   ║  ← system │
                         │   ║  clean schema · real FKs ·    ║    of     │
                         │   ║  indexes · NON‑NULL dates ·   ║   record  │
                         │   ║  branch_id on every row       ║           │
                         │   ╚══════════════════════════════╝           │
                         └────────────▲─────────────────────────────────┘
                                      │ ETL / sync (READ‑ONLY, transition only,
                                      │ dedicated read‑only SQL login)
                          ┌───────────┴───────────┐
                          ▼                        ▼
              ┌──────────────────────┐  ┌──────────────────────────┐
              │  eStock SQL  `stock` │  │  Titan / Drug‑Eye         │
              │  192.168.1.2         │  │  D:\Labirdo               │
              │  ops / POS / money / │  │  drug NAMES · SUBSTITUTION │
              │  inventory / ledger  │  │  interactions · dosing     │
              │  (read‑only; retired │  │  (read‑only; schema = TBD) │
              │   after cutover)     │  │                           │
              └──────────────────────┘  └──────────────────────────┘
```

**ProCare never writes to eStock.** The only arrows into eStock are read‑only ETL pulls through a
**dedicated read‑only SQL login**, and they stop entirely after cutover. Titan/Drug‑Eye is likewise
read‑only; its database schema is **not yet audited (TBD)** — see
[`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md).

## Components

### 1. ProCare own database (SQL Server)
- The new **system of record**. Clean schema defined in
  [`../sql/procare-schema.sql`](../sql/procare-schema.sql).
- **Multi‑branch from day one** (Main + Elsanta) — every operational table carries `branch_id`. See
  [`07-multi-branch.md`](07-multi-branch.md).
- Fixes every eStock data problem catalogued in
  [`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md):
  - **Real foreign keys** everywhere (eStock enforces none — risk of orphaned rows).
  - **Indexes from day one** on hot paths (e.g. `IX_sales_date`, `IX_stock_product_branch`,
    `IX_stock_expiry`).
  - **NON‑NULL dates** — `sales.sale_date` is `NOT NULL DEFAULT SYSDATETIME()`, fixing eStock's
    pervasive NULL `bill_date` on recent sales.
  - **No negative stock** — `stock_batches.amount` has `CHECK (amount >= 0)`, vs eStock's 33,249
    zero/negative batches.
  - **No broken views** — eStock ships 8 views that reference tables which no longer exist
    (`Item_Catalog`, `Pur_trans_h`, `Store_trans_h`, …) and crash on query.
- Core tables (clean equivalents of eStock's): `branches`, `products`, `stock_batches`,
  `stock_movements`, `customers`, `vendors`, `employees`, `sales` / `sale_lines`,
  `purchases` / `purchase_lines`, `stock_transfers` / `stock_transfer_lines`, `cash_transfers`,
  `ledger_entries`.
- Product names are stored **bilingually** (`name_ar`, `name_en`) and each product carries a
  nullable `titan_drug_id` linking it to Titan/Drug‑Eye.

### 2. ETL / sync engine (transition only)
- Reads eStock `stock` (`192.168.1.2`) and Titan/Drug‑Eye (`D:\Labirdo`) via a **read‑only** login —
  never a write of any kind to the source.
- **Initial load:** products (`Products`, 53,474), batch stock (`Product_Amount` / per‑branch
  `Branches_Product_Amount`, 121,625), customers (`Customer`, 1,197), vendors (`Vendor`, 87), sales
  history (`Sales_header` 95,088 / `Sales_details` 183,906), purchasing, and ledger
  (`Gedo_Financial`, `Gedo_customers`, `Gedo_Vendors`, `Gedo_branches`) → ProCare DB.
- **Data‑quality transforms on read** (apply the rules from `05`):
  - `bill_date` is often NULL → `COALESCE(bill_date, insert_date)`.
  - Exclude returns → `back <> 'Y'` (eStock keeps returns in `Back_sales_header` / `Back_Sales_details`).
  - Available stock → `amount > 0 AND (exp_date > GETDATE() OR has_expiry = 'N')`.
  - FEFO ordering → `ORDER BY exp_date ASC`.
  - Flag the 74 expired‑but‑in‑stock batches and 61 over‑credit‑limit customers for review.
- **Incremental sync (Phase 1):** keep ProCare's copy fresh while validating.
- **Reconciliation jobs:** compare ProCare totals vs eStock daily (revenue, stock value, debtors);
  report any drift before it is trusted.
- **Decommissioned at cutover** (Phase 3).

### 3. Web UI (React / Next.js)
- Arabic‑first, **RTL by default**. Runs on the LAN; reachable from counter PCs (Main + Elsanta) and
  the manager's phone.
- **English** is an optional language toggle (full i18n, all strings externalized; direction flips
  with the language).
- **Dark mode** is an optional theme toggle (**light is default**). Both preferences persist per user.
- Screens mirror eStock's 9 functional modules — Sales/POS, Purchasing, Inventory, Customers, Vendors,
  HR, Accounts, Reports, Settings — see [`02-eStock-database-reference.md`](02-eStock-database-reference.md).
- A **branch switcher** (Main / Elsanta / consolidated) is present on every screen.

### 4. FastAPI backend (Python 3.12)
- One API serving UI, ETL, automation, and AI. Organized as a module per domain (sales, inventory,
  customers, vendors, branches, HR, accounts, reports).
- After cutover, this owns **all the business logic eStock kept inside its `.exe`** — but in
  versioned, testable code. Hot paths are pushed into stored procedures (planned in
  [`../sql/procare-schema.sql`](../sql/procare-schema.sql)): `sp_create_sale`, `sp_deduct_stock`,
  `sp_calc_profit`, `sp_check_credit`, `sp_transfer_stock`.
- Enforces permissions equivalent to eStock's `Employee` flags (e.g. `can_see_buy_price`,
  `can_edit_sell_price`, `can_sale_credit`, `can_return`, `can_void`, `max_disc_per`).

### 5. AI assistant (Arabic)
- Natural‑language → **safe, read‑only** SQL against ProCare's own clean DB (constrained
  text‑to‑SQL). Answers in Arabic; **never executes a write from a chat prompt.**
- Backed by the **Claude API**. The model only emits `SELECT` over a whitelisted schema; the backend
  validates and parameterizes before execution.
- Surface: `PharmacyAI.chat` plus structured helpers (`smart_reorder`, `expiry_risk`,
  `sales_forecast`, `drug_interactions`, `customer_insights`). See
  [`04-ai-automation-spec.md`](04-ai-automation-spec.md).

### 6. Automation scheduler (APScheduler)
- `PharmacyAutomation` jobs, mirroring [`04-ai-automation-spec.md`](04-ai-automation-spec.md):
  - **Hourly:** `auto_purchase_order` — reorder draft from low‑stock / `min_stock` thresholds
    (eStock surfaces these in `Shortcoming`, 5,754 rows).
  - **Daily 09:00:** `expiry_alerts` — 90 / 30 / 7‑day horizons **and auto‑lock expired batches**.
  - **Daily / weekly / monthly:** `auto_reports` — manager KPI digests.
  - **On demand / scheduled:** `send_whatsapp` for invoices, POs, debt reminders, reports.

### 7. Drug service (Titan / Drug‑Eye)
- Maps ProCare products → Titan via `products.titan_drug_id` to return drug **names**,
  **substitutions / alternatives**, **interactions**, and **dosing**. Read‑only and **advisory**.
- Titan lives at `D:\Labirdo`; its DB schema is **not yet audited (TBD)** — mapping and discovery
  approach in [`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md).

### 8. Notifications
- **WhatsApp Cloud API** + **SMTP email**: invoices (PDF), purchase orders, debt reminders for
  over‑limit / overdue customers, and scheduled manager reports.
- PDFs rendered with WeasyPrint / ReportLab.

## Localization & theming (owner requirements)

| Preference | Default | Option | Implementation |
|-----------|---------|--------|----------------|
| Language | **Arabic** (RTL) | English (LTR) | i18n dictionaries (`ar.json`, `en.json`); page `dir` flips with the language. |
| Theme | **Light** | Dark | CSS variables / theme tokens; toggle persisted per user. |
| Branch | **Last used** | Main / Elsanta / All | Branch switcher on every screen; selection scopes all queries by `branch_id`. |

Language and theme are **user‑level toggles, remembered across sessions**. All product data is stored
bilingually (`name_ar`, `name_en`) so every screen renders correctly in either language. Arabic is the
primary working language; English is purely an optional convenience.

## Data‑flow examples

### A. Counter sale with interaction safety check (post‑cutover)
1. Cashier scans items at a branch PC → ProCare reads available batches **FEFO** from its own
   `stock_batches` for the **active `branch_id`** (`amount > 0`, not expired, `ORDER BY exp_date ASC`).
2. The **drug service** checks interactions across the basket **and** the customer's recent history
   via Titan/Drug‑Eye, and looks up in‑stock substitutions for any flagged item.
3. If a serious interaction exists, the pharmacist sees an **advisory** banner plus available
   alternatives. The advisory **never silently blocks the sale** — the pharmacist decides.
4. `sp_check_credit` validates the customer against `credit_limit` for credit sales.
5. On confirm, `sp_create_sale` runs **atomically** in one transaction: insert `sales` header +
   `sale_lines`, deduct stock per batch via `sp_deduct_stock` (FEFO, never below zero), write
   `stock_movements` audit rows, and post `ledger_entries`. All FK‑checked — no orphan rows possible.

### B. Inter‑branch stock transfer (Main → Elsanta)
1. Elsanta requests 50 units of product X → `stock_transfers` header (`status = 'requested'`) +
   `stock_transfer_lines`.
2. Main approves & ships → `status = 'in_transit'`; Main stock −50 from the FEFO batch
   (`sp_transfer_stock`).
3. Elsanta receives → `status = 'received'`; Elsanta stock +50, with the **same batch identity and
   expiry** preserved so FEFO/expiry stay correct across branches.
4. Both legs are audited as `stock_movements` rows under one `transfer_id`; cash transfers between
   branches follow the same request→execute pattern in `cash_transfers`. This replicates eStock
   Module 7 (`Branch_order_header/details`, `Branch_money_order/convert`). See
   [`07-multi-branch.md`](07-multi-branch.md).

### C. Nightly / scheduled automation
1. **09:00** — expiry scan (90/30/7 days) over `stock_batches`; auto‑lock expired batches; WhatsApp
   the manager the at‑risk list.
2. **Hourly** — reorder check against `min_stock`; draft purchase orders per branch.
3. **Daily** — KPI email/WhatsApp (revenue, profit, top sellers, debtors) per branch and consolidated.
4. **Weekly / monthly** — rollup reports. Forecasting (Prophet) feeds `smart_reorder` and
   `sales_forecast`.

## Tech stack

| Concern | Technology | Notes |
|--------|------------|-------|
| Own database | SQL Server | Clean ProCare schema, multi‑branch, real FKs + indexes. |
| API / business logic | Python 3.12, FastAPI | Module per domain; hot paths in stored procedures. |
| DB driver | `pyodbc` + ODBC Driver 18, via SQLAlchemy Core | Read‑only login for eStock; read/write for ProCare DB. |
| ETL / reconciliation | Python | Read‑only on eStock (`192.168.1.2`) + Titan (`D:\Labirdo`). |
| Scheduler | APScheduler | Hourly reorder, 09:00 expiry, daily/weekly/monthly reports. |
| Forecasting | Prophet | Demand forecast → smart reorder, sales forecast. |
| AI assistant | Claude API | Arabic NL → constrained, read‑only text‑to‑SQL. |
| Frontend | React / Next.js | RTL by default, i18n (ar/en), light default + dark toggle. |
| PDF | WeasyPrint / ReportLab | Invoices, purchase orders, reports. |
| Notifications | WhatsApp Cloud API + SMTP | Invoices, POs, debt reminders, scheduled reports. |
| Native POS (optional, later) | .NET 8 (WinForms/WPF), Dapper | Optional offline‑resilient counter app. |

## Guardrails (non‑negotiable)

1. **ProCare never writes to eStock.** Read‑only ETL only, via a **dedicated read‑only SQL login**;
   it stops entirely at cutover.
2. **ProCare's own DB is clean from day one** — real FKs, indexes, NON‑NULL dates, `amount >= 0`
   checks, no broken views — and fixes every eStock data‑quality problem.
3. **Writes to ProCare's DB go through stored procedures + transactions** on the hot paths
   (`sp_create_sale`, `sp_deduct_stock`, `sp_transfer_stock`, `sp_check_credit`).
4. **Reconcile before trusting.** Match eStock totals for several consecutive days before relying on
   ProCare, and again before cutover.
5. **Secrets out of git.** `config/connections.json` is git‑ignored; only
   [`../config/connections.example.json`](../config/connections.example.json) is committed.
6. **Clinical / interaction output is advisory.** It is shown to a pharmacist and **never silently
   blocks a sale.**

## Environments

| Environment | Where | Reads | Writes |
|-------------|-------|-------|--------|
| **Dev** | Developer machine | Restored eStock backup (read‑only) | A dev ProCare DB only. |
| **Phase 1–2** | LAN box (can be `192.168.1.2` or a dedicated machine) | eStock `stock` + Titan (read‑only) | ProCare's own DB only. |
| **Phase 3 (prod)** | LAN production host | — (eStock retired) | ProCare DB — sole system across Main + Elsanta. |

---

**Related documents:**
[`00-CONCLUSION.md`](00-CONCLUSION.md) ·
[`02-eStock-database-reference.md`](02-eStock-database-reference.md) ·
[`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md) ·
[`04-ai-automation-spec.md`](04-ai-automation-spec.md) ·
[`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md) ·
[`06-roadmap.md`](06-roadmap.md) ·
[`07-multi-branch.md`](07-multi-branch.md) ·
schema: [`../sql/procare-schema.sql`](../sql/procare-schema.sql) ·
dashboard queries: [`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql)
