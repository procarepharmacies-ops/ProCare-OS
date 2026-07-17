# Data Quality — eStock Issues & How ProCare Fixes Them

The eStock audit (`stock_phy_ver1.8.0.0`, report dated 2026-06-23) flagged real, countable
problems. This document is the authoritative catalogue of **every** data-quality defect, and for each
one it states three things:

1. **The defect** — exactly what is wrong in eStock, with the exact count from the audit.
2. **The ETL handling** — how ProCare's read-only ETL copes with it *while reading* the original
   `stock` database (Phase 1 mirror), so the mirror is faithful and never carries the rot forward.
3. **The ProCare fix-by-design** — how the new clean schema (`../sql/procare-schema.sql`) makes the
   problem structurally impossible in the new system of record.

Then it defines the **reconciliation method** used to prove the mirror is correct before any branch
cuts over.

> **Guardrail (LOCKED):** ProCare **never** writes to the eStock database. All access to `stock` is
> read-only, through a dedicated read-only SQL login. The "fixes" below are applied in ProCare's own
> clean database — the original eStock data is left untouched. The audit's own `UPDATE`/`DROP`/`ALTER`
> remediation snippets are recorded here for reference only and are **not** run against eStock.

Related docs: [`01-architecture.md`](01-architecture.md) ·
[`02-eStock-database-reference.md`](02-eStock-database-reference.md) ·
[`07-multi-branch.md`](07-multi-branch.md) · [`06-roadmap.md`](06-roadmap.md).
Schema: [`../sql/procare-schema.sql`](../sql/procare-schema.sql) ·
Query patterns: [`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql).

---

## 1. Issue register (exact counts from the audit)

| # | Issue | Count (from audit) | Severity | Business impact |
|---|-------|--------------------|----------|-----------------|
| 1 | 8 broken views referencing tables that no longer exist | **8 views** | Critical | Any query against them crashes |
| 2 | Expired batches still carried as live stock | **74 batches** | High | Overstated stock; expired product sellable |
| 3 | Customers over their credit limit | **61 customers** | Medium | Credit control bypassed |
| 4 | `bill_date` NULL on recent sales | **All recent records** | High | Date-based reports are wrong |
| 5 | Zero/negative stock batches | **33,249 batches** | Normal | Sold-out batches clutter every stock query |
| 6 | No foreign keys enforced | **DB-wide** (0 FKs) | Risk | Orphaned rows accumulate over time |
| 7 | No stored procedures / functions | **0 custom** | Structural | All business logic trapped in the `.exe` |
| 8 | No business logic in the DB layer | DB-wide | Structural | Stock deduction, profit, credit checks live only in the app |
| 9 | Missing indexes for reporting | DB-wide | Performance | Date-range and stock reports scan large tables |

> The audit also documents the absence of any safe re-runnable logic in the database: **0** custom
> stored procedures, **0** custom functions; the only programmability present is SQL Server's own
> unused stubs (**22** `dt_*` source-control SPs, **6** `sp_*diagram` SPs, **1** `fn_diagramobjects`).
> Everything operational — POS, stock movement, pricing, credit — is compiled into the eStock `.exe`.

Supporting magnitude (for reconciliation scope): **53,474** products, **95,088** sales headers,
**183,906** sale lines, **35,404** real-time batch rows (`Product_Amount`) plus **121,625**
branch-level batch rows (`Branches_Product_Amount`), **1,197** customers, **87** vendors, **2**
branches (MASHALA / `مسهله`, ELSANTA / `السنطه`).

---

## 2. Defect-by-defect handling

### 2.1 — NULL `bill_date` on recent sales (High)

**Defect.** `Sales_header.bill_date` (`datetime`) is frequently NULL on recent invoices — the audit
calls this out explicitly ("Invoice date (often NULL — bug)"). `Sales_header.insert_date` (`datetime`,
"Actual record creation time") is reliably populated. Any report grouped on `bill_date` silently drops
or misdates NULL rows. The same pattern is mirrored on returns (`Back_sales_header`).

**ETL handling (read-only).** Treat the effective sale timestamp as:

```sql
COALESCE(bill_date, insert_date) AS effective_sale_date
```

Every extract that buckets sales by day/month uses this expression, never raw `bill_date`. The dashboard
query pack already standardises on `insert_date` for "today/this month" KPIs for the same reason — see
[`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql).

**ProCare fix-by-design.** In `../sql/procare-schema.sql` the `sales` table defines:

```sql
sale_date  DATETIME2 NOT NULL DEFAULT SYSDATETIME()   -- NOT NULL (eStock bug fixed)
```

The column is **NON-NULL with a server default**, so a sale can never exist without a real timestamp.
The ETL writes `COALESCE(bill_date, insert_date)` into `sales.sale_date`; from cutover onward the POS
path sets it at creation. Reporting indexes (`IX_sales_date`, `IX_sales_branch`) sit directly on this
clean column.

---

### 2.2 — Expired batches still carried as live stock (High)

**Defect.** **74** batches in `Product_Amount` have `exp_date < today` yet still have `amount > 0`, so
they inflate stock value and remain technically sellable. `Products.product_has_expire = 'N'` marks
products that legitimately never expire (these must NOT be filtered out).

**ETL handling (read-only).** "Available stock" is defined as:

```sql
pa.amount > 0
AND (pa.exp_date > GETDATE() OR p.product_has_expire = 'N')
```

Expired-but-positive batches are still mirrored faithfully (so reconciliation can see them and so the
expiry-risk report can quantify them), but they are flagged `is_expired = 1` in the mirror and excluded
from any "sellable / available" figure. FEFO ordering (`ORDER BY exp_date ASC`) is applied wherever a
batch must be chosen for a sale.

**ProCare fix-by-design.** `stock_batches` keeps the batch granularity (`product_id`, `branch_id`,
`exp_date`, `amount`) and indexes expiry for reporting:

```sql
CREATE INDEX IX_stock_expiry ON stock_batches(exp_date) WHERE amount > 0;
```

Expiry status is **derived** at query time from `exp_date < CAST(SYSDATETIME() AS DATE)` rather than
trusting a stale stored flag, so it can never drift. The daily `expiry_alerts` automation (09:00 —
90/30/7-day horizons) surfaces approaching expiries and **auto-locks expired batches from sale** with
an audit row in `stock_movements` (`reason = 'writeoff'`), instead of leaving them silently saleable.
Clinical/expiry output is advisory and shown to a pharmacist; it does not silently delete stock.

---

### 2.3 — Customers over their credit limit (Medium)

**Defect.** **61** customers have `customer_current_money` (outstanding balance) exceeding
`customer_max_money` (credit limit). eStock relies on the application and the `allaw_sale_credit`
employee permission flag to gate credit sales; the database itself enforces nothing, so limits drift.

**ETL handling (read-only).** Balances and limits are mirrored as-is into `customers`
(`current_balance`, `credit_limit`). The ETL does **not** "correct" a real over-limit balance — that is
genuine business data — but a reconciliation/validation report lists the 61 (or current count)
over-limit customers so they are visible rather than hidden.

**ProCare fix-by-design.** `customers` carries `credit_limit` and `current_balance` as NON-NULL MONEY
columns (defaulting to 0). Credit enforcement at POS is delegated to the planned hot-path procedure
**`sp_check_credit`** (declared as a Phase 2+ TODO in `../sql/procare-schema.sql`): a sale that would
push `current_balance` past `credit_limit` requires an explicit override by a user holding the credit
permission — the clean-schema equivalent of eStock's `allaw_sale_credit`. This makes the limit an
enforced control instead of an honour-system field.

> Status note: `sp_check_credit`, `sp_create_sale`, `sp_deduct_stock`, `sp_calc_profit`, and
> `sp_transfer_stock` are **specified** in the schema's TODO block and land in Phase 2+ (parallel-run
> on the Elsanta pilot). Until then the rule is enforced in the FastAPI service layer.

---

### 2.4 — Zero/negative stock batches (Normal, but pervasive)

**Defect.** **33,249** batch rows in `Product_Amount` have `amount <= 0` (mostly sold-out batches).
They are not "wrong" historically, but they clutter every naive stock query and can include negatives
produced by the app's non-transactional `UPDATE Product_Amount SET amount = amount - @qty` pattern.

**ETL handling (read-only).** All "current stock" extracts filter `amount > 0`. Zero/negative rows are
not deleted from the mirror's history (movements remain auditable) but are excluded from live-stock
aggregates and from the available-stock definition in §2.2.

**ProCare fix-by-design.** `stock_batches.amount` is guarded by a check constraint:

```sql
amount DECIMAL(18,3) NOT NULL DEFAULT 0 CHECK (amount >= 0)   -- never negative
```

Negative stock is structurally **impossible**. A batch that reaches 0 simply has `amount = 0` and is
filtered out of live-stock views by the `WHERE amount > 0` predicate, while its full history survives in
`stock_movements` (every change recorded as a signed `delta` with a `reason`). This replaces eStock's
separate `Product_amount_Change` audit table (265,249 rows) with a single clean movements ledger.

---

### 2.5 — No foreign keys enforced (Risk)

**Defect.** The audit confirms the eStock database has **zero** foreign keys. Nothing prevents a
`Sales_details` line pointing at a non-existent `sales_id` or `product_id`, an orphaned purchase line,
or stock against a missing store. Orphans accumulate silently.

**ETL handling (read-only).** The ETL validates referential integrity on the way in: rows whose parent
keys do not resolve are quarantined into a reject log (counted, not silently dropped) so the
reconciliation report can account for every source row as either *loaded* or *rejected-with-reason*.

**ProCare fix-by-design.** `../sql/procare-schema.sql` declares **real** foreign keys throughout, e.g.
`sale_lines.sale_id → sales`, `sale_lines.product_id → products`,
`sale_lines.batch_id → stock_batches`, `purchase_lines.purchase_id → purchases`,
`stock_batches.product_id → products`, `stock_batches.branch_id → branches`,
`ledger_entries.branch_id → branches`, and the inter-branch transfer keys
(`stock_transfers.from_branch_id` / `to_branch_id → branches`). Orphans become impossible by
construction.

---

### 2.6 — Eight broken views (Critical)

**Defect.** All **8** views are broken — each references old-schema tables that no longer exist:

| View | Broken — references |
|------|---------------------|
| `item_purchasing` | `Pur_trans_h`, `Stores` (old name) |
| `item_changes_report` | `Item_Catalog`, `Item_changes` |
| `Item_catalog_date` | `Item_Catalog`, `Companys` |
| `item_qty_chang_report` | `Item_Catalog`, `Item_qty_chang` |
| `item_qty_update_report` | `Item_Catalog`, `Item_qty_update` |
| `item_return_purchasing` | `Pur_trans_h_r` |
| `store_convert_report` | `Store_trans_h` |
| `store_item_qty` | `Item_Class_Store`, `Item_Catalog` |

Querying any of them throws.

**ETL handling (read-only).** The ETL reads from **base tables only** (`Sales_header`,
`Sales_details`, `Product_Amount`, `Branches_Product_Amount`, etc.) and never touches these views, so
the breakage cannot reach the mirror.

**ProCare fix-by-design.** None of the broken views are inherited. ProCare reporting is built on clean,
tested views/queries over the new schema (the `../sql/dashboard-queries.sql` patterns), where every
referenced table actually exists.

---

### 2.7 / 2.8 — No stored procedures, all logic trapped in the `.exe` (Structural)

**Defect.** **0** custom stored procedures and **0** custom functions. Stock deduction, profit
calculation, pricing, unit conversion (`sale_unit_change`), and credit checking exist only inside the
eStock `.exe`. The DB cannot enforce or even describe its own rules; reporting must re-implement app
logic by hand and risks diverging from it.

**ETL handling (read-only).** Because the rules are opaque, the ETL never assumes them — it mirrors the
**outcomes** (final `amount`, `total_sell`, `buy_price`, balances) exactly as eStock computed them, and
reconciliation (§3) proves ProCare's re-derived figures (e.g. profit = `Σ total_sell − Σ amount·buy_price`)
match eStock's stored totals before any cutover.

**ProCare fix-by-design.** Business logic lives in two complementary, **testable, versioned** layers:
the Python + FastAPI service layer, and hot-path stored procedures specified in the schema's TODO block
for Phase 2+: `sp_create_sale` (atomic header + lines + FEFO deduction + audit), `sp_deduct_stock`
(per-batch, never negative), `sp_calc_profit` (revenue − cost by period/branch), `sp_check_credit`
(credit-limit enforcement), and `sp_transfer_stock` (atomic Elsanta ↔ Mas-hala transfer). Logic is no
longer locked in a binary.

---

### 2.9 — Missing indexes for reporting (Performance)

**Defect.** eStock lacks indexes tuned for the date-range and per-product/per-branch reporting ProCare
needs; large scans on `Sales_header` and `Product_Amount` are the result.

**ETL handling (read-only).** The ETL reads in keyset/batched ranges and does its heavy aggregation
inside ProCare's own indexed database, so it does not depend on indexes that eStock does not have, and
never adds indexes to eStock (read-only guardrail).

**ProCare fix-by-design.** The clean schema ships purpose-built indexes from day one:
`IX_sales_date` on `sales(sale_date)`, `IX_sales_branch` on `sales(branch_id, sale_date)`,
`IX_sale_lines_sale` on `sale_lines(sale_id)`, `IX_stock_product_branch` on
`stock_batches(product_id, branch_id)`, the filtered `IX_stock_expiry` on `stock_batches(exp_date)
WHERE amount > 0`, and `IX_ledger_branch_date` on `ledger_entries(branch_id, entry_date)`.

---

## 3. eStock remediation snippets — reference only (NOT run by ProCare)

The audit proposes in-place fixes for eStock. They are recorded here so the catalogue is complete, but
**ProCare does not execute them** — they would write to the eStock database, violating the read-only
guardrail. They belong to the (separate, owner-decided) question of whether to patch the legacy system
before retirement.

- **Backfill NULL dates:** `UPDATE Sales_header SET bill_date = insert_date WHERE bill_date IS NULL`.
- **Write off expired stock (after physical count):**
  `UPDATE Product_Amount SET amount = 0 WHERE exp_date < GETDATE() AND amount > 0`.
- **Drop the 8 broken views:** `DROP VIEW IF EXISTS item_purchasing; …` (all eight).
- **Add indexes / FKs:** the audit's `CREATE INDEX` and `ALTER TABLE … ADD CONSTRAINT FOREIGN KEY`
  statements on `Sales_details`, `Purchase_details`, `Product_Amount`.

ProCare achieves every one of these outcomes natively in `../sql/procare-schema.sql` instead.

---

## 4. Reconciliation — proving the mirror is correct before cutover

Cutover is **earned, not scheduled.** Before any branch (Elsanta first, per the pilot strategy) moves to
ProCare, the mirror must match eStock on the same period, computed from the same source rows, for
several consecutive days. Reconciliation runs daily (APScheduler) and writes a pass/fail report.

### 4.1 — What gets reconciled

| Metric | eStock source (read-only) | ProCare source | Match rule |
|--------|---------------------------|----------------|------------|
| Sales count & net revenue per day, per branch | `Sales_header` grouped on `COALESCE(bill_date, insert_date)`, `back <> 'Y'` | `sales` grouped on `sale_date`, returns excluded | Counts equal; money within ±0.01 rounding |
| Sale-line totals | `Sales_details` (`total_sell`) | `sale_lines` | Σ equal per day/branch |
| Gross profit per period/branch | `Σ total_sell − Σ amount·buy_price` over `Sales_details` | same formula over `sale_lines` | Within ±0.01 |
| Live stock quantity per product/branch | `Product_Amount` / `Branches_Product_Amount`, `amount > 0`, not expired | `stock_batches`, `amount > 0`, not expired | Quantities equal |
| Stock value per branch | `Σ amount·buy_price` (available batches) | same | Within ±0.01 |
| Customer balances | `Customer.customer_current_money` (1,197 rows) | `customers.current_balance` | Per-customer equal |
| Vendor balances | `Vendor.vendor_current_money` (87 rows) | `vendors.current_balance` | Per-vendor equal |
| Inter-branch transfers | `Branch_order_header/details`, `Branch_money_order/convert` | `stock_transfers` / `cash_transfers` | Counts & totals equal |
| Row-count parity | Source table counts | Mirror loaded + rejected | loaded + rejected = source |

### 4.2 — Method

1. **Identical period, identical filters.** Both sides use `back <> 'Y'` to exclude returns and
   `COALESCE(bill_date, insert_date)` / `sale_date` as the date axis. The available-stock and FEFO
   rules from §2.2 and §2.4 are applied on both sides so like is compared with like.
2. **Per-branch, not just total.** Every metric is computed per `branch_id` (ELSANTA and MASHALA) and as a
   grand total, since the whole point of the parallel run is one-branch validation.
3. **Full row accounting.** Every source row is either *loaded* or *rejected-with-reason* (orphan FK,
   unparseable value). `loaded + rejected = source count` must hold — no silent drops.
4. **Tolerances.** Integer counts must match exactly. Money is compared to ±0.01 to absorb rounding
   differences between eStock's `money` type and ProCare's `MONEY`/`DECIMAL`.
5. **Drift is investigated, never waved through.** Any mismatch produces a diff (which day, which
   branch, which records) and blocks cutover until explained and resolved.
6. **Green-streak gate.** A branch cuts over only after the reconciliation report is fully green for
   several consecutive days. After cutover that branch's eStock data is frozen as a read-only archive;
   eStock is retired completely once all branches are green (Phase 3).

### 4.3 — Where the queries live

The reconciliation aggregations reuse the audited eStock read patterns (NULL-date coalescing,
return exclusion, FEFO, `amount > 0`) documented in
[`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql) and
[`02-eStock-database-reference.md`](02-eStock-database-reference.md), run side-by-side against the
ProCare schema in [`../sql/procare-schema.sql`](../sql/procare-schema.sql).

---

## 5. Open items (TBD)

- **Titan / Drug-Eye schema** (path `D:\Labirdo`): source of truth for drug **names** and
  **substitution/alternatives** (and interactions/dosing). Its schema is **not yet audited** — its own
  data-quality profile and how its name/substitution data reconciles against eStock `product_name_ar/en`
  and `product_scientific_name` is **TBD**. See [`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md).
- **Read-only SQL login credentials** for the ETL against `192.168.1.2 \ stock`: provisioned out of
  git (`config/connections.json` is git-ignored; only `connections.example.json` is committed) — **TBD**
  at the deployment step.
- **Exact live counts** (74 expired, 61 over-limit, 33,249 zero/negative) are the audit snapshot of
  2026-06-23; the reconciliation job recomputes them on each run, so the gate uses current numbers, not
  the snapshot.
