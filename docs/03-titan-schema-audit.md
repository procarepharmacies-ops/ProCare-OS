# Titan / Drug-Eye Schema Audit — COMPLETED 2026-07-13

> This is the audit that [`03-titan-drugeye-integration.md`](03-titan-drugeye-integration.md) §3
> required before any integration work. Every "TBD" in that doc is resolved here.
> Extraction + mapping implemented in [`../src/backend/tools/titan_extract.py`](../src/backend/tools/titan_extract.py)
> (tests: `app/tests/test_titan_extract.py`).

## 1. Engine and files — resolved

| Fact | Value |
|------|-------|
| Vendor / product | Titan (Drug-Eye family), version **360.260217**, ~18k Egyptian drugs |
| Location | `D:\Labirdo\TITAN.W1` (local disk on the dev PC, no server) |
| Engine | **None** — proprietary fixed-width binary files (`.phy`, `.ebw`), no DBMS, no ODBC |
| Main app | `Phye.exe` (VB-era desktop app) |
| Access mode | Direct file read, **read-only** (guardrail preserved — ProCare never writes) |
| Credentials | Not applicable (filesystem read) |

## 2. Data files (the "tables")

| File | Size / shape | Contents |
|------|--------------|----------|
| `Files/DBI/tar.phy` | 32,000 slots × **856 bytes** fixed records | **Drug master** — the file the extractor reads |
| `Files/DBI/max.drug.txt` | one number (18,105) | High-water slot count |
| `Files/DB/GN.ebw` | 122-byte records (uint16 len + 120-byte buffer) | Generic / scientific name list (~2,097 names) |
| `Files/DB/DisList.ebw` | same container format | Disease list |
| `Files/DB/AvoidPreg.ebw` | same container format | Pregnancy-avoidance list |
| `Files/DBI/salesfull.phy`, `pruchworld.phy`, `customers.w.phy` | large binaries | Titan's own POS data — **not needed** (eStock owns operations) |

### `tar.phy` record layout (audited byte-by-byte)

| Offset | Length | Field | Notes |
|--------|--------|-------|-------|
| 0 | 40 | Trade name (EN) | space-padded; blank = unused slot |
| 40 | 30 | Trade name (AR) | cp1256 — **corrupted in this copy** (literal U+FFFD bytes); extractor stores NULL |
| 70 | 20 | Manufacturer | e.g. `MUP`, `GSK` |
| 90 | 40 | **Scientific name / active ingredients** | `A+B+C` for combinations — the mapping key |
| ~130–260 | | Prices and flags (floats) | not extracted (eStock owns prices) |
| 792 | 64 | Therapeutic category | e.g. `TOPICAL-ANTIBIOTIC` |

## 3. Extraction results (run 2026-07-13)

| Metric | Value |
|--------|-------|
| Drugs parsed from `tar.phy` | **15,373** (of 32,000 slots) |
| With scientific name | 13,978 (91%) |
| Distinct active-ingredient combinations | **4,091** |
| Mirrored to ProCare `titan_drugs` | 15,373 rows (idempotent reload) |

## 4. eStock ↔ Titan mapping results (docs/03 §4 tiers)

Tier 1 (shared id) confirmed **not to exist** — matching is by normalised English
trade name, unambiguous keys only (an ambiguous key is dropped: a wrong clinical
link is worse than none).

| Tier | Method | Score | Matches |
|------|--------|-------|---------|
| exact | `exact_name` | 100 | 3,447 |
| pack-count stripped | `name_no_pack` | 90 | 470 |
| token-sorted | `name_tokens` | 85 | 228 |
| **total mapped** | | | **4,145 / 53,416** |

Plus **658 scientific-name backfills** onto products eStock left blank
(never overwrites an eStock-provided value; the sync's `update_on_match` now
COALESCEs so it can't wipe the enrichment either).

**Why "only" 4,145:** eStock's 53k catalogue is majority non-drug (cosmetics,
supplies, consumables) which Titan doesn't cover. The counter-relevant view:

| Sales-weighted (products sold in last 180 days = 3,091) | Count | % |
|---|---|---|
| with scientific name | 1,541 | 50% |
| with resolved `titan_drug_id` | 854 | 28% |

### Substitution figures (the consolidation deliverable)

| Metric | Value |
|--------|-------|
| Products with scientific name (whole catalogue) | 8,784 (was 7,566 before Titan) |
| Substitution groups (≥2 products, same ingredients) | **1,242** |
| Products with ≥1 in-catalogue therapeutic alternative | **6,861** |

## 5. What's still open

1. **Tier-3 fuzzy queue** (docs/03 §4): ~1–2k more drug products are matchable
   with `rapidfuzz` + pharmacist review UI. Never auto-accept.
2. **Arabic names**: corrupted in this Titan copy — eStock's `name_ar` remains
   the Arabic source; no loss.
3. **Interactions / dosing**: not found as parseable tables in this Titan build
   (likely inside `Phye.exe` resources or the `.ebw` clinical lists).
   `services/clinical.py`'s curated rule set stays the interaction source;
   Titan supplies identity/substitution/category data.
4. **eStock write-back**: after the owner validates the mapping in ProCare,
   a one-time reviewed export can fill eStock's `product_scientific_name`
   (currently 7.5k/53.5k) — separate, explicitly-approved step; ProCare itself
   stays read-only on eStock.

## 6. Related bug found during this audit

eStock's `Products.deleted` flag is **inverted** relative to its name
(`deleted='1'` on ~53,400 live selling products on BOTH branch servers;
`'0'` + `active=0` on the ~90 truly removed). The ETL mirrored it literally,
marking 99.7% of the catalogue `is_deleted=1` in ProCare — hiding it from POS,
inventory, prescriptions, clinical and reports. Fixed in
`app/services/etl.py::_product_deleted` (+ regression tests in `test_etl.py`);
existing rows corrected in place. `Customer.deleted` has normal semantics.
