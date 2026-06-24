# ProCare OS

**A new, fully independent pharmacy operating system with its own clean database — built for Procare Pharmacies. It first _mirrors_ the live eStock data (read-only), runs in _parallel_ for testing, then _completely replaces_ eStock — fused with the Titan / Drug-Eye clinical drug database and an AI + automation layer.**

> Two branches: **MAIN (الرئيسي)** and **ELSANTA (السنتا)**. Both source systems run on the LAN host **`192.168.1.2`**.
> UI is **Arabic by default (RTL)**; English and Dark mode are **optional, per-user toggles**.

---

## What this repository is

This is the **design + foundation** repository for ProCare OS. It is the conclusion of a careful, end-to-end read of two source documents:

1. **eStock Database — Full Picture Report** — the live SQL Server database `stock` (version `stock_phy_ver1.8.0.0`), audited on 2026-06-23.
2. **ProCare OS — AI & Automation feature spec** — the `PharmacyAI` / `PharmacyAutomation` vision.

From those, plus the owner's direction, this repo defines **how to build a separate, independent system that owns its own clean database, mirrors eStock to validate, runs in parallel, then replaces eStock entirely** — without ever disrupting (or writing to) the live pharmacy operation.

> Owner's words: _"I need a separate system with their own database. Firstly I will depend on the original database for reading data and I will test a new system, then change the old one completely. I want to have my own software independently."_

Start here → **[`docs/00-CONCLUSION.md`](docs/00-CONCLUSION.md)** (the executive conclusion).

## The core decision

ProCare OS is a **standalone system of record**, not a permanent read-only layer over eStock.

- **Own clean database from day one** — real foreign keys, proper indexes, NON-NULL dates, no broken views. This directly fixes every data-quality problem found in eStock (which has **ZERO** stored procedures, **ZERO** functions, **NO** foreign keys, and **8 BROKEN** views).
- **eStock is read-only, and temporary** — used only as the initial source of truth to mirror and validate against during the transition. ProCare **never writes to the eStock database** — read-only ETL only, via a dedicated read-only SQL login.
- **Two branches, modeled cleanly** — MAIN and ELSANTA, with a `branch_id` on every operational row, replicating how eStock connects the branches (Module 7).
- **Fuses clinical intelligence** — Titan / Drug-Eye (at path `D:\Labirdo`) supplies drug product names, substitution/alternatives, interactions, and dosing, surfaced at the counter as **advisory** guidance (never silently blocks a sale).
- **Adds AI + automation** — Arabic assistant, smart reorder, expiry alerts, forecasting, WhatsApp/email reports.

## Build strategy — mirror → parallel → cut over

| Phase | Goal | eStock relationship |
|-------|------|---------------------|
| **Phase 1 — Mirror** | Read from the original eStock DB to mirror data into ProCare's own DB and validate it; stand up the read-only dashboard + Arabic AI assistant. | Read-only ETL |
| **Phase 2 — Parallel** | Run the new system in parallel on **one** branch to test in real use. **Elsanta is the recommended pilot branch.** | Read-only ETL continues |
| **Phase 3 — Cut over** | Switch over **completely** and **retire eStock**. ProCare becomes the sole, independent system of record. | eStock retired |

Full delivery plan: **[`docs/06-roadmap.md`](docs/06-roadmap.md)**.

## Repository map

| Path | What it holds |
|------|---------------|
| [`docs/00-CONCLUSION.md`](docs/00-CONCLUSION.md) | **The conclusion** — the independent-system decision, build strategy, the 3 phases |
| [`docs/01-architecture.md`](docs/01-architecture.md) | Detailed architecture, data flow, tech stack, guardrails (non-negotiable) |
| [`docs/02-eStock-database-reference.md`](docs/02-eStock-database-reference.md) | Full eStock schema reference — 8 modules, key tables, columns |
| [`docs/03-titan-drugeye-integration.md`](docs/03-titan-drugeye-integration.md) | Titan / Drug-Eye (`D:\Labirdo`) integration plan + schema-discovery checklist (**TBD**) |
| [`docs/04-ai-automation-spec.md`](docs/04-ai-automation-spec.md) | AI assistant + automation feature spec (Arabic-first) |
| [`docs/05-data-quality-and-fixes.md`](docs/05-data-quality-and-fixes.md) | Known eStock data issues + the fixes ProCare OS bakes in |
| [`docs/06-roadmap.md`](docs/06-roadmap.md) | Phase-by-phase delivery roadmap (mirror → parallel → cut over) |
| [`docs/07-multi-branch.md`](docs/07-multi-branch.md) | Multi-branch model — Main + Elsanta, transfers, ledgers (eStock Module 7) |
| [`sql/procare-schema.sql`](sql/procare-schema.sql) | ProCare's **own** clean SQL Server schema (FKs, indexes, NON-NULL dates) |
| [`sql/dashboard-queries.sql`](sql/dashboard-queries.sql) | Ready-to-run, **read-only** KPI / dashboard queries against eStock |
| [`config/connections.example.json`](config/connections.example.json) | Connection template (no secrets) — copy to `connections.json` |
| [`.gitignore`](.gitignore) | Ensures `config/connections.json` (and other secrets) are never committed |
| [`src/`](src/README.md) | Application source (scaffold to be filled from Phase 1) |

## The two source systems (on `192.168.1.2`)

| System | Role | Location / Database | Status |
|--------|------|---------------------|--------|
| **eStock** | Operations: POS, purchasing, inventory, customers, vendors, HR, accounts, ledger | SQL Server `stock` (`stock_phy_ver1.8.0.0`) | Live; mirror source for Phase 1, retired after Phase 3 |
| **Titan / Drug-Eye** | Clinical drug intelligence: product names, substitution/alternatives, interactions, dosing | Path `D:\Labirdo`; DB schema **TBD** (not yet audited) — see [`docs/03`](docs/03-titan-drugeye-integration.md) | Live; schema discovery pending |

### eStock at a glance (from the 2026-06-23 audit)

- **~53,474 products** (`Products`, 61 columns: `product_name_ar`/`product_name_en`, `product_scientific_name`, `product_drug`, prices, 3 unit types, 14 barcode slots).
- **95,088 sales invoices** (`Sales_header`) / **183,906 sale lines** (`Sales_details`); **4,359 / 4,212** return headers/lines (`Back_sales_header` / `Back_Sales_details`).
- **1,197 customers** (`Customer`: `customer_max_money` credit limit, `customer_current_money` balance), **87 vendors** (`Vendor`), **1,210 companies** (`Companys`).
- **2 branches** (`Branches`, 52 columns each) — Main + Elsanta. Per-branch stock in `Branches_Product_Amount` (121,625); inter-branch stock transfers in `Branch_order_header` (8,204) / `Branch_order_details` (61,872); inter-branch cash in `Branch_money_order` (1,102) / `Branch_money_convert` (1,098); branch ledger `Gedo_branches` (9,271).
- Real-time inventory in `Product_Amount` (35,404 batch rows: `product_id` + `store_id` + `counter_id` + `exp_date` → `amount`).
- General ledger `Gedo_Financial` (93,925); customer ledger `Gedo_customers` (88,359); vendor ledger `Gedo_Vendors` (2,878).

ProCare OS mirrors all of this into its own clean schema, fixes the data-quality problems, then becomes the single system that finally lets operations and clinical drug data talk to each other.

## Data-quality rules when reading eStock

ProCare's ETL applies these rules; the clean ProCare schema makes them impossible going forward (see [`docs/05`](docs/05-data-quality-and-fixes.md)):

- **`bill_date` is often NULL** on recent sales → always `COALESCE(bill_date, insert_date)`.
- **Exclude returns** from sales metrics → `back IS NULL OR back <> 'Y'`.
- **Available stock** = `amount > 0` **AND** not expired (`exp_date > GETDATE()` or `product_has_expire = 'N'`).
- **FEFO** (First Expire First Out) = `ORDER BY exp_date ASC`.
- **74 expired batches** still in stock; **61 customers** over their credit limit; **33,249 zero/negative** stock batches; **8 broken views** (`item_purchasing`, `store_item_qty`, etc. — querying them crashes).

## Multi-branch — Main + Elsanta

ProCare replicates eStock Module 7 with a clean model: a `branches` table, per-branch + per-batch stock, atomic audited `stock_transfers` (header + lines) between branches, `cash_transfers` between branches, and a unified ledger with a `branch_id` on every financial row. The dashboard/UI has a branch switcher (Main / Elsanta / All). Details: [`docs/07-multi-branch.md`](docs/07-multi-branch.md).

## Tech stack

- **Backend:** Python + FastAPI; `pyodbc` / SQLAlchemy for SQL Server; APScheduler for jobs; Prophet for forecasting.
- **AI:** Claude API powers the Arabic assistant (`PharmacyAI.chat`), which translates natural language into **constrained, READ-ONLY SQL**.
- **Frontend:** React / Next.js — RTL + i18n (Arabic default, English optional), Light default + Dark optional; both preferences persist per user. Product data stored bilingually (`name_ar` / `name_en`).
- **Notifications:** WhatsApp Cloud API + SMTP.
- **Automation:** hourly `auto_purchase_order`; daily 09:00 `expiry_alerts` (90/30/7 days + auto-lock expired); daily/weekly/monthly `auto_reports`; `send_whatsapp`.
- **Optional later:** native .NET 8 POS.

See [`docs/01-architecture.md`](docs/01-architecture.md) and [`docs/04-ai-automation-spec.md`](docs/04-ai-automation-spec.md).

## Security note

- This repo is **private** because it documents internal network topology and database schema.
- **No credentials or connection strings are committed.** Copy [`config/connections.example.json`](config/connections.example.json) → `config/connections.json` (git-ignored via [`.gitignore`](.gitignore)) and fill in a **dedicated read-only** SQL login for the eStock mirror.
- **ProCare NEVER writes to the eStock database** — read-only ETL only. This guardrail keeps the live pharmacy 100% safe throughout Phases 1–2.
- **Clinical / interaction output is ADVISORY**, shown to a pharmacist — it never silently blocks a sale.
- See the full guardrails in [`docs/01-architecture.md`](docs/01-architecture.md#guardrails-non-negotiable).

## Status

Foundation / design phase. Next concrete step: stand up **Phase 1** — the read-only mirror ETL, the dashboard, and the Arabic AI assistant against the live eStock database, then validate against the source. See [`docs/06-roadmap.md`](docs/06-roadmap.md).
