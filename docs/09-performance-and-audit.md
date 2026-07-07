# Performance over time, post-sync audit & supplier analysis

Once ProCare is running on the new **SQL Server Express** database (see
[`deploy/SQL-SERVER-EXPRESS.md`](../deploy/SQL-SERVER-EXPRESS.md)) and the
read-only eStock mirror has filled it, this layer answers the owner's core
question — **how is the pharmacy doing over time?** — plus the two operational
checks that go with it: *is the synced data clean?* and *what are we buying from
PharmaOverseas?*

Everything here is **derived arithmetic** over ProCare's own clean tables — no
estimates. The same numbers come out of the API, the Reports → **Performance**
screen, and [`sql/performance-analysis.sql`](../sql/performance-analysis.sql)
run directly in SSMS.

## 1. Live sync, then audit

The flow after pointing ProCare at SQL Server Express:

1. **Sync** — fill `estock_source` in `config/connections.json` and run the
   read-only mirror: *Settings → Sync*, or `POST /api/etl/run` (one full load),
   or leave the background sync on (`SYNC_ENABLED=true`). Guardrail unchanged:
   ProCare only ever `SELECT`s from eStock.
2. **Audit** — `GET /api/performance/audit`. A post-sync data-quality report:

   | Check | What it catches |
   |---|---|
   | `negative_stock` | any batch below zero (must be **0** — the schema forbids it) |
   | `expired_in_stock` | expired batches still on hand + their value at cost |
   | `orphan_batches` | stock pointing at a deleted/missing product |
   | `zero_line_sales` | invoices with no line items |
   | `price_below_cost` | active products whose sell price is under cost |
   | `customers_over_limit` | debtors past their credit limit |
   | `walk_in_share` | % of invoices with no registered customer (CRM reach) |

   The response also carries the **data span** (first/last sale, totals) and a
   full **valuation** snapshot (stock at cost & retail, receivables, payables).

## 2. Five-year performance

`GET /api/performance/overview?years=5[&branch_id=]` returns, **per calendar
year** (and a per-month series for charting):

- revenue, COGS, gross profit and **margin %**
- **invoices** (bills) and returns (count + value)
- **active customers** (distinct buyers) and **new customers** (by join date)
- units sold, cash vs card collected, discount given, average bill
- **purchasing spend** and purchase-order count
- **year-over-year revenue growth %**

…plus a `snapshot` of the current position: stock on hand (units, value at cost
and retail), expired-in-stock value, low-stock products, registered customers,
receivables from customers and payables to vendors — the **cash-on-hand /
stock-level** picture.

## 3. Supplier purchasing — PharmaOverseas

`GET /api/performance/vendor?query=pharmaoverseas&years=5` investigates one
distributor: spend / orders / items **per year**, the **top products** bought
from them, the current **payable balance**, their **share of total purchasing**,
and a **ranking of every vendor** for context. `query` matches an English or
Arabic vendor name (or an id); an unknown name returns the ranking so the call
is never a dead end.

## 4. Run it straight on SQL Server Express

[`sql/performance-analysis.sql`](../sql/performance-analysis.sql) reproduces all
of the above in T-SQL. Set the three knobs at the top (`@today`, `@years`,
`@vendor`) and run it in SSMS against the ProCare database — sections A–E map
one-to-one to the API views.

## 5. Access & where it shows

The endpoints are **management-only** (CEO / Manager once `AUTH_ENABLED=true`).
In the UI they render under **Reports → Performance over time**: the current
snapshot, the 5-year trend (chart + table), the audit checklist, and the
PharmaOverseas purchasing breakdown, all branch-scopable and bilingual.

> Offline, the demo seed (`app/db/seed.py`) carries five years of history and
> real purchasing so every screen and query is populated without the live
> database; in production the identical code runs on the synced SQL Server data.
