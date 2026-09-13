# ProCare OS — Owner Gap Plan (2026-09-10)

Audit of the 17 items raised by the owner on 2026-09-10, checked against the
code as it stands on disk, not against `task_plan.md`.

> **Correction (2026-09-10, later):** an earlier draft of this document said
> "working tree clean". That was wrong — only `src/frontend` had been checked.
> The tree carries substantial uncommitted work; see **§0.5**, which outranks
> every item in this plan.

**Why that distinction matters:** `task_plan.md` reads 76 done / 2 open, but the
owner is reporting gaps. In most cases both are true — the *backend* landed and
the *UI surface* did not. Each item below says which.

Legend: **✅ exists** · **🟡 partial** · **🔴 missing** · **⛔ blocked / cannot be done as asked**

---

## 0. What I verified today

| Check | Result |
|---|---|
| Frontend build | Clean. 16/16 routes 200, zero errors/warnings, 244 MB stale `.next` cleared |
| Backend | Healthy on `127.0.0.1:8100`, SQL Server, 53,672 products seeded |
| Same-origin API proxy | Working — `/api/health` via :3100 matches backend directly |
| Auth | Enforced server-side (`/api/branches` → `401 no_token`) |
| Tunnel | `procare.prospices.net` live, **behind Cloudflare Access** (team `procarepharmacy`, tunnel `731be1ed-eb1a-4cce-97be-a6f8f292e35a`) |
| Duplicate repo | `ProCare-OS-main` deleted — one copy remains |

**Not verifiable without a login:** every report and dashboard number. All 14
endpoints the `/reports` page calls sit behind `auth_guard`. Task **R0** below
exists purely to close that gap before anyone estimates the rest.

---

## 0.5 P0 — uncommitted Arabic data-corruption fix is sitting in the working tree

This is the most important thing found today and it is **not** on the owner's
list. Four tracked files are modified and never committed:

| File | Change |
|---|---|
| `app/db/migrate.py` | **+249 lines** — new `ensure_arabic_columns_unicode()` plus MSSQL column/index introspection helpers |
| `app/db/models.py` | ~107 lines — `String(n)` → `Unicode(n)` across every `name_ar` and free-text column |
| `app/main.py` | +7 — calls `ensure_arabic_columns_unicode(engine)` in the startup lifespan, deliberately **before the sync thread starts** |
| `app/services/agent_orchestration.py` | mine, today (B2) |

Plus untracked repair tooling: `tools/repair_arabic.py`,
`tools/run_arabic_migration.py`, `stderr_test.py`, `start-procare.bat`.

**What it fixes**, in the migration's own words: this database's collation is
`SQL_Latin1_General_CP1_CI_AS`, which has **no Arabic codepage**, so a `VARCHAR`
column *silently stores `?` in place of every Arabic character at write time*.
The comment records damage already measured on the live database:

- `customers.name_en` — **13,116 rows** holding `?` runs
- `vendors.name_en` — **15,480 rows**
- `products.name_en` — **4,035 rows**

eStock's own `*_en` fields are filled by pharmacists typing Arabic into
whichever box is in front of them, so the "English" columns carry Arabic too.

**Why this is P0 and blocks the rest of the plan:**

1. **It is live data loss, ongoing.** Until the columns are `NVARCHAR`, every
   sync cycle writes another batch of `?`. The characters are not recoverable
   from ProCare — only by re-reading eStock.
2. **It runs at startup and is uncommitted.** `ensure_arabic_columns_unicode`
   is wired into the lifespan, so whether it has already run against production
   depends on when the backend was last restarted relative to the file being
   saved. **That must be established before anyone restarts the backend** —
   including for B1, which needs a restart to take effect.
3. **A month of work is unprotected.** None of it is committed and there is
   also a `stash@{0}` from 2026-08-07 (`pre-main-update: stocktaking WIP`).
   A bad `git` command loses all of it.

### P0.1 RESULT (verified 2026-09-11, read-only)

**The schema migration is FULLY APPLIED.** Against database `ProCare`
(collation `SQL_Latin1_General_CP1_CI_AS`, confirmed — no Arabic codepage):

```
85 target columns:  85 already NVARCHAR/NTEXT · 0 still VARCHAR · 0 absent
VERDICT: FULLY APPLIED
```

So **no new corruption is being written**, and **restarting the backend is safe**
— `ensure_arabic_columns_unicode` is idempotent and will find nothing to do.

**But the existing damage is far worse than the migration comment recorded**,
because widening a column does not rewrite the values already in it:

| column | rows | damaged (`??` runs) | share |
|---|---:|---:|---:|
| `customers.name_ar` | 198,393 | **193,769** | **97.7%** |
| `customers.name_en` | 198,393 | 12,900 | 6.5% |
| `vendors.name_ar` | 37,415 | **37,323** | **99.8%** |
| `vendors.name_en` | 37,415 | 15,480 | 41.4% |
| `employees.name_ar` | 32 | 4 | 12.5% |
| `products.name_ar` | 53,673 | 0 | clean |
| `products.name_en` | 53,673 | 0 | clean |

Two things follow, and they change the shape of P0:

1. **Products have already been repaired.** The migration comment cited
   `products.name_en` at 4,035 damaged rows; it now reads **0**. `vendors.name_en`
   still matches its recorded 15,480 exactly, and `customers.name_en` has drifted
   only 13,116 → 12,900. So a repair pass ran over **products only** and stopped.
   That is good news: it proves `repair_arabic.py` works on live data.
2. **The Arabic-name columns were never in the original count.** Nobody had
   measured `name_ar`. Customer and vendor Arabic names — the fields staff
   actually search by — are **97.7% and 99.8% destroyed**, ~231,000 rows.

**Revised P0 remainder:**

- [x] **P0.1 · Establish whether the migration has already run** — done, fully
      applied; backend restart is safe.
- [ ] **P0.2 · Commit or branch the work as-is**, before anything else touches
      the tree. It is unreviewed but it is also the only copy.
- [x] **P0.3 · Quantify current damage** — done, table above. Baseline:
      **~231,000 damaged rows**, concentrated in `customers.name_ar` (193,769)
      and `vendors.name_ar` (37,323).
- [ ] **P0.4 · Repair customers + vendors** with `repair_arabic.py`, off-peak.
      The schema half is done; this is the data half, and it is the only
      remaining source of user-visible breakage. Scope it to the five damaged
      columns — products need nothing. Re-run the damage query afterwards as
      the acceptance test: every `runs` count must reach 0.
      **Read the script before running it** — it writes to production, and it
      is uncommitted and unreviewed (P0.2).
- [ ] **P0.5 · Decide the `stash@{0}` question** — restore that 2026-08-07
      stocktaking WIP or drop it deliberately. Leaving it is how it gets lost.

---

## 1. Findings per item

### 1.1 e-Stock clone — menus and pages incomplete 🟡
The data layer is done; the screens are not. `progress.md` (2026-08-26) records
**114 eStock tables at 100% coverage** — 28 dedicated models + 86 in
`estock_raw_mirror`. But `reports-daily/page.js` carries the telling comment:

> *"The reusable REPORT PATTERN for the other **119 reports**"*

So eStock exposes ~120 reports and ProCare has built roughly 6 screens against
them. **The gap is UI surface, not data.**

Also still open from the mirror work: the **first fill of the 10 largest tables
has never been run** into production (~2M rows, off-peak job, procedure in
`docs/RAW-MIRROR-FIRST-FILL.md`).

### 1.2 Redeem customer points / loyalty 🟡
`app/services/loyalty.py` and `app/api/crm.py` exist; Phase 3 logged "Loyalty
tiers + CRM engagement" and Phase 4 logged "Customer 360 … points+redeem".
Backend is there. Needs functional verification and, most likely, the redeem
step wired into POS checkout rather than only the customer screen.

### 1.3 Dashboard date range ✅ backend / 🟡 UX
Already present — `app/page.js:31-33` has `fromDate`/`toDate` state and calls
`api.rangeSummary(branch, fromDate, toDate)`. The problem is that it's a
*secondary* panel: the primary KPIs are hardcoded to today and a fixed 30 days
(`api.topProducts(branch, 30)`). **Fix is to promote the range to a global
control that every widget reads**, not to build date handling from scratch.

### 1.4 Column filters on all pages 🔴
Not implemented anywhere. `app/components/` holds only 8 components
(`DecisionCardsWidget`, `DetailModal`, `Shell`, `StockScanMode`, `Wordmark`,
`charts`, `icons`, `rx`). No sort/filter primitive exists. This is greenfield
and touches every table screen — build one component, adopt it everywhere.

### 1.5 Prescriptions via Hermes instead of Gemini ⛔ as asked / 🟡 achievable
`app/services/prescriptions.py:38`:
```python
def is_configured() -> bool:
    """vision needs Gemini — the Anthropic path has no key wired for images here"""
    return settings.ai_provider == "gemini" and bool(settings.ai_api_key())
```
Prescription reading is **hardcoded to Gemini vision**. Two blockers:

1. **Hermes 3 405B is a text-only model.** The configured default
   (`nousresearch/hermes-3-llama-3.1-405b:free`) cannot read an image at all.
2. `is_configured()` gates on provider identity, not capability.

**What actually meets the intent** (free, not Google): route the image through
OpenRouter to a free **vision** model — Llama 3.2 11B Vision, Qwen2.5-VL or
similar — and refactor the gate to "provider supports vision" instead of
"provider == gemini". Same `_EXTRACT_PROMPT`, same strict-JSON parse, same
manual fallback. Keep a fallback chain, because OpenRouter retires `:free`
slugs without notice (already a documented hazard in `HERMES_FALLBACK_MODELS`).

### 1.6 Hermes agent CLI instead of Claude API 🟡 — mostly config
Both halves already exist:
- **Provider registry** (`services/llm.py`): `anthropic`, `gemini`, `hermes`
  (OpenRouter, aliases `openrouter`/`nous`), `ollama`, `claude-cli`.
- **Agent registry** (`services/agent_orchestration.py`): `_run_hermes` plus
  `claude` (`claude -p`), `gemini` CLI, `antigravity`.

What's actually wrong is **configuration**: `config/connections.json` says
```json
"ai": { "provider": "anthropic", "model": "claude-opus-5" }
```
And `config.py:197-201` auto-detects in the order **Gemini → OpenRouter →
Anthropic**, so a stray `GEMINI_API_KEY` silently wins. Setting
`AI_PROVIDER=hermes` explicitly is required — the auto-detect will not pick it
for you. No AI key is currently set in `src/backend/.env`, so AI features are
probably falling back to the keyword router right now.

### 1.7 Titan / Drug-Eye consolidation + rename 🟡
`app/services/catalogue.py` exists; `progress.md` logs "Catalogue fix Phase 0 —
Titan enrichment + duplicates" (2026-07-20) and "Drug-Eye online harvest (uses +
substitution)". But it also records:

> *"NOT DONE yet: review UI (Phase 1) and the approved eStock write-back"*

So matches are computed and never reviewable or applied. The rename is trivial;
**the review UI is the real work**, and the write-back to eStock is the risky
part that needs an approval gate.

### 1.8 Product card — units, and unit adjustment on buy/sell 🟡 schema gap
Current model (`models.py:111-116`) is **two levels only**:
```python
unit_big    # علبة
unit_small  # شريط / أمبول / كبسولة
unit_factor # one float
```
The owner wants **three** — pack → strip → tablet. eStock itself carries
`product_unit1/2/3` plus `product_unit1_2` and `product_unit1_3`, i.e. three
levels with two conversion factors. **ProCare is mirroring only two of them.**
This needs a schema migration, an ETL change, and POS/purchasing unit pickers,
in that order. It is the deepest item on this list.

### 1.9 Product categorisation 🟡
Columns exist: `dosage_form` (`Unicode(50)`, **free text, no constraint**),
`is_otc`, `is_medicine`, `category`. Missing:
- a **controlled vocabulary** for the owner's taxonomy — ampoule, tablet,
  capsule, syrup, sachet, inhaler, cream, ointment, suppository, eyedrop, eardrop
- a **`needs_refrigeration`** flag (nothing in the model)
- a backfill to classify 53,672 existing products (name-pattern rules + the
  Titan/Drug-Eye data from 1.7, then manual review of the residue)

### 1.10 Compounding pharmacy section 🔴
Nothing. No model, no service, no page — `grep -i "compound|تركيب"` returns
empty. Fully greenfield: formula master (ingredients + quantities + method),
batch preparation, cost roll-up, labels, expiry/shelf-life.

### 1.11 Scrape Facebook page «صيادله التركيبات» ⛔
I won't build a Facebook scraper. It breaks Facebook's ToS, group content sits
behind an auth wall so it would need your personal credentials, and any such
scraper breaks on their next markup change. Practical alternatives:
- **Graph API** — legitimate, but only for a page you administer, with a token.
  If you admin the page, this is the clean route.
- **Manual export** — you paste or export the useful formulas once; I model and
  import them. Best effort-to-value ratio for a one-off knowledge base.
- **A curated seed list** you approve, which the compounding module then owns.

I'd take the manual export: the formulas you actually compound are a stable set
of dozens, not a feed worth scraping.

### 1.12 Marketing & social moderation 🟡
`app/api/marketing.py` + `app/services/campaigns.py` exist; Phase 4 logged
"Marketing & social studio (شبكات + عروض)". Needs a concrete gap list against
what you expect — this is the item where I have the least evidence about
*which* part is missing. Please point at the screen that disappoints you.

### 1.13 Second-click detail, especially accounting & expense types 🟡 / 🔴
`DetailModal.js` exists and drill-down is logged as done. But **expenses have no
real model** — the only thing in the schema is `other_expenses` as a *column on
an invoice* (`models.py:403-405`). There is no expense ledger and therefore no
expense *types* to drill into. That sub-item is greenfield: `expense_types` +
`expenses` tables, entry screen, and drill-down by type/branch/period.

### 1.14 Branch menus + "Main" for consolidated 🟡
The plumbing is there — `providers.js` holds `branch` state where **`0` = all
branches (consolidated)**, and branches load from `api.branches()`. What's
missing is the **menu structure** the owner wants: per-branch sections plus a
Main/consolidated section, rather than one global dropdown.

### 1.15 Shortages 🟡
`app/api/shortages.py` and Phase 3 "كشكول النواقص وخطة الشراء" exist. Needs
verification, plus the "facilitate transaction" flow the owner described
(shortage → transfer or purchase in one action).

### 1.16 Accounting statement per branch 🟡
`accounting.py:354 account_statement(...)` exists. Needs branch-scoping
confirmed and a per-branch statement screen.

### 1.17 Reports not working 🟡 — needs auth to diagnose
`app/api/reports.py` **does** exist and **is** registered
(`routes.py:186`) with 5 endpoints: `/stock`, `/stock/batches`,
`/stock/movements`, `/stock/valuation`, `/item-movement`.

But `/reports/page.js` calls **14** different API functions —
`cashiers, dailySales, expiry, lowStock, perfAudit, perfOverview, perfVendor,
profitLoss, salesByCustomer, stockMovements, stockReport, stockValuation,
topProducts` — spread across `dashboard`, `performance`, `accounting` and
`insights`. **If any one of them 500s, the page looks broken.** Which one is
failing cannot be determined without a session token.

---

## 2. Plan

Ordered so that cheap, high-leverage work lands first and the two schema-deep
items don't block everything else.

### Phase R — Diagnose (do this first, ~half a day)

- [ ] **R0 · Get an authenticated session and capture real failures.**
      Log in, then hit all 14 `/reports` endpoints and the dashboard endpoints,
      recording status + error per call. **Nothing else on this list should be
      estimated until R0 is done** — "reports not working" could be one broken
      endpoint or twelve.
- [ ] **R1 · Screen-by-screen walkthrough** with the owner, capturing which of
      the 🟡 items are genuinely absent vs. present-but-unusable. Items 1.12 and
      1.15 especially.

### Phase A — Cross-cutting UI (biggest perceived win per hour)

- [ ] **A1 · `DataTable` component** — per-column filter, sort, sticky header,
      CSV export, print. One component, built once. *(Item 1.4)*
- [ ] **A2 · Adopt `DataTable`** across inventory, reports, customers, vendors,
      purchasing, shortages, treasury, employees, audit.
- [ ] **A3 · Global date-range control** — lift `fromDate`/`toDate` into
      `providers.js` beside `branch`, add presets (today / 7 / 30 / 90 / custom),
      make every dashboard widget and report read it. Replaces the hardcoded
      `today` and `30`. *(Item 1.3)*
- [ ] **A4 · Branch/Main menu restructure** — per-branch nav sections plus a
      Main consolidated section, driven by the existing `branch === 0`
      convention. *(Item 1.14)*

### Phase B — AI provider switch (small, well-understood)

- [ ] **B1 · Make Hermes the default.** `config/connections.json` →
      `provider: "hermes"`; set `AI_PROVIDER=hermes` and `OPENROUTER_API_KEY`
      in `src/backend/.env`. Remove/ignore `GEMINI_API_KEY` so auto-detect
      can't override. *(Item 1.6)*
- [ ] **B2 · Default the agent runner to `hermes`** instead of `claude` in
      `agent_orchestration.py`, keeping `claude-cli` selectable.
- [ ] **B3 · Vision refactor for prescriptions** — replace the
      `provider == "gemini"` gate with a capability check; add an OpenRouter
      free-vision adapter and a fallback chain. **B3 is the only real code in
      this phase.** *(Item 1.5)*
- [ ] **B4 · Fail-soft test** — assert that when every free slug is exhausted
      the app degrades to manual entry with a visible reason, never a silent
      empty extraction.

### Phase C — Product model depth (schema-first, do not rush)

- [ ] **C1 · Third unit level.** Migration for `unit_mid` + a second conversion
      factor; mirror eStock's `product_unit1/2/3`, `unit1_2`, `unit1_3`; ETL
      update; backfill. *(Item 1.8)*
- [ ] **C2 · Unit pickers** in POS sell and purchasing buy, with the conversion
      shown on the line, plus stock-effect tests (selling 1 tablet from a
      pack-of-10-strips-of-10 must deduct 0.01 packs).
- [ ] **C3 · Product-card rebuild** — units, conversions, categories, batches,
      barcodes, movement, on one screen.
- [ ] **C4 · Category vocabulary + `needs_refrigeration`** flag, constrained
      list, migration. *(Item 1.9)*
- [ ] **C5 · Classification backfill** — rule pass over 53,672 products, then
      Titan/Drug-Eye enrichment, then a review queue for the residue.

### Phase D — Catalogue consolidation

- [ ] **D1 · Review UI** for Titan/Drug-Eye match candidates — accept / reject /
      merge, with confidence shown. This is the piece `progress.md` flags as
      NOT DONE. *(Item 1.7)*
- [ ] **D2 · Rename** the consolidation feature to the owner's preferred name.
- [ ] **D3 · eStock write-back behind an explicit approval gate**, never
      automatic. Highest-risk item in this plan — it writes to production.

### Phase E — Accounting & expenses

- [ ] **E1 · `expense_types` + `expenses` models** and migration. *(Item 1.13)*
- [ ] **E2 · Expense entry screen** with type, branch, period, attachment.
- [ ] **E3 · Drill-down** from any accounting figure into its expense lines.
- [ ] **E4 · Per-branch account statement** screen over the existing
      `account_statement()`; confirm branch scoping. *(Item 1.16)*

### Phase F — Loyalty, shortages, reports breadth

- [ ] **F1 · Redeem in POS checkout** — points balance, redeem, tier discount
      applied to the sale. *(Item 1.2)*
- [ ] **F2 · Shortage → action** — one click to transfer request or purchase
      line. *(Item 1.15)*
- [ ] **F3 · Report factory** — generalise the `reports-daily` pattern
      (date filter, branch tag, totals, CSV, print) into a config-driven
      generator, then work down the eStock report list by owner priority.
      **Do not hand-build 119 screens.** *(Items 1.1, 1.17)*
- [ ] **F4 · Raw-mirror first fill** of the 10 large tables, off-peak, per
      `docs/RAW-MIRROR-FIRST-FILL.md`. *(Item 1.1)*

### Phase G — Compounding

- [ ] **G1 · Formula master** — ingredients, quantities, method, shelf life.
      *(Item 1.10)*
- [ ] **G2 · Batch preparation** — consume components, produce a batch, cost
      roll-up, label + expiry.
- [ ] **G3 · Formula knowledge base** seeded from your **manual export**, not a
      scraper. *(Item 1.11)*
- [ ] **G4 · Compounding marketing plan** — flag which compounded products to
      promote, feeding Phase H.

### Phase H — Marketing & social

- [ ] **H1 · Gap list** from R1, then close it. Scope deliberately deferred
      until the walkthrough, because 1.12 is the item with the least evidence.

---

## 3. Sequencing

```
R0 ──► everything (R0 is the gate; it may re-rank all of Phase F)
R1 ──► H1, and confirms/kills the 🟡 items

A1 ──► A2 ──► (A3, A4 in parallel)          UI, independent of backend
B1 ──► B2                                    config only, ship immediately
B3 ──► B4                                    the one AI code change
C1 ──► C2 ──► C3     C4 ──► C5               schema-first, don't reorder
D1 ──► D2 ──► D3                             D3 last: it writes to eStock
E1 ──► E2 ──► E3     E4 standalone
F3 ──► the report backlog                    factory before volume
G1 ──► G2 ──► G4     G3 needs your export
```

**Recommended first sprint:** R0, R1, B1, B2, A1. That is one diagnosis, two
config changes that immediately stop the Claude API spend, and the component
that makes every table screen better.

---

## 4. Three things that cannot be done as asked

1. **Hermes cannot read prescriptions.** Hermes 3 405B is text-only. The intent
   (free, not Google) is achievable via an OpenRouter free *vision* model — see
   B3 — but not with the model named.
2. **No Facebook scraper.** ToS, an auth wall needing your personal credentials,
   and permanent fragility. Graph API if you admin the page, otherwise a manual
   export — see 1.11.
3. **Free-tier AI is not a reliability tier.** OpenRouter retires `:free` slugs
   without notice; `HERMES_FALLBACK_MODELS` exists precisely because of this.
   Acceptable for prescription assist with manual fallback. **Not** acceptable
   for anything that silently produces a number someone then trusts.

---

## 5. Also worth knowing

- **`next dev` is running, not production.** It took 40s to serve `/login`
  cold. Before real users come through the tunnel:
  `npm run build && npm run start` (same port 3100, tunnel unchanged).
- **The dev server currently running was started inside a Claude Code session**
  and dies with it. Run it from your own terminal or as a Windows service, the
  way `cloudflared` already is.
- **`/api/health` answers unauthenticated** and reveals DB type and product
  count. Cloudflare Access covers the hostname, so this is low risk today —
  worth tightening if the app is ever exposed without Access.
