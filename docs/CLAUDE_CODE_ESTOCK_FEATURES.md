# eStock — Business Logic & Hidden Features (for Claude Code)

Supplement to `CLAUDE_CODE_ESTOCK_STRUCTURE.md`. This covers the **behavioral /
client-driven features** the user described that are NOT obvious from a static
schema dump: the notification system, F-keys, the moving expiry ribbon, the
FEFO auto-pick, the shortage notebook (كشكول النواقص), F2 branch-stock lookup, and
how features get hidden per employee. Every table/column named below was verified
live against the eStock DB (mashala) — these are the REAL backing structures.

---

## 1. THE SHORTAGE NOTEBOOK — كشكول النواقص (`Shortcoming`)

**Table confirmed:** `Shortcoming` (5,756 rows on mashala), plus `Branches_shortcoming`
(branch-scoped). Columns: `id, class, product_id, general, notes, store_id,
insert_uid, insert_date, update_uid, update_date, vendor_id, amount`.

**What it is:** when a sale (or branch transfer) cannot be fully filled, the
product is auto-added to the shortage notebook. Real `notes` values seen in the
data: `'فاتورة البيع'` (sales invoice) and `'تحويل لفرع'` (branch transfer). So the
trigger is: **during a sale, if requested qty > available stock, write a
`Shortcoming` row** (note = reason) so purchasing/management can follow up.

**Build in ProCare:**
- Add a `shortcomings` table (product_id, store_id/branch, reason, qty_needed,
  qty_available, notes, created_by, created_at).
- At POS, after FEFO allocation, if `requested > allocated`, auto-insert a
  shortage row (do NOT block the sale — sell what's available, log the rest).
- Surface it as a "النواقص" screen + a count badge on the dashboard.
- Mirror `Shortcoming` + `Branches_shortcoming` read-only so history shows.

---

## 2. FEFO AUTO-PICK + NEAR-EXPIRY (already in schema, confirm logic)

`Product_Amount` holds one row per (product × store × vendor × expiry) batch,
ordered by `exp_date`. **Verified:** a single product (e.g. 21971) has batches
2022-03, 2022-04, 2022-06, 2022-07, 2022-08, 2022-10 — multiple expiries.

**Rule (user requirement, explicit):** if stock for a product has 2+ expiry
batches, the sale MUST consume the **nearest expiry first** (FEFO). At POS, when
the user picks a product, the system should:
1. `SELECT … FROM Product_Amount WHERE product_id=? AND store_id=? AND amount>0
   ORDER BY exp_date ASC` and allocate from the top batch(es).
2. If the top batch is insufficient, spill into the next-nearest expiry.
3. **Show the chosen expiry** on the sale line (`Sales_details.exp_date` already
   stores it — keep that).

The "moving ribbon about near-expiry during sale" is a UI banner: while ringing
up, if the allocated batch's `exp_date` is within N days, flash a warning. Backed
by the same `Product_Amount.exp_date` query.

---

## 3. THE MOVING RIBBON / NOTIFICATIONS (شريط متحرك + تنبيهات)

**Tables confirmed:**
- **`News_bar`** (`id, news_id, news, insert_date, syndicate_id, company_id,
  news_insert_date, deleted, deleted_date`) — the scrolling announcement ticker
  shown on the POS/main screen. `deleted` soft-removes a message. (Currently 0
  active on mashala — but the channel exists.)
- **`Flag`** (`f_id, f_code, f_name`) — notification CATEGORIES. Values seen:
  `1=نقطة البيع` (POS), `2=الخزينة` (treasury), `3=البنك` (bank), `4=مصروفات`
  (expenses), `5=مورد` (vendor). This is the routing/channel taxonomy for alerts.

**Build in ProCare:**
- A notification/announcement feed sourced from `News_bar` (respect `deleted`).
- An alert center categorized by `Flag` (POS / treasury / bank / expenses / vendor).
- The near-expiry + low-stock + shortage events (§1, §2) post here too.

---

## 4. F2 = BRANCH STOCK LOOKUP (during product search)

This is a **client hotkey**, not a table. When the cashier searches a product
(at POS or search screen) and presses **F2**, a popup shows that product's stock
across ALL branches/stores — backed by querying `Product_Amount` (main) +
`Branches_Product_Amount` (branch replicas) for the same `product_id`.

**Build in ProCare:**
- A `GET /api/products/{id}/branch-stock` endpoint that returns, per branch/store,
  the available `amount` (sum of `Product_Amount.amount` where `amount>0`, grouped
  by branch/store, ignoring expired batches per FEFO).
- Wire the POS product-search modal's **F2** key to open this popup.
- Mirror `Branches_Product_Amount` so cross-branch stock is available.

---

## 5. HOTKEYS / KEYS DURING SALES & PURCHASING

The eStock client uses function keys (F1–F12) and shortcuts at POS and in
purchasing. From the schema + the user's description, the documented ones are:
- **F2** — view product stock in other branches (§4).
- **FEFO auto-pick** happens on product selection (§2) — no key, automatic.
- **Auto-add to shortage notebook** on unmet qty (§1) — automatic, no key.
- The fine-grained per-action permissions are gated by **`EMP_CONTROL`** (§6).

When building ProCare's POS, define an explicit hotkey map (F-keys for: search,
branch-stock, discount, customer-select, hold/cash, shortage-add, returns) and
**make it visible in the UI** (a help strip) — eStock hides them, which is a UX
pain the user called out.

---

## 6. HIDDEN FEATURES (why some are invisible to the user)

eStock hides screens/actions per employee via the **`EMP_CONTROL`** table — one
row per `emp_id` with **198 boolean columns** (A, A1…A35, B, B1…B34, C, C1…C7,
D, D1…D11, E, E1…E8, F, F1…F28, G, G1…G31, H, H1…H2, I, I1…I21, J, J1…J25). Each
column gates a screen or action (e.g. `emp_add_product`, `emp_edit_sell_price`,
`emp_change_cash_disk`, `allaw_sale_credit`, `allaw_sale_delivery`, `emp_del_vendor`).

**This is almost certainly why features are "hidden from you"**: your employee
record's `EMP_CONTROL` row has those flags = 0. The feature EXISTS in the program
and DB; it's just disabled for your login.

**Build in ProCare:**
- Model roles/permissions explicitly (don't copy the 198-letter matrix literally —
  group into role flags: cashier / manager / CEO per `CLAUDE.md`).
- A **"hidden features" discovery screen**: list every permission flag and whether
  the current user has it ON — so nothing is silently invisible. This directly
  answers the user's request to "find hidden features."
- Keep `EMP_CONTROL` mirrored read-only so ProCare can show what eStock granted.

---

## 7. WHAT TO IMPLEMENT (hand-off)

1. **Shortage notebook** (`shortcomings` table + auto-insert at POS on unmet qty +
   "النواقص" screen + dashboard badge). Mirror `Shortcoming`/`Branches_shortcoming`.
2. **FEFO enforcement** at POS: allocate nearest-expiry batch first; show chosen
   `exp_date` on the line; near-expiry warning banner during sale.
3. **Notification center + ribbon**: source `News_bar` (respect `deleted`) +
   categorize by `Flag` (POS/treasury/bank/expenses/vendor); post expiry/low-stock/
   shortage events there.
4. **F2 branch-stock popup**: `GET /api/products/{id}/branch-stock` over
   `Product_Amount` + `Branches_Product_Amount`; bind F2 in the POS search modal.
5. **Explicit, visible hotkey map** at POS (search/F2/discount/customer/hold/cash/
   shortage/returns) — surface it in the UI, don't hide it.
6. **Permissions discovery screen**: show all role flags for the current user
   (model from `EMP_CONTROL`) so hidden features are discoverable, not invisible.
7. Mirror the backing tables read-only (SELECT only — never write to eStock).

All of this is consistent with the mirror mapping in
`CLAUDE_CODE_ESTOCK_STRUCTURE.md` §12 and the chunked-WAN-fetch rule in
`CLAUDE_CODE_ETL_TASK.md` §4.
