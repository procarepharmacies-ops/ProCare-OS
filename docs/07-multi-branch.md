# Multi‑Branch Model — Elsanta + Mas-hala (السنطه + مسهله)

ProCare OS runs the same two physical branches as eStock and replicates exactly how eStock
connects them — but on a **clean, independent database** that fixes every eStock data‑quality
problem from day one (real foreign keys, indexes, NON‑NULL dates, no broken views, stock that can
never go negative).

> **Scope note.** This document covers the multi‑branch model only: the two branches, the mapping
> from eStock Module 7 to the ProCare clean schema, the design principles, the stock‑ and
> cash‑transfer flows, and per‑branch + consolidated reporting. For the overall architecture see
> [`01-architecture.md`](01-architecture.md); for the full eStock table inventory see
> [`02-eStock-database-reference.md`](02-eStock-database-reference.md); for the data‑quality rules
> that every ETL read must honour see [`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md).

---

## 1. The two branches

| Branch | Arabic | Role |
|--------|--------|------|
| **Mas-hala** | مسهله | Primary branch / main warehouse |
| **Elsanta** | السنطه | Secondary branch — recommended **pilot** for the Phase‑2 parallel run |

eStock confirms exactly **two** branches in its `Branches` table (2 rows, 52 columns of per‑branch
config each). Both branches live on the same LAN host (`192.168.1.2`); eStock itself keeps a single
physical `Stores` row and models the second location through its Module 7 (`Branches_*`) tables.

ProCare seeds these two branches deterministically so every operational row can reference them by a
clean integer key (see [`../sql/procare-schema.sql`](../sql/procare-schema.sql)):

```sql
INSERT INTO branches (name_ar, name_en) VALUES (N'مسهله', N'Mas-hala');     -- branch_id = 1
INSERT INTO branches (name_ar, name_en) VALUES (N'السنطه',  N'Elsanta');  -- branch_id = 2
```

> **TBD.** eStock's internal branch identifiers (its own numeric `branch_id` / `store_id` values
> and the meaning of the 52 `Branches` columns) are read and confirmed during the Phase‑1 mirror.
> Until then, ProCare treats `branch_id = 1` as Mas-hala and `branch_id = 2` as Elsanta and records the
> eStock → ProCare key mapping in the ETL layer. The pilot recommendation (Elsanta) is an
> operational choice, not anything encoded in eStock.

---

## 2. How eStock connects the branches (Module 7) — and what ProCare replicates

eStock **Module 7: Branches / Multi‑Store** is the source of truth for branch behaviour. ProCare
mirrors each concern with a clean, indexed, FK‑backed equivalent. Row counts below are from the
eStock audit (2026‑06‑23) and show what real data exists today.

| Concern | eStock table(s) | Rows | ProCare clean equivalent |
|---------|-----------------|-----:|--------------------------|
| Branch definitions | `Branches` (52 cols) | 2 | `branches` (`branch_id`, `name_ar`, `name_en`, `is_active`) |
| Per‑branch stock | `Branches_Product_Amount` (mirrors `Product_Amount`) | 121,625 | `stock_batches` (`product_id` + `branch_id` + `exp_date` → `amount`, `buy_price`, `sell_price`) |
| Stock change audit | `Product_amount_Change` (Module 1) | 265,249 | `stock_movements` (`batch_id`, `branch_id`, `delta`, `reason`, `ref_id`) |
| Inter‑branch stock transfers | `Branch_order_header` / `Branch_order_details` | 8,204 / 61,872 | `stock_transfers` (header) + `stock_transfer_lines` |
| Inter‑branch cash transfers | `Branch_money_order` (orders) / `Branch_money_convert` (executed) | 1,102 / 1,098 | `cash_transfers` (single table; `status` sent→received) |
| Branch financial ledger | `Gedo_branches` | 9,271 | `ledger_entries` (every row carries `branch_id`) |
| Branch sales / purchases / parties | `Branches_sales_header/details`, `Branches_purchase_header/details`, `Branches_customer/Vendor` | 0 | `sales` / `purchases` / `customers` / `vendors`, each branch‑tagged via `branch_id` |

Notes on the mapping:

- **`Branches_Product_Amount` (121,625 rows) is the live per‑branch inventory** and mirrors the
  single‑store `Product_Amount` table (35,404 rows, 16 columns). ProCare collapses both into one
  clean table, `stock_batches`, keyed by `(product_id, branch_id, exp_date)` and indexed on
  `(product_id, branch_id)` and on `exp_date WHERE amount > 0`.
- **eStock splits cash transfers into two tables** — `Branch_money_order` (the request, 1,102 rows)
  and `Branch_money_convert` (the executed conversion, 1,098 rows). ProCare folds both into a single
  `cash_transfers` row whose `status` moves `sent → received`, so the request and the execution are
  one auditable record rather than two loosely‑coupled tables.
- **The `Branches_sales_*`, `Branches_purchase_*`, and `Branches_customer/Vendor` tables are empty
  (0 rows)** in eStock — they are replication targets that were never populated. ProCare does **not**
  create parallel per‑branch sales/purchase/party tables; instead every `sales`, `purchases`,
  `customers`, and `vendors` row carries a `branch_id` column directly (see §3.1). This is cleaner
  and avoids the duplication eStock left half‑built.
- **`Gedo_branches` (9,271 rows)** is the branch‑level financial ledger; ProCare's `ledger_entries`
  replaces it with explicit `debit`/`credit` columns and a mandatory `branch_id`.

> **GUARDRAIL.** ProCare **never writes to the eStock DB**. All Module 7 data above is read
> **read‑only** through a dedicated read‑only SQL login during Phases 1–2, then ProCare becomes the
> sole system of record at cut‑over (Phase 3). See [`01-architecture.md`](01-architecture.md) and
> [`06-roadmap.md`](06-roadmap.md).

---

## 3. Design principles

### 3.1 Every operational row carries a `branch_id`
Stock, sales, purchases, stock movements, and ledger entries are all branch‑stamped. Nothing is
branch‑ambiguous. In the clean schema this is enforced structurally:

| Table | `branch_id` | Constraint |
|-------|-------------|------------|
| `stock_batches` | `branch_id INT NOT NULL` | `REFERENCES branches(branch_id)` |
| `stock_movements` | `branch_id INT NOT NULL` | `REFERENCES branches(branch_id)` |
| `sales` | `branch_id INT NOT NULL` | `REFERENCES branches(branch_id)`, indexed `(branch_id, sale_date)` |
| `purchases` | `branch_id INT NOT NULL` | `REFERENCES branches(branch_id)` |
| `ledger_entries` | `branch_id INT NOT NULL` | `REFERENCES branches(branch_id)`, indexed `(branch_id, entry_date)` |

(Master data that is genuinely shared — `products`, `companies`, `product_groups`, `units` — is
deliberately **not** branch‑scoped; only operational/transactional rows are.)

### 3.2 Stock is per‑branch **and** per‑batch
A product can have different quantities — and even entirely different batches with different expiry
dates — in Elsanta vs Mas-hala. The grain is one row per `(product_id, branch_id, exp_date)` in
`stock_batches`. Two invariants the eStock DB does not enforce but ProCare does:

- **`amount` can never go negative** — `CHECK (amount >= 0)`. (eStock today has **33,249
  zero/negative batches**; ProCare makes that state impossible.)
- **FEFO ordering is preserved per branch** — `ORDER BY exp_date ASC` within a branch, so the
  oldest‑expiring batch at *that* branch is consumed first. (eStock has **74 expired batches still
  in stock**; ProCare's expiry index `IX_stock_expiry … WHERE amount > 0` plus the daily expiry job
  prevent that — see [`04-ai-automation-spec.md`](04-ai-automation-spec.md).)

### 3.3 Stock transfers are atomic and audited
A Mas-hala → Elsanta transfer decrements the source branch and increments the destination branch under a
**single `transfer_id`**, inside one database transaction. Both legs are written to
`stock_movements` (one `delta < 0` at the source, one `delta > 0` at the destination), each tagged
with `reason = 'transfer'` and `ref_id = transfer_id`. If any step fails, the whole transfer rolls
back — stock is never lost or double‑counted. This is the job of the planned `sp_transfer_stock`
stored procedure (see the TODO block in [`../sql/procare-schema.sql`](../sql/procare-schema.sql)).

### 3.4 Cash transfers mirror stock transfers
A cash transfer is a request plus an execution, both ledgered. eStock models this with two tables
(`Branch_money_order` + `Branch_money_convert`); ProCare uses one `cash_transfers` row whose
`status` advances `sent → received`, with a matching pair of `ledger_entries` (debit at the sender,
credit at the receiver) so the two branch ledgers always reconcile.

### 3.5 Batch identity travels with every transfer
`stock_transfer_lines` carries `exp_date` alongside `product_id` and `amount`. The expiry date moves
with the goods, so FEFO and expiry tracking stay correct **across** branches — the units received at
Elsanta keep the same expiry they had at Mas-hala and are not silently re‑dated.

### 3.6 Consolidated by default, drill‑down on demand
Every report and dashboard can show a **single branch** or **both combined**. The UI carries a
branch switcher — **Elsanta / Mas-hala / All** — and the selection persists per user alongside the
language (Arabic default / English) and theme (light default / dark) preferences described in
[`01-architecture.md`](01-architecture.md).

---

## 4. Stock‑transfer flow (Mas-hala → Elsanta)

Tables touched: `stock_transfers`, `stock_transfer_lines`, `stock_batches`, `stock_movements`.

```
1. Elsanta requests 50 units of product X
   → stock_transfers (from=Mas-hala, to=Elsanta, status='requested')
   → stock_transfer_lines (product_id=X, amount=50, exp_date=<batch>)

2. Mas-hala approves & ships
   → stock_transfers.status = 'in_transit'
   → Mas-hala  stock_batches.amount −50   (FEFO: oldest exp_date at Mas-hala first)
   → stock_movements (batch_id=<Mas-hala batch>, branch_id=Mas-hala,
                      delta=−50, reason='transfer', ref_id=transfer_id)

3. Elsanta receives
   → stock_transfers.status = 'received'
   → Elsanta stock_batches.amount +50  (same product_id + same exp_date)
   → stock_movements (batch_id=<Elsanta batch>, branch_id=Elsanta,
                      delta=+50, reason='transfer', ref_id=transfer_id)

4. Result: 2 audit rows, one transfer_id, fully reconcilable.
```

Key points:
- Steps 2–3 run inside a **single atomic transaction** (`sp_transfer_stock`); the transfer is never
  half‑applied.
- The `exp_date` recorded on the transfer line is the batch shipped, so the destination batch is
  created/updated with the **same expiry** — FEFO integrity holds at both branches.
- eStock's equivalent is `Branch_order_header` (8,204) + `Branch_order_details` (61,872): a high‑use
  feature, so this flow must be correct and fast.

---

## 5. Cash‑transfer flow (Branch A → Branch B)

Tables touched: `cash_transfers`, `ledger_entries`.

```
1. Branch A sends cash to Branch B
   → cash_transfers (from=A, to=B, amount, status='sent')
   → ledger_entries (branch_id=A, credit=amount,
                     ref_type='transfer', ref_id=cash_transfer_id)   -- cash leaves A

2. Branch B confirms receipt
   → cash_transfers.status = 'received'
   → ledger_entries (branch_id=B, debit=amount,
                     ref_type='transfer', ref_id=cash_transfer_id)   -- cash arrives at B
```

Both legs reference the same `cash_transfer_id`, so the two branch ledgers reconcile and the
consolidated cash position is always correct. This replaces eStock's split
`Branch_money_order` (1,102) / `Branch_money_convert` (1,098) pair, whose ~4‑row gap between
"ordered" and "converted" is exactly the kind of loose coupling the single‑row `status` model
eliminates.

---

## 6. Reporting

### 6.1 Per branch
Filtered by `branch_id`: sales, gross profit, stock value, debtors, and expiry — for Mas-hala alone or
Elsanta alone. The supporting indexes (`IX_sales_branch`, `IX_ledger_branch_date`,
`IX_stock_product_branch`) make these filters fast.

### 6.2 Consolidated (the group picture)
Elsanta + Mas-hala combined — the owner's whole‑business view. This mirrors what eStock's
`Gedo_branches` ledger was meant to provide, now backed by `ledger_entries` with explicit
debit/credit columns. Sales/profit consolidations honour the eStock‑derived data‑quality rules:
`COALESCE(bill_date, insert_date)` for dating, and **exclude returns** (`back <> 'Y'`) — see
[`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md).

### 6.3 Transfer reports
What moved between branches over any period:

- **Stock transfers** — from `stock_transfers` + `stock_transfer_lines`, reconciled against the
  paired `stock_movements` audit rows (`reason='transfer'`).
- **Cash transfers** — from `cash_transfers`, reconciled against the paired `ledger_entries`.

Because each transfer's two legs share one id, these reports can prove that nothing was lost in
transit — every shipped unit and every sent pound has a matching received row.

---

## 7. Open items (TBD)

- **eStock `Branches` 52‑column semantics** and the eStock→ProCare branch‑key mapping — resolved
  during the Phase‑1 mirror.
- **Hot‑path stored procedures** `sp_transfer_stock` (atomic stock transfer) and `sp_create_sale`
  (FEFO deduction + audit) — listed as Phase‑2+ TODOs in
  [`../sql/procare-schema.sql`](../sql/procare-schema.sql).
- **Titan / Drug‑Eye** at `D:\Labirdo` supplies product names and substitutions only; its schema is
  not yet audited and has no bearing on the branch model — see
  [`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md).

See the full clean schema in [`../sql/procare-schema.sql`](../sql/procare-schema.sql) and the
read‑only dashboard queries in [`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql).
