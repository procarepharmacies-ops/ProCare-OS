# Roadmap

**Read first → run parallel → cut over completely.** ProCare OS is a *separate, independent* system
with its own clean SQL Server database. It **never writes to the eStock `stock` DB** — Phase 1–2 read
it read‑only via a dedicated login; Phase 3 retires it.

Owner's words: *"I want my own software independently."* The path there is deliberately staged so the
business is never at risk: mirror and prove the data, pilot the live POS on **one** branch, then cut
both branches over once the numbers match.

**Related docs:** [`01-architecture.md`](01-architecture.md) (phase model + topology) ·
[`02-eStock-database-reference.md`](02-eStock-database-reference.md) (source tables) ·
[`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md) (clinical source — schema **TBD**) ·
[`04-ai-automation-spec.md`](04-ai-automation-spec.md) (AI + automation) ·
[`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md) (read‑time rules) ·
[`07-multi-branch.md`](07-multi-branch.md) (branch model) ·
SQL: [`../sql/procare-schema.sql`](../sql/procare-schema.sql) ·
[`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql).

---

## Phase overview

| Phase | Goal | eStock role | ProCare writes to |
|-------|------|-------------|-------------------|
| **0 — Foundation** | Build the clean DB + app skeleton; secure read‑only access. | Untouched. | Nothing yet. |
| **1 — Mirror & read (shadow)** | Mirror eStock into ProCare's own DB; run dashboards/AI read‑only; reconcile daily. | Source of truth (read‑only). | ProCare DB (mirror only). |
| **2 — Parallel pilot (Elsanta)** | Run ProCare as the real POS on **Elsanta**; eStock stays live on **Mas-hala**. | Still authoritative; cross‑checked. | ProCare DB (real ops, Elsanta). |
| **3 — Full cutover** | Both branches on ProCare; eStock retired to cold backup. | **Retired.** | ProCare DB — sole system of record. |

ASCII timeline (mirrors [`00-CONCLUSION.md`](00-CONCLUSION.md)):

```
 Phase 0:  —                 build schema + skeleton    (eStock untouched)
 Phase 1:  READ ──────────►  shadow / validate          (eStock untouched)
 Phase 2:  READ ──────────►  pilot POS on Elsanta        (eStock still live on Mas-hala)
 Phase 3:  (retired, cold)   BOTH branches, sole SoR     ← independent software
```

---

## Phase 0 — Foundation

*eStock is not touched at all in this phase.*

- [ ] Finalize ProCare's own clean schema (multi‑branch Elsanta + Mas-hala) — [`../sql/procare-schema.sql`](../sql/procare-schema.sql).
  Real FKs, indexes from day one, **NON‑NULL** dates (`sale_date`), `CHECK (amount >= 0)`, no broken views.
- [ ] Seed the two branches: `مسهله / Mas-hala` and `السنطه / Elsanta` (the schema already seeds both).
- [ ] Stand up FastAPI backend skeleton (pyodbc/SQLAlchemy) + React/Next.js UI skeleton.
- [ ] UI defaults locked in: **Arabic / RTL default**, English toggle optional, **Light default**, Dark
      toggle optional — both preferences persist per user. Branch switcher (Elsanta / Mas-hala / All) on every screen.
- [ ] Create a **read‑only** SQL login on `192.168.1.2` for the `stock` DB; fill
      `config/connections.json` (git‑ignored; only `connections.example.json` is committed). **Credentials = TBD.**
- [ ] Confirm the read‑only login truly cannot write (try a blocked `UPDATE` and expect a permission error).
- [ ] **Audit the Titan / Drug‑Eye DB** at `D:\Labirdo` (engine, schema, names/substitution/interaction/dosing
      tables). Schema is **🔴 TBD** — record findings in [`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md).
- [ ] Stand up APScheduler inside the FastAPI service (Windows Task Scheduler is the fallback daemon).
- [ ] Wire the Claude API for the Arabic assistant behind the constrained text‑to‑SQL guardrail
      (single `SELECT`, view whitelist only — see [`04-ai-automation-spec.md`](04-ai-automation-spec.md) §4.3).

**Exit criteria:** schema applies cleanly; app skeleton runs; read‑only login verified non‑writable;
Titan schema documented (or explicitly logged as still TBD with a follow‑up owner).

---

## Phase 1 — Mirror & read (shadow mode)

*ProCare reads the original eStock DB and mirrors it into its own clean DB. eStock stays untouched.*

- [ ] ETL: initial full load from eStock → ProCare DB, applying every data‑quality rule in
      [`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md):
  - [ ] **Products** — eStock `Products` (53,474; 61 cols) → `products` (bilingual `name_ar/name_en`,
        `scientific_name`, `is_controlled` from `product_drug`, `has_expiry` from `product_has_expire`).
  - [ ] **Stock batches** — eStock `Product_Amount` (35,404) / per‑branch `Branches_Product_Amount`
        (121,625) → `stock_batches` with `branch_id`. Filter `amount > 0` and not expired for "available".
  - [ ] **Customers** — eStock `Customer` (1,197) → `customers` (`credit_limit`, `current_balance`).
  - [ ] **Vendors** — eStock `Vendor` (87) → `vendors`; `Product_Vendor` (3,301) for product↔supplier links.
  - [ ] **Sales** — eStock `Sales_header` (95,088) + `Sales_details` (183,906) → `sales` + `sale_lines`,
        using `COALESCE(bill_date, insert_date)` as `sale_date` and excluding returns (`back <> 'Y'`).
  - [ ] **Returns** — eStock `Back_sales_header` (4,359) / `Back_Sales_details` (4,212) → `is_return` rows.
  - [ ] **Purchasing** — eStock `Purchase_header` (685) + `Purchase_details` (9,230) → `purchases` +
        `purchase_lines` (carry `bonus`/free units and `exp_date`).
  - [ ] **Ledger** — eStock `Gedo_Financial` (93,925), `Gedo_customers` (88,359), `Gedo_Vendors`
        (2,878), `Gedo_branches` (9,271) → `ledger_entries` with `branch_id`.
  - [ ] **Inter‑branch** — eStock `Branch_order_header` (8,204) / `Branch_order_details` (61,872) →
        `stock_transfers` (+ lines); `Branch_money_order` (1,102) / `Branch_money_convert` (1,098) → `cash_transfers`.
- [ ] **Incremental sync** keeps ProCare's copy fresh (scheduled delta load) while validating.
- [ ] Load Titan / Drug‑Eye drug names, substitution/alternatives, interaction, and dosing data — or,
      if the schema is still TBD, defer and read Titan live for clinical lookups (see [`03`](03-titan-drugeye-integration.md)).
- [ ] Live dashboard (read‑only) — KPIs + the 10 dashboard queries seeded in
      [`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql): today/month revenue, top products,
      expiry‑in‑30‑days, low‑stock, debtors, vendor payables, daily sales chart, cashier performance, hourly peaks.
- [ ] Arabic AI assistant (`PharmacyAI.chat`) read‑only over ProCare's own copy — constrained text‑to‑SQL.
- [ ] Automated alerts running read‑only: `expiry_alerts` (daily 09:00 — 90/30/7 day horizons) and
      low‑stock / smart‑reorder **drafts** (hourly). Per branch + consolidated.
- [ ] Drug‑interaction lookup (advisory) wired to Titan / Drug‑Eye.
- [ ] **Reconcile** ProCare totals vs eStock **daily** until they match exactly:
  - [ ] Total sales per day (`COALESCE(bill_date, insert_date)`, `back <> 'Y'`).
  - [ ] Total stock value per branch (`amount > 0`, not expired).
  - [ ] Customer balances and vendor balances.
  - [ ] Profit per period (`revenue − cost`).
- [ ] Investigate (never ignore) any drift; document each fix.

**Exit criteria:** mirror reconciles to eStock for **several consecutive days** on all four checks; the
read‑only dashboard, Arabic assistant, expiry/low‑stock alerts, and interaction lookup all work over
ProCare's own copy.

---

## Phase 2 — Parallel run (pilot on Elsanta)

*ProCare becomes the real POS on **Elsanta only**; eStock keeps running on **Mas-hala**.*

- [ ] Implement the hot‑path stored procedures (clean, testable — eStock had **0** SPs/functions):
      `sp_create_sale`, `sp_deduct_stock` (FEFO, never negative), `sp_calc_profit`, `sp_check_credit`,
      `sp_transfer_stock` — see the TODO block in [`../sql/procare-schema.sql`](../sql/procare-schema.sql).
- [ ] POS module on Elsanta: new sale, returns, cash‑desk shift open/close, FEFO batch picking
      (`ORDER BY exp_date ASC`), barcode label printing.
- [ ] **Credit‑limit enforcement at POS** via `sp_check_credit` — a sale that would exceed
      `credit_limit` requires an explicit permissioned override (mirrors eStock `allaw_sale_credit`).
      Directly fixes the **61 customers over credit limit** eStock allowed.
- [ ] **Expiry auto‑lock**: a product whose only on‑hand stock is expired is blocked from sale (fixes
      the **74 expired batches still sellable** in eStock); write‑off writes an audit row to `stock_movements`.
- [ ] Employee permissions enforced (`can_sale_credit`, `can_return`, `can_void`, `can_edit_sell_price`,
      `max_disc_per`) — mirrors eStock's `Employee` permission flags.
- [ ] eStock keeps running on **Mas-hala**, untouched; ProCare's read‑only mirror of Mas-hala continues.
- [ ] **Daily reconciliation of Elsanta**: sales, returns, stock, cash (shift closures), profit — ProCare
      (live) vs the data the branch produces; investigate any mismatch before extending the pilot.
- [ ] **Inter‑branch transfers across the split** (Mas-hala on eStock, Elsanta on ProCare):
  - [ ] Stock transfers Elsanta ↔ Mas-hala via `stock_transfers` (+ lines), batch identity/expiry travels
        with the transfer; bridge/reconcile against eStock `Branch_order_*` until both are on ProCare.
  - [ ] Cash transfers Elsanta ↔ Mas-hala via `cash_transfers`; bridge against eStock `Branch_money_*`.
- [ ] WhatsApp customer invoices (PDF) + debt reminders + supplier POs (draft → approved) live on Elsanta.
- [ ] Sign‑off: owner + Elsanta staff confirm ProCare handles real daily operations without falling back to eStock.

**Exit criteria:** Elsanta runs a full business cycle on ProCare (sales, returns, shift close, transfers,
notifications); daily reconciliation is clean; owner approves promoting Mas-hala.

---

## Phase 3 — Full cutover (independence)

*Both branches on ProCare; eStock retired.*

- [ ] Migrate **Mas-hala** onto ProCare OS too; both Elsanta + Mas-hala now transact on ProCare.
- [ ] Final full mirror + reconciliation of Mas-hala before the switch; freeze eStock writes at cutover.
- [ ] Inter‑branch stock + cash transfers now fully internal to ProCare (`stock_transfers` /
      `cash_transfers`) — no eStock bridge.
- [ ] Decommission the read‑only ETL and the eStock read‑only login.
- [ ] **eStock retired** — kept as a **cold, read‑only backup** for historical reference only.
- [ ] ProCare OS is the **sole, independent system of record** across Elsanta + Mas-hala.
- [ ] Post‑cutover backup/restore tested on the ProCare DB; runbook handed to the owner.

**Exit criteria:** eStock is off the daily path; ProCare is the only system staff use on both branches;
backups verified.

---

## Continuous (once live)

Ongoing capabilities that run after a branch is live (full spec in
[`04-ai-automation-spec.md`](04-ai-automation-spec.md)). Each runs **per branch and consolidated**.

- [ ] **Smart reorder** automation — `auto_purchase_order`, hourly; consumption × lead time vs on‑hand;
      transfer‑aware (suggest a Elsanta↔Mas-hala transfer before a new PO). Drafts only — a human approves.
- [ ] **Sales forecasting (Prophet)** — `sales_forecast` per product/branch (weekly/monthly, seasonality)
      feeding the reorder logic. LSTM noted as a future option; Prophet is the default.
- [ ] **Expiry risk** — daily `expiry_alerts` at 90/30/7 days + auto‑lock of expired‑only products.
- [ ] **WhatsApp** invoices (PDF) / purchase orders / customer debt reminders (Cloud API; SMTP for email).
- [ ] **Auto‑reports** to the manager — daily 08:00, weekly Sun 08:00, monthly 1st 08:00 (revenue,
      profit, top sellers, debtors, expiry, low‑stock).
- [ ] **Customer insights** + targeted offers + refill reminders (top drugs, purchase cadence).
- [ ] **Drug‑interaction safety checks** at every counter sale — advisory to the pharmacist, **never
      silently blocks a sale** (clinical guardrail).
- [ ] **Backups** scheduled and tested on the ProCare DB (eStock had `Run_Backup` empty / `DB_online_update_Error` rows — ProCare logs and verifies).

---

## Mapping to the eStock report's own upgrade list

The eStock audit closed with a 10‑step **UPGRADE ROADMAP** (plus five **IMMEDIATE FIXES**). For eStock
those were patches to a flawed DB; ProCare delivers each one **by design** in the new clean system —
either fixed in the schema, handled at read‑time by the ETL, or built as a first‑class module.

| # | eStock report upgrade (tables it named) | Where ProCare delivers it |
|---|------------------------------------------|---------------------------|
| 1 | Fix NULL `bill_date` (`Sales_header`) | **Phase 1 ETL** uses `COALESCE(bill_date, insert_date)`; ProCare `sales.sale_date` is **NOT NULL** by design ([`05`](05-data-quality-and-fixes.md)). |
| 2 | Add indexes (all main tables) | **Phase 0 clean schema** ships indexes from day one: `IX_sales_date`, `IX_sales_branch`, `IX_sale_lines_sale`, `IX_stock_product_branch`, `IX_stock_expiry` (filtered `amount > 0`), `IX_ledger_branch_date` ([`../sql/procare-schema.sql`](../sql/procare-schema.sql)). |
| 3 | Drop / rewrite the 8 broken views | **None inherited** — ProCare reporting is built on clean, tested views over the new schema (Phase 0). |
| 4 | Build dashboard (read‑only) | **Phase 1** read‑only dashboard; query patterns in [`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql). |
| 5 | Stored procedures for stock deduction (`Product_Amount`, `Product_amount_Change`) | **Phase 2** hot‑path SPs: `sp_deduct_stock` (FEFO, `CHECK amount >= 0`) + `sp_create_sale`, audited via `stock_movements`. |
| 6 | Expiry alerts (automated) (`Product_Amount`) | **Phase 1** automation `expiry_alerts` (daily 09:00, 90/30/7 days) + **Phase 2** auto‑lock of expired stock ([`04`](04-ai-automation-spec.md) §4.2). |
| 7 | Credit‑limit enforcement at POS (`Customer`, `Sales_header`) | **Phase 2** `sp_check_credit` — permissioned override required; fixes the 61 over‑limit customers. |
| 8 | Barcode label printing module (`Products`, `Product_Amount`) | **Phase 2** POS module (barcode picking + label printing). |
| 9 | WhatsApp / SMS customer notifications (new `Customer_notifications`) | **Phase 1+** automation `send_whatsapp` (Cloud API) + SMTP email; invoices, POs, debt reminders. |
| 10 | Multi‑branch real‑time sync (`Branches_*`) | **Multi‑branch model** ([`07`](07-multi-branch.md)): per‑branch + per‑batch `stock_batches`, atomic audited `stock_transfers` / `cash_transfers`, branch‑aware `ledger_entries`. Fully internal by Phase 3. |

### The five "immediate fixes" eStock needed — and why ProCare doesn't

The audit also listed five fixes to apply *to eStock itself* (`UPDATE bill_date`, write off expired
stock, `DROP` the 8 views, `CREATE INDEX`, add FK constraints). ProCare **never runs these against
eStock** (read‑only guardrail). Instead:

| eStock immediate fix | ProCare equivalent |
|----------------------|--------------------|
| `UPDATE Sales_header SET bill_date = insert_date` | Done at **read‑time** in ETL via `COALESCE`; ProCare's own date column is NOT NULL — no back‑fill ever needed. |
| Write off 74 expired batches | ETL filters expired from "available"; Phase 2 auto‑lock + audited write‑off in `stock_movements`. |
| `DROP` the 8 broken views | Not inherited — clean views only. |
| `CREATE INDEX …` on eStock | ProCare indexes exist from Phase 0; eStock is never altered. |
| `ALTER TABLE … ADD CONSTRAINT FK_…` | ProCare has **real FKs everywhere** by design; orphans impossible. |

> Everything in this table is grounded in the eStock audit (`stock_phy_ver1.8.0.0`, report dated
> 2026‑06‑23). Unknowns — the Titan / Drug‑Eye schema and all credentials — remain **TBD** and are
> tracked in [`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md) and
> `config/connections.json` (git‑ignored).
