# ProCare OS — The Conclusion

_A new, **fully independent** pharmacy operating system with **its own clean database**, that first
mirrors the existing **eStock** data (reading from it), runs in parallel for testing, and then
**completely replaces** eStock — fused with the **Titan / Drug‑Eye** drug database and an AI +
automation layer. Arabic by default; English and Dark mode optional._

This document is the executive conclusion. It is the result of reading the two source files
end‑to‑end — the **eStock Database Full‑Picture Report** (audited from the live `stock` database,
`stock_phy_ver1.8.0.0`, report dated 2026‑06‑23) and the **AI & Automation feature spec** — plus the
owner's stated direction:

> _"I need a separate system with their own database. Firstly I will depend on the original
> database for reading data and I will test a new system, then change the old one completely.
> I want to have my own software independently."_

**Read this first, then the supporting docs:**
[`01-architecture.md`](01-architecture.md) ·
[`02-eStock-database-reference.md`](02-eStock-database-reference.md) ·
[`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md) ·
[`04-ai-automation-spec.md`](04-ai-automation-spec.md) ·
[`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md) ·
[`06-roadmap.md`](06-roadmap.md) ·
[`07-multi-branch.md`](07-multi-branch.md) ·
[`../sql/procare-schema.sql`](../sql/procare-schema.sql).

---

## 1. The decision (what we are building)

**ProCare OS is a standalone pharmacy operating system with its own clean SQL Server database — the
new system of record.** It is **not** a permanent read‑only layer on top of eStock, and **not** a
patch to eStock. eStock is used only as the **initial source of truth to read from** while ProCare is
built and validated; once ProCare proves itself, eStock is retired and **ProCare becomes the sole,
independent system of record** for both branches.

**Why a new system at all — what eStock cannot fix about itself.** The eStock database
(`stock`, `stock_phy_ver1.8.0.0`) holds the real history of the business: **53,474 products**,
**95,088 sales invoices** (**183,906** line items), **1,197 customers**, **87 vendors**, across
**2 branches**. But all business logic lives in the closed `.exe`, and the database itself is
structurally weak:

- **0 custom stored procedures, 0 custom functions** — no logic to reuse; every rule (stock
  deduction, profit, credit check) is locked inside the application.
- **No foreign keys enforced** — orphaned rows are possible DB‑wide.
- **8 broken views** that reference tables which no longer exist (`Item_Catalog`, `Pur_trans_h`,
  `Store_trans_h`, …) — querying them crashes.
- **`bill_date` is NULL on all recent sales** — date‑range reports are wrong unless you compensate.
- **74 expired batches still in stock**, **33,249 zero/negative batches**, **61 customers over their
  credit limit** — data‑quality debt that distorts every figure.

We cannot safely "upgrade in place" — we have no permission to write to the production DB, and the
logic we'd need isn't in the DB to begin with. So we build clean and migrate.

**Three things ProCare OS does that eStock cannot:**

1. **Owns a clean schema** — real foreign keys, proper indexes, **non‑null dates**, and **no broken
   views**, designed correctly from day one. See
   [`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md) and the schema in
   [`../sql/procare-schema.sql`](../sql/procare-schema.sql).
2. **Fuses clinical intelligence** — Titan / Drug‑Eye (data at `D:\Labirdo`) is the source of truth
   for drug **names**, **scientific/generic names**, **substitution / alternatives**, and
   **interactions / dosing**, surfaced at the counter. See
   [`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md).
3. **Adds AI + automation** — an Arabic assistant, smart reorder, expiry alerts, sales forecasting,
   and WhatsApp reports. See [`04-ai-automation-spec.md`](04-ai-automation-spec.md).

## 2. Two branches: Main + Elsanta

eStock already runs **two physical branches** — **MAIN (الرئيسي)** and **ELSANTA (السنتا)** —
recorded in its `Branches` table (**2 rows**, 52 config columns per branch). ProCare OS replicates the
same two‑branch model and, crucially, **how the branches are connected** (eStock Module 7):

| Concern | eStock tables (rows) | ProCare clean equivalent |
|---------|----------------------|--------------------------|
| Per‑branch stock | `Branches_Product_Amount` (121,625) — mirrors `Product_Amount` | per‑branch, per‑batch `stock_batches` with `branch_id` |
| Inter‑branch **stock** transfers | `Branch_order_header` (8,204) / `Branch_order_details` (61,872) | `stock_transfers` (header) + `stock_transfer_lines` |
| Inter‑branch **cash** transfers | `Branch_money_order` (1,102) / `Branch_money_convert` (1,098) | `cash_transfers` (request + execution) |
| Consolidated branch ledger | `Gedo_branches` (9,271) | `ledger_entries` with `branch_id` |

ProCare's own schema models this cleanly: a `branches` table, per‑branch / per‑batch stock,
`stock_transfers` (header + lines) between branches, `cash_transfers` between branches, and a unified
ledger with a **`branch_id` on every operational and financial row** — nothing is branch‑ambiguous.
Batch identity and expiry travel with each transfer so FEFO and expiry tracking stay correct across
branches. The dashboard and reports can show **one branch or both combined** via a Main / Elsanta /
All switcher. Full design: [`07-multi-branch.md`](07-multi-branch.md).

## 3. Build strategy — read first, run parallel, then cut over

This is the owner's stated plan, made concrete and safe. The governing rule across every phase:
**ProCare never writes to the eStock database — read‑only ETL only, through a dedicated read‑only SQL
login.** This keeps the live pharmacy 100% safe for the entire transition.

### Phase 0 — Foundation
- Finalize ProCare's own clean database schema (multi‑branch, real FKs, indexes, non‑null dates, no
  broken views) — see [`../sql/procare-schema.sql`](../sql/procare-schema.sql).
- Stand up the FastAPI backend + web UI skeleton (**Arabic default / RTL**; **English + Dark mode
  optional**, both persisted per user).
- Provision the read‑only eStock login and record all connection details in
  `config/connections.json` (git‑ignored; only `config/connections.example.json` is committed).

### Phase 1 — Mirror & read (shadow mode)
- An **ETL / sync engine** (Python + `pyodbc`/SQLAlchemy, scheduled via APScheduler) reads from the
  live eStock `stock` database on `192.168.1.2` and from the Titan / Drug‑Eye source (`D:\Labirdo`),
  and loads ProCare's own DB.
- **Data‑quality fixes are applied on the way in**, never inherited:
  `COALESCE(bill_date, insert_date)` for the NULL‑date bug; exclude returns (`back <> 'Y'`); available
  stock = `amount > 0 AND not expired`; FEFO via `ORDER BY exp_date ASC`. See
  [`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md).
- ProCare runs in **shadow mode** — live dashboards, Arabic AI answers, expiry/low‑stock alerts, and
  drug‑interaction checks, all from its own copy of the data.
- **Validation gate:** ProCare's totals (sales, stock, balances, debtors, payables) are reconciled
  against eStock until they match. This is how we prove correctness before trusting the new system.

### Phase 2 — Parallel run (pilot on one branch)
- Pick one branch — **recommend Elsanta (السنتا)**, the smaller/secondary branch — and run ProCare OS
  as the **real POS** there, writing to **ProCare's own database only**.
- eStock keeps running untouched on the other branch (Main). The Phase‑1 read sync continues so the
  rest of the data stays mirrored.
- Daily reconciliation confirms ProCare handles real sales, returns, stock movements, inter‑branch
  transfers, and money correctly before the stakes go up.

### Phase 3 — Full cutover (independence)
- Switch **both branches** (Main + Elsanta) to ProCare OS as the **sole system of record**.
- eStock is retired and kept only as a **cold, read‑only backup** for historical reference.
- ProCare OS is now **your own independent software** — clean DB, two branches, Titan/Drug‑Eye and AI
  built in.

```
 eStock (live)        ProCare OS (own DB)
 ───────────         ──────────────────
 Phase 0:  —                 build schema + skeleton    (eStock untouched)
 Phase 1:  READ ──────────►  shadow / validate          (eStock untouched)
 Phase 2:  READ ──────────►  pilot POS on Elsanta        (eStock still live on Main)
 Phase 3:  (retired, cold)   BOTH branches, sole SoR     ← independent software
```

The phase‑by‑phase task breakdown is in [`06-roadmap.md`](06-roadmap.md).

## 4. Recommended technology

| Layer | Choice | Why |
|-------|--------|-----|
| Database (own) | **SQL Server** (clean ProCare schema) | Same engine as eStock → straightforward ETL, familiar tooling, and the existing server can host it. |
| Backend / API / AI | **Python + FastAPI** | The AI/automation spec is Python (Prophet, async); excellent SQL Server access; easy WhatsApp/email/scheduling. |
| ETL / sync | Python (`pyodbc` + SQLAlchemy) | Reads eStock + Titan → loads ProCare DB; runs reconciliation jobs. |
| Scheduling | **APScheduler** | Hourly auto purchase orders, daily 09:00 expiry alerts, daily/weekly/monthly reports. |
| Frontend | **React / Next.js** (RTL, i18n) | Runs on any LAN device; **Arabic default, English optional; Light default, Dark optional** — preferences persist per user. |
| AI assistant | **Claude API** (Arabic NL → constrained, **read‑only** text‑to‑SQL) | Answers in Arabic over ProCare's own clean DB; never issues writes. |
| Forecasting | **Prophet** | Consumption / sales forecasting that drives smart reorder. |
| Clinical data | **Titan / Drug‑Eye** (`D:\Labirdo`) | Drug names, scientific names, substitution, interactions, dosing. |
| Reports / PDF | WeasyPrint or ReportLab | Invoices, account statements, manager reports. |
| Notifications | **WhatsApp Cloud API + SMTP** | Invoices, purchase orders, debt reminders, scheduled reports. |
| Native POS (optional, later) | **.NET 8** (WinForms/WPF) + Dapper | If a native desktop counter feel is preferred over the web POS. |

See the full system layout in [`01-architecture.md`](01-architecture.md).

## 5. Guardrails (non‑negotiable)

1. **ProCare never writes to the eStock database.** Read‑only ETL only, via a dedicated **read‑only
   SQL login**. eStock stays safe and untouched for the entire transition.
2. **ProCare's own DB is clean from day one** — real foreign keys, indexes, non‑null `bill_date` and
   other dates, and no broken views. Every eStock data problem
   (see [`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md)) is **fixed in the new schema,
   not inherited**.
3. **Reconcile before trusting.** Do not cut over a branch until ProCare's numbers match eStock's for
   several consecutive days.
4. **Every operational row carries a `branch_id`.** Stock, sales, purchases, transfers, and ledger are
   never branch‑ambiguous.
5. **The AI is read‑only.** The Arabic assistant produces constrained SELECT‑only SQL against
   ProCare's DB; it can never mutate data.
6. **Clinical output is advisory.** Interaction / substitution warnings are shown to a pharmacist and
   **never silently block a sale**.
7. **No secrets in git.** Connection strings and credentials live in `config/connections.json`
   (git‑ignored); only `config/connections.example.json` is committed.

## 6. What's still needed (open items)

1. **Titan / Drug‑Eye database audit** of `D:\Labirdo` — the same "full picture" we have for eStock —
   to map the interaction / substitution / scientific‑name tables. Its schema is **not yet audited
   (TBD)**. Checklist in [`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md).
2. **Read‑only SQL login** + confirmed instance/database names on `192.168.1.2`. eStock DB name
   (`stock`) is known; the **Titan DB name/instance under `D:\Labirdo` is TBD**.
3. **Confirm exact install paths** of both programs — the eStock app path is **TBD**; the Titan
   executable is recorded as `D:\downlod\TITAN.W1B.exe`. Record final values in
   `config/connections.json`.
4. **WhatsApp channel** decision — Cloud API vs. a third‑party gateway (**TBD**).
5. **Confirm the AI model id** used by the assistant (pinned in `config/connections.json`).

> **Note on host/instance:** the eStock audit was generated on `localhost` / `DESKTOP-SHTFS3J`; per the
> ProCare deployment decision the source is reached over the LAN at **`192.168.1.2`**. Confirm the
> reachable server name/instance when the read‑only login is provisioned.

---

### One‑line summary

> **Build ProCare OS as an independent Python/FastAPI + SQL Server system with its own clean,
> two‑branch (Main + Elsanta) database — mirror eStock by reading it (read‑only), validate in shadow
> mode, pilot the live POS on Elsanta in parallel, then cut over both branches completely — with
> Titan/Drug‑Eye clinical data and an AI + automation layer built in, Arabic by default and English +
> Dark mode optional.**

Next: the system architecture in [`01-architecture.md`](01-architecture.md) and the phased plan in
[`06-roadmap.md`](06-roadmap.md).
