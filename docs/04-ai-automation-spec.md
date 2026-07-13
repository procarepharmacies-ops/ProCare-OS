# AI & Automation Spec

The intelligence layer that makes ProCare OS more than a modern eStock. Arabic‑first; runs over
ProCare's own clean database (and Titan/Drug‑Eye for clinical checks). Everything here is
**multi‑branch** (Elsanta / Mas-hala / consolidated) and obeys the project guardrails: read‑only against
eStock, advisory clinical output, and no secrets in git.

**Related docs:** [`01-architecture.md`](01-architecture.md) (where this layer sits) ·
[`02-eStock-database-reference.md`](02-eStock-database-reference.md) (source tables) ·
[`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md) (clinical source) ·
[`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md) (read‑time rules) ·
[`07-multi-branch.md`](07-multi-branch.md) (branch model) ·
SQL: [`../sql/procare-schema.sql`](../sql/procare-schema.sql) ·
[`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql).

---

## 4.1 AI Assistant (`PharmacyAI`)

An in‑system smart assistant that answers in Arabic. It reads ProCare's own clean DB (mirrored from
eStock during the transition) and Titan/Drug‑Eye for anything clinical. It is **read‑only**: it can
explain, summarize, forecast, and *draft* a purchase order, but it never commits a write from a chat
prompt.

```python
class PharmacyAI:

    async def chat(self, query: str, context: dict) -> str:
        """
        مساعد ذكي داخل النظام يجيب بالعربي
        أمثلة:
        • "كام باعت الصيدلية امبارح؟"
        • "إيه الأدوية اللي هتخلص الأسبوع الجاي؟"
        • "اعملي طلب شراء للأصناف الناقصة"
        • "وريني أكثر عميل اشترى الشهر ده"
        """

    async def smart_reorder(self) -> list:
        """اقتراح طلبات الشراء تلقائياً — يحلل معدل الاستهلاك، يراعي المواسم،
        يقترح الكميات المثلى، وينبّه قبل النفاد بـ X أيام."""

    async def expiry_risk(self) -> list:
        """تحليل مخاطر انتهاء الصلاحية — يحدد القريب من الانتهاء، يحسب الخسارة
        المتوقعة، ويقترح خطط تصريف (خصومات / أولوية بيع)."""

    async def sales_forecast(self, product_id: int, days: int = 30) -> dict:
        """توقع المبيعات المستقبلية (Prophet / LSTM) — توقعات أسبوعية وشهرية لكل صنف."""

    async def drug_interactions(self, product_ids: list) -> list:
        """فحص التداخلات الدوائية (عبر Titan / Drug‑Eye) — ينبّه على التداخل الخطير
        ويعرض الجرعة الصحيحة."""

    async def customer_insights(self, customer_id: int) -> dict:
        """تحليل سلوك العميل — أكثر الأدوية شراءً، دورية الشراء، عروض مخصصة، تذكير تلقائي."""
```

### How each method works (grounded in the eStock data)

| Method | Reads | Core logic | Notes |
|--------|-------|-----------|-------|
| `chat()` | ProCare views (whitelist) | Claude API → constrained read‑only SQL | Arabic in, Arabic out. See §4.3. |
| `smart_reorder()` | `sales` + `sale_lines` history; `stock_batches` on‑hand; `products.min_stock` | consumption rate × lead time vs available stock; flag below reorder point | Mirrors eStock `Shortcoming` (5,754 below‑minimum rows) and `Product_Vendor` (3,301 product↔supplier links) for who to buy from. Drafts a PO; does not send it. |
| `expiry_risk()` | `stock_batches` (`exp_date`, `amount`, `buy_price`) | batches expiring within a window; expected loss = `amount × buy_price`; suggest discount/priority sale | eStock has **74 expired batches still in stock** and **33,249 zero/negative batches** — read‑time filters (`amount > 0`, not expired) keep this clean. FEFO sets sell priority. |
| `sales_forecast()` | `sales` + `sale_lines` time series per product/branch | **Prophet** weekly/monthly forecast (seasonality, holidays) | LSTM noted as a future option; Prophet is the default. Forecast feeds `smart_reorder()`. |
| `drug_interactions()` | **Titan / Drug‑Eye** (`D:\Labirdo`) | pairwise interaction lookup + dosing for the basket | Schema is **🔴 TBD** — see [`03`](03-titan-drugeye-integration.md). Output is **advisory** to a pharmacist; never blocks a sale. |
| `customer_insights()` | `sales` + `sale_lines` per `customer_id`; `customers` (balance, limit) | top drugs, purchase cadence, targeted offers, refill reminders | eStock has **1,197 customers**; **61 are over credit limit** — insights surface this, POS enforces it. |

**Implementation notes**

- `chat()` uses the **Claude API** to turn Arabic questions into **constrained, read‑only SQL**
  against a whitelist of ProCare views — never a free‑form write. Full guardrails in §4.3.
- `drug_interactions()` / dosing come from **Titan / Drug‑Eye** (`D:\Labirdo`); the Titan schema is
  not yet audited (**TBD**) — see [`03`](03-titan-drugeye-integration.md).
- `sales_forecast()` uses **Prophet** on ProCare's own sales history (`sales` + `sale_lines`).
- Every method accepts an implicit **branch scope** (Elsanta / Mas-hala / consolidated) via `context`;
  results carry `branch_id` so the UI can filter or aggregate.

---

## 4.2 Automation (`PharmacyAutomation`)

```python
class PharmacyAutomation:

    @scheduled(interval="1h")
    async def auto_purchase_order(self):
        """طلب شراء تلقائي عند الوصول للحد الأدنى"""

    @scheduled(cron="0 9 * * *")            # every day 09:00
    async def expiry_alerts(self):
        """تنبيه 90 / 30 / 7 أيام قبل الانتهاء، وقفل بيع المنتهية تلقائياً"""

    @scheduled(cron="0 8 * * *")            # daily report
    @scheduled(cron="0 8 * * 0")            # weekly report
    @scheduled(cron="0 8 1 * *")            # monthly report
    async def auto_reports(self):
        """إرسال التقارير للمدير عبر Email / WhatsApp"""

    async def send_whatsapp(self, phone: str, message: str, pdf=None):
        """إشعارات واتساب: فاتورة للعميل (PDF)، طلب شراء للمورد، تذكير ديون العملاء"""
```

### Schedule & behaviour

| Job | Trigger | What it does | Source tables (ProCare) |
|-----|---------|--------------|--------------------------|
| `auto_purchase_order` | hourly (`interval="1h"`) | recompute reorder points per branch; **draft** a PO per vendor for items below minimum; queue for manager approval | `stock_batches`, `products.min_stock`, `sales`/`sale_lines` (consumption), `vendors` |
| `expiry_alerts` | daily **09:00** (`cron="0 9 * * *"`) | scan batches at **90 / 30 / 7** day horizons; notify per branch + consolidated; **auto‑lock** any product whose only remaining stock is expired | `stock_batches` (`exp_date`, `amount`) |
| `auto_reports` | daily 08:00, weekly Sun 08:00, monthly 1st 08:00 | KPI pack to the manager (revenue, profit, top sellers, debtors, expiry, low‑stock) via Email / WhatsApp | `sales`, `sale_lines`, `customers`, `vendors`, `stock_batches`, `ledger_entries` |
| `send_whatsapp` | on demand (called by other jobs) | customer invoice (PDF), supplier PO, customer debt reminder | n/a — delivery channel |

**Implementation notes**

- Scheduling via **APScheduler** inside the FastAPI service (Windows Task Scheduler is the fallback
  if the service is not run as a long‑lived daemon). Cron expressions above are the source of truth.
- Alerts and reports are produced **per branch (Elsanta, Mas-hala) and consolidated** — see §4.5.
- WhatsApp via the **WhatsApp Cloud API** (a gateway is an acceptable alternative; final choice is a
  config decision, not a code change). PDFs rendered with **WeasyPrint / ReportLab**.
- **Expiry auto‑lock:** a product whose only on‑hand stock is expired is blocked from sale at the POS.
  This directly fixes the eStock problem of **74 expired batches still sellable**. Locking writes an
  audit row to `stock_movements` (`reason = 'writeoff'`/`'lock'`); it never edits eStock.
- Email via **SMTP**. All notification recipients/branch routing live in config, not in code.
- `auto_purchase_order` only **drafts** — a human approves before anything is sent to a supplier
  (mirrors eStock's empty `Order_header`/`Order_details`: purchase orders were a manual step there).

---

## 4.3 Constrained text‑to‑SQL (the safe core of `chat()`)

The Arabic assistant turns natural language into SQL, but under tight constraints so a chat prompt can
never mutate data or read outside its lane.

**Pipeline**

1. **Intent + entities** — the Claude API parses the Arabic question (date range, branch, product,
   customer, metric).
2. **Constrained generation** — Claude emits SQL against a **read‑only whitelist of ProCare views**
   only (e.g. `vw_daily_sales`, `vw_expiry_risk`, `vw_low_stock`, `vw_customer_debtors`,
   `vw_top_products`). No base‑table writes, no DDL, no `EXEC`.
3. **Static validation** — before execution: must be a single `SELECT`; reject `INSERT/UPDATE/DELETE/
   MERGE/DROP/ALTER/EXEC/;`‑stacking and any object not on the whitelist; enforce a `TOP`/row cap and
   a query timeout.
4. **Execution** — runs under the **read‑only DB login** (the same principle as the eStock ETL login),
   so even a bypass cannot write.
5. **Answer** — results are summarized back in Arabic, with the branch and date range echoed.

**Why this is safe by construction**

- The login has no write permission, so the worst case of a bad generation is a failed/empty read.
- The whitelist means the model cannot reach HR salaries, password hashes, or raw ledger rows it
  shouldn't.
- This is the same separation eStock never had: in eStock **all business logic lived in the `.exe`**
  with **0 stored procedures and 0 functions** in the DB. ProCare keeps logic in versioned code and
  exposes only curated read views to the assistant.

> Model/SDK details (model IDs, pricing, prompt caching, tool use) are intentionally **not pinned**
> here — treat them as config and confirm against the current Claude API reference at integration
> time rather than hard‑coding a model string.

---

## 4.4 Where the data comes from

| Feature | Reads from | Key tables / objects |
|---------|-----------|----------------------|
| KPIs, dashboards, `auto_reports` | ProCare own DB (mirrored from eStock during transition) | `sales`, `sale_lines`, `stock_batches`, `ledger_entries` (eStock: `Sales_header` 95,088 / `Sales_details` 183,906) |
| `smart_reorder` / `auto_purchase_order` | ProCare own DB | `stock_batches`, `products.min_stock`, `vendors`, consumption from `sale_lines` (eStock: `Shortcoming` 5,754, `Product_Vendor` 3,301) |
| `expiry_risk` / `expiry_alerts` | ProCare own DB | `stock_batches` (`exp_date`, `amount`, `buy_price`) (eStock: `Product_Amount` 35,404) |
| `sales_forecast` | ProCare own DB (history) | `sales` + `sale_lines` time series (Prophet) |
| `customer_insights`, debt reminders | ProCare own DB | `customers`, `sales`, `sale_lines`, `ledger_entries` (eStock: `Customer` 1,197) |
| `drug_interactions`, substitution, dosing | **Titan / Drug‑Eye** (`D:\Labirdo`) | Interactions / Substitutions / Dosing tables — **🔴 schema TBD** (see [`03`](03-titan-drugeye-integration.md)) |
| Notifications | ProCare own DB + WhatsApp/SMTP | recipients & routing from `config/connections.json` (git‑ignored) |

**Provenance & data‑quality.** During Phase 1 the ETL mirrors eStock (`stock` on `192.168.1.2`)
read‑only into ProCare's clean schema, applying the rules from [`05`](05-data-quality-and-fixes.md):
`COALESCE(bill_date, insert_date)`; exclude returns (`back <> 'Y'`); available stock = `amount > 0`
AND not expired; FEFO = `ORDER BY exp_date ASC`. After cutover, every feature above reads ProCare's
own DB only. All read‑query patterns are seeded in
[`../sql/dashboard-queries.sql`](../sql/dashboard-queries.sql).

> **Credentials are TBD / out of git.** The read‑only eStock login and the Titan connection string are
> filled into `config/connections.json` (git‑ignored); only `connections.example.json` is committed.

---

## 4.5 Per‑branch + consolidated alerting

ProCare runs two physical branches — **MASHALA (مسهله)** and **ELSANTA (السنطه)** — and every
operational row carries a `branch_id` (see [`07-multi-branch.md`](07-multi-branch.md)). The
intelligence layer respects that end to end:

- **Per branch.** `expiry_alerts`, `auto_purchase_order`, low‑stock, debtors and `auto_reports` all
  run **once per branch**, so Elsanta's manager gets Elsanta's numbers and Mas-hala's gets Mas-hala's.
- **Consolidated.** A group‑level roll‑up (mirroring eStock's branch ledger `Gedo_branches`, 9,271
  rows) combines both branches for the owner.
- **Transfers.** Reorder logic is transfer‑aware: if Mas-hala is overstocked on an item Elsanta is short
  on, the suggestion can be an **inter‑branch transfer** (`stock_transfers`) instead of a new PO
  (eStock: `Branch_order_header` 8,204 / `Branch_order_details` 61,872).
- **Routing.** Which manager/phone/email receives which branch's alerts is configuration, not code.

This matches the Phase‑2 plan to pilot on **Elsanta** first, then cut Mas-hala over — the same alerting
code serves one branch, the other, or both combined without change. See
[`06-roadmap.md`](06-roadmap.md).

---

## 4.6 Guardrails (recap, non‑negotiable)

1. **Read‑only on eStock.** Nothing in this layer writes to the eStock `stock` DB — ETL and the
   assistant both use a dedicated read‑only login.
2. **Constrained text‑to‑SQL.** `chat()` emits a single `SELECT` against a view whitelist only
   (§4.3); writes are impossible by permission and by validation.
3. **Clinical output is advisory.** `drug_interactions()` shows the pharmacist a warning + correct
   dose; it **never silently blocks a sale**.
4. **Auto‑PO is draft‑only.** A human approves before any order reaches a supplier.
5. **Secrets out of git.** All connection strings and notification credentials live in
   `config/connections.json` (ignored); only the example file is committed.
