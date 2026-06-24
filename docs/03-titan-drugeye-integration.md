# Titan / Drug‑Eye Integration

> Titan / Drug‑Eye is the **clinical knowledge source**: drug names, scientific (generic) names,
> therapeutic **substitutions / alternatives**, drug **interactions**, and **dosing**.
> ProCare OS reads it **read‑only** to enrich every product and to give the pharmacist an
> **advisory** safety layer at the point of sale. It never blocks a sale automatically.
>
> ⚠️ **The Titan schema is NOT yet audited — every table/column name below is a working
> assumption (TBD) until a real audit of `D:\Labirdo` is done.** Treat this document as the
> integration *plan* and the audit *checklist*, not a verified reference. Contrast with
> [`02-eStock-database-reference.md`](02-eStock-database-reference.md), which **is** grounded in a
> completed audit.

---

## 1. What Titan / Drug‑Eye provides

| Capability | What ProCare gets from it | Used by |
|------------|---------------------------|---------|
| **Drug names** | Canonical Arabic + English trade names, brand vs. generic | Product enrichment, search, bilingual UI |
| **Scientific / generic names** | Active ingredient(s), strength, dosage form | eStock ↔ Titan **mapping key** (see §4) |
| **Substitution / alternatives** | Therapeutic equivalents (same active ingredient), generics, cheaper/branded swaps | "Out of stock → suggest in‑stock alternative" at POS |
| **Drug interactions** | Pairwise interactions with severity (critical / major / moderate / minor) + effect description | POS basket safety check, `PharmacyAI.drug_interactions()` |
| **Dosing** | Recommended dose by age/weight, frequency, max daily dose, route, indication | `get_correct_dose()`, prescription assist |

This is **separate** from eStock. eStock (`stock` DB on `192.168.1.2`) owns operations
(POS, inventory, customers, money). Titan (`D:\Labirdo`) owns clinical/reference knowledge.
ProCare OS is the **independent system of record** that links the two during the transition and
keeps the clinical link permanently — see [`01-architecture.md`](01-architecture.md) §7.

> **Note on overlap:** eStock already has a small `Product_Dose` table (**69 rows**) and a
> `product_scientific_name` column on every product. That eStock dosing data is sparse and
> free‑text; **Titan is the richer, authoritative clinical source** and supersedes it. eStock's
> `product_scientific_name` is still valuable — it is one of the **mapping keys** into Titan (§4).

---

## 2. Where Titan lives — and what we don't know yet

| Fact | Value | Status |
|------|-------|--------|
| File system path | `D:\Labirdo` | ✅ Known |
| Vendor / product | Titan / Drug‑Eye (Egyptian drug reference) | ✅ Known |
| DBMS engine | SQL Server? Access/`.mdb`? Firebird? SQLite? Embedded? | 🔴 **TBD** |
| Database name(s) | e.g. `Titan`, `DrugEye`, `DrugEyePremium`, `pharma` | 🔴 **TBD** |
| Host / instance | On `192.168.1.2`, a different host, or a **local attached** file? | 🔴 **TBD** |
| Read‑only credentials | A dedicated read‑only login (mirror the eStock guardrail) | 🔴 **TBD** |
| Table/column schema | Products, scientific names, interactions, alternatives, dosing | 🔴 **TBD** |
| Row counts | # drugs, # interactions, # substitutions, # dosing rules | 🔴 **TBD** |
| Mapping to eStock | Shared id? scientific‑name join? fuzzy name only? (see §4) | 🔴 **TBD** |
| Data quality | NULLs, orphans, duplicate ingredients, encoding of Arabic | 🔴 **TBD** |

> Drug‑Eye historically ships as an **embedded/attached** database (often Access `.mdb` or an
> attachable SQL Server `.mdf`) rather than a networked server. **Do not assume SQL Server.**
> Step 1 of the audit (§3) is to determine the engine before anything else, because the engine
> decides the ODBC driver, the connection string, and whether ETL can even reach it over the LAN.

---

## 3. Schema‑discovery checklist (do this first)

Produce a **`03-titan-schema-audit.md`** in this repo, mirroring the depth of
[`02-eStock-database-reference.md`](02-eStock-database-reference.md). Work top‑down:

### 3.1 Identify the engine and the files
- [ ] List `D:\Labirdo` recursively. Note extensions: `.mdf`/`.ldf` (SQL Server), `.mdb`/`.accdb`
      (Access), `.fdb`/`.gdb` (Firebird), `.db`/`.sqlite` (SQLite), or a proprietary format.
- [ ] If `.mdf`: is it **attached** to a SQL Server instance, or a loose file to attach read‑only?
- [ ] If `.mdb`/`.accdb`: which ODBC driver is installed (`Microsoft Access Driver`)? Is it 32‑ vs
      64‑bit? (This dictates whether `pyodbc` from a 64‑bit Python can open it.)
- [ ] Capture the exact **connection string** that opens it read‑only, and the **DB name**.

### 3.2 Enumerate tables and columns
- [ ] Dump every table name + row count (SQL Server: `sys.tables` + `sys.dm_db_partition_stats`;
      Access: `MSysObjects` / driver catalog). Record the real names — **do not assume English**;
      Drug‑Eye internals are often Arabic or transliterated.
- [ ] For each candidate table, dump column names, types, nullability, and a 10‑row sample.
- [ ] Identify primary keys and any (rare) relationships.

### 3.3 Locate the five capability tables (names are TBD — match by content, not by guessing)
- [ ] **Product / Drug master** — expect: a drug id (PK), trade `name_ar` / `name_en`, a
      `scientific_name` / active‑ingredient reference, `strength`, `dosage_form`, manufacturer.
- [ ] **Active ingredient / scientific name** — Drug‑Eye usually normalizes ingredients into their
      own table, with a many‑to‑many "drug ↔ ingredient" bridge (combination drugs have several).
- [ ] **Interactions** — expect two drug/ingredient FKs, a `severity` code, and an effect
      description (likely Arabic). Confirm whether interactions are keyed by **drug** or by
      **active ingredient** (ingredient‑level is far more useful and avoids per‑brand duplication).
- [ ] **Substitution / alternatives** — expect a drug id → alternative drug id, or it may be
      *derived* (two drugs are alternatives **iff** they share the same active ingredient + strength).
      Determine which: an explicit table, or a query over the ingredient bridge.
- [ ] **Dosing** — expect drug/ingredient id, age/weight bands, dose, frequency, max daily dose,
      route, indication.

### 3.4 Data‑quality probes (so ProCare's clinical layer is trustworthy)
- [ ] Arabic **encoding**: confirm text reads correctly via the driver (NVARCHAR/Unicode vs. a
      legacy code page). Mojibake here will silently break every interaction message.
- [ ] Count NULL scientific names / unmapped ingredients (these can't be matched to eStock).
- [ ] Count duplicate ingredient spellings (e.g. `Paracetamol` vs `Acetaminophen` vs Arabic) —
      this is the #1 risk for the scientific‑name join in §4.
- [ ] Severity vocabulary: list the distinct `severity` values and map them to ProCare's
      canonical set `critical | major | moderate | minor`.

### 3.5 Establish the mapping path to eStock
- [ ] Is there **any shared identifier** between Drug‑Eye drug ids and eStock `Products.product_id`
      or `Products.product_code`? (Usually **no** — confirm.)
- [ ] How clean is eStock `Products.product_scientific_name` (nvarchar(200))? Sample it against
      Titan's scientific names to estimate the join hit‑rate **before** committing to a strategy.

---

## 4. eStock ↔ Titan product mapping strategy

ProCare's own catalog already carries the link column. In
[`../sql/procare-schema.sql`](../sql/procare-schema.sql) the `products` table has:

```sql
scientific_name   NVARCHAR(200) NULL,
titan_drug_id     INT           NULL,   -- link to Titan/Drug-Eye (see docs/03)
```

`titan_drug_id` is the **resolved** foreign reference into Titan. The mapping job's whole purpose is
to populate that column for as many of the **53,474** products as possible. Use a **tiered match**,
best key first; record *how* each row was matched so low‑confidence links can be reviewed.

### Tier 1 — Shared identifier (best, if it exists)
If the audit (§3.5) finds a shared id or code between Titan and eStock, join on it directly and
mark the match `exact`. **Most likely this does not exist** between eStock and Drug‑Eye — confirm,
don't assume.

### Tier 2 — Scientific‑name / active‑ingredient join (the realistic primary key)
Normalize both sides (trim, lowercase, strip strength/form tokens, unify Arabic/Latin spelling via a
synonym list built from §3.4) and join eStock `product_scientific_name` ↔ Titan ingredient/scientific
name. This is expected to be the **main** path. Mark matches `by_scientific_name`.

> Caveat: a scientific name maps to **many brands**, and combination drugs have **several**
> ingredients. Tier 2 gives a *candidate set*; disambiguate with strength + form before accepting.

### Tier 3 — Fuzzy name match (fallback, human‑reviewed)
For leftovers, fuzzy‑match trade names (`name_ar` / `name_en`) using token‑set ratio
(e.g. `rapidfuzz`). **Never auto‑accept** a fuzzy hit for clinical use: queue it with its score for a
pharmacist to confirm. Mark `fuzzy_pending` until approved, then `fuzzy_confirmed`.

### Suggested mapping‑provenance columns (extend `products`)
| Column | Meaning |
|--------|---------|
| `titan_drug_id` | Resolved Titan id (already in schema) |
| `titan_match_method` | `exact` / `by_scientific_name` / `fuzzy_confirmed` / `unmapped` |
| `titan_match_score` | 0–100 confidence (100 for exact) |

Unmapped products simply get **no** clinical enrichment — the POS degrades gracefully (no advisory,
sale proceeds). Coverage (% of products with a confident `titan_drug_id`) becomes a tracked metric.

### Caching
Load Titan's interaction + substitution + dosing data into memory (or Redis if large) at startup;
it changes rarely. Refresh on a schedule, not per request. ProCare queries the **cache** at POS so a
slow/locked Titan file never stalls a sale.

---

## 5. Query layer (pseudo‑code — exact Titan columns are TBD)

These functions live in ProCare's FastAPI **drug‑interaction service**
([`01-architecture.md`](01-architecture.md) §7) and back `PharmacyAI.drug_interactions()` in
[`04-ai-automation-spec.md`](04-ai-automation-spec.md). They take **ProCare** `product_id`s,
resolve to `titan_drug_id` internally, and return **advisory** results.

```python
# NOTE: Table/column names prefixed `titan_*` are PLACEHOLDERS until the §3 audit.
# In-stock checks hit ProCare's OWN clean DB (stock_batches), never eStock directly.

SEVERITY_RANK = {"critical": 3, "major": 2, "moderate": 1, "minor": 0}


async def _resolve_titan_ids(product_ids: list[int]) -> dict[int, int]:
    """ProCare product_id -> titan_drug_id, skipping unmapped products."""
    rows = await db.fetch_all(
        "SELECT product_id, titan_drug_id FROM products "
        "WHERE product_id IN :ids AND titan_drug_id IS NOT NULL",
        {"ids": tuple(product_ids)},
    )
    return {r.product_id: r.titan_drug_id for r in rows}


async def get_drug_interactions(product_ids: list[int],
                                min_severity: str = "major") -> list[dict]:
    """All pairwise interactions among the products on an invoice (+ customer history).
    Advisory only — the caller shows it to the pharmacist; it never blocks the sale."""
    titan_ids = list((await _resolve_titan_ids(product_ids)).values())
    if len(titan_ids) < 2:
        return []
    # Interactions are stored once per unordered pair -> check BOTH orderings.
    rows = await titan_cache.query("""
        SELECT i.drug1_id, i.drug2_id, i.severity,
               i.effect_ar, i.effect_en
        FROM   titan_interactions i
        WHERE  i.drug1_id IN :ids AND i.drug2_id IN :ids
    """, {"ids": tuple(titan_ids)})
    floor = SEVERITY_RANK[min_severity]
    return [r for r in rows if SEVERITY_RANK.get(r["severity"], 0) >= floor]


async def get_substitutions(product_id: int, branch_id: int) -> list[dict]:
    """Therapeutic alternatives for a drug that are ACTUALLY IN STOCK at this branch.
    Stock comes from ProCare's own stock_batches (FEFO, non-expired)."""
    ids = await _resolve_titan_ids([product_id])
    if product_id not in ids:
        return []
    titan_id = ids[product_id]
    # Alternatives may be an explicit table OR derived from shared active ingredient.
    alt_titan_ids = await titan_cache.query("""
        SELECT alternative_drug_id, reason
        FROM   titan_substitutions
        WHERE  drug_id = :tid
    """, {"tid": titan_id})
    if not alt_titan_ids:
        return []
    # Map Titan alternatives back to ProCare products, then keep only in-stock ones.
    return await db.fetch_all("""
        SELECT p.product_id, p.name_ar, p.name_en, p.sell_price,
               SUM(sb.amount) AS available_qty
        FROM   products p
        JOIN   stock_batches sb ON sb.product_id = p.product_id
        WHERE  p.titan_drug_id IN :alts
          AND  sb.branch_id = :branch
          AND  sb.amount > 0
          AND  (sb.exp_date IS NULL OR sb.exp_date > CAST(SYSDATETIME() AS date))
        GROUP  BY p.product_id, p.name_ar, p.name_en, p.sell_price
        ORDER  BY p.sell_price ASC
    """, {"alts": tuple(a["alternative_drug_id"] for a in alt_titan_ids),
          "branch": branch_id})


async def get_correct_dose(product_id: int,
                           patient_age_years: float,
                           weight_kg: float | None = None) -> dict | None:
    """Recommended dose for a patient's age (and weight if dosing is weight-based).
    Advisory; returns None if Titan has no rule for this drug/age."""
    ids = await _resolve_titan_ids([product_id])
    if product_id not in ids:
        return None
    row = await titan_cache.query_one("""
        SELECT dose, unit, frequency, max_daily_dose, route,
               indication_ar, indication_en
        FROM   titan_dosing
        WHERE  drug_id = :tid
          AND  age_min_years <= :age AND :age <= age_max_years
          AND  (:wt IS NULL OR (weight_min_kg <= :wt AND :wt <= weight_max_kg))
        ORDER  BY age_min_years DESC          -- most specific band first
    """, {"tid": ids[product_id], "age": patient_age_years, "wt": weight_kg})
    return row
```

**Why these shapes:**
- Interactions stored once per unordered pair → query **both** `(d1,d2)` orderings (here by passing
  the same id set to both sides). Filter to `severity >= major` by default so the pharmacist isn't
  buried in trivia.
- Substitutions are only useful if the alternative is **sellable now** → the in‑stock filter runs
  against ProCare's **own** `stock_batches` (per `branch_id`, `amount > 0`, not expired), matching the
  FEFO/availability rules in [`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md) — **never**
  query eStock at runtime (guardrail: read‑only ETL only).
- Dosing returns the **most specific** matching age (and optional weight) band.
- All three are **advisory**: clinical output is shown to a pharmacist and **never silently blocks a
  sale** (locked guardrail).

---

## 6. How this plugs into ProCare

- **POS counter sale** ([`01-architecture.md`](01-architecture.md) "Data flow examples"): as items are
  scanned, `get_drug_interactions()` runs over the basket **plus the customer's recent history**; a
  serious interaction shows an advisory banner; out‑of‑stock items offer `get_substitutions()`.
- **AI assistant**: `PharmacyAI.drug_interactions()` ([`04-ai-automation-spec.md`](04-ai-automation-spec.md))
  wraps these functions and answers in Arabic.
- **Product enrichment**: the mapping job (§4) fills `products.titan_drug_id`, and a UI screen shows
  each drug's scientific name, alternatives, and dosing pulled from Titan.

---

## 7. Next steps

1. **Audit `D:\Labirdo` first.** Determine the engine, DB name, connection string, and read‑only
   credentials; then enumerate tables/columns/row counts. Save as **`03-titan-schema-audit.md`** with
   the same rigor as the eStock reference. Until then, every `titan_*` name in §5 is a placeholder.
2. **Add a read‑only Titan login** (mirror the eStock guardrail: ProCare never writes to Titan).
   Put its connection details in `config/connections.json` (git‑ignored; commit only
   `connections.example.json`).
3. **Decide the mapping strategy** (§4) from real hit‑rate numbers: confirm Tier‑1 shared id exists or
   not; measure the Tier‑2 scientific‑name join coverage against eStock's 53,474 products; size the
   Tier‑3 fuzzy review queue.
4. **Build the mapping job** to populate `products.titan_drug_id` (+ `titan_match_method`,
   `titan_match_score`); expose unmatched/low‑confidence rows for pharmacist review.
5. **Replace the placeholder SQL** in §5 with the audited table/column names and load
   interactions/substitutions/dosing into the startup cache.
6. **Validate with known cases** — e.g. **aspirin + warfarin** must flag a *major* interaction;
   a paracetamol brand should list its in‑stock generics as substitutions; a pediatric syrup should
   return an age‑appropriate dose. Verify Arabic effect text renders correctly end‑to‑end.

---

### Related docs
- [`01-architecture.md`](01-architecture.md) — where the drug‑interaction service sits (§7) and data flow.
- [`02-eStock-database-reference.md`](02-eStock-database-reference.md) — the audited eStock side (`Products`, `product_scientific_name`).
- [`04-ai-automation-spec.md`](04-ai-automation-spec.md) — `PharmacyAI.drug_interactions()`.
- [`05-data-quality-and-fixes.md`](05-data-quality-and-fixes.md) — FEFO / in‑stock / expiry rules used by `get_substitutions()`.
- [`../sql/procare-schema.sql`](../sql/procare-schema.sql) — `products.titan_drug_id`, `stock_batches`.
