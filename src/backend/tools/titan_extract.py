"""Titan / Drug-Eye extraction + eStock product mapping (docs/03 §3–§4).

Reads the Titan drug master READ-ONLY from ``D:\\Labirdo\\TITAN.W1`` and:

  1. mirrors it into ProCare's own DB table ``titan_drugs`` (idempotent:
     delete + reload in one transaction);
  2. maps ProCare ``products`` rows to Titan drugs by normalised English
     trade name (Tier 1 of docs/03 §4), filling ``products.titan_drug_id``,
     ``titan_match_method`` and ``titan_match_score``;
  3. backfills ``products.scientific_name`` from Titan where eStock left it
     blank — this is what feeds the clinical substitution layer;
  4. prints the coverage / substitution figures the migration decision needs.

Titan file format (audited 2026-07: version 360, ``max.drug.txt`` = 18105):
  * ``Files/DBI/tar.phy`` — 32,000 fixed slots x 856 bytes.
      offset   0..39   trade name (EN), space padded
      offset  40..69   trade name (AR) — cp1256; corrupted (U+FFFD bytes) in
                       some exports, stored NULL when unreadable
      offset  70..89   manufacturer
      offset  90..129  scientific name / active ingredients ("A+B+C")
      offset 792..855  therapeutic category (e.g. "TOPICAL-ANTIBIOTIC")
    Unused slots have an all-space/zero name and are skipped.

Run from ``src/backend`` with the app's venv so it reuses the configured
ProCare DB (SQL Server via config/connections.json, or the SQLite dev file):

    python tools/titan_extract.py [--titan-dir D:\\Labirdo\\TITAN.W1] [--dry-run]

Titan is NEVER written to (project guardrail). Only ProCare's own DB changes.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

# Allow running as a plain script from src/backend.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RECORD_SIZE = 856
MAX_SLOTS = 32_000

# Fixed-width field offsets inside one tar.phy record (see module docstring).
F_NAME_EN = slice(0, 40)
F_NAME_AR = slice(40, 70)
F_MANUFACTURER = slice(70, 90)
F_SCIENTIFIC = slice(90, 130)
F_CATEGORY = slice(792, 856)

# Pack-size tokens: "AUGMENTIN 1GM 14 TAB" and "AUGMENTIN 1GM 20 TAB" are the
# same Titan drug (same molecule + strength, different box count), so a second
# match pass drops the count in front of these words. Strength tokens (MG/ML/GM
# values) are kept — different strengths must never merge.
_PACK_WORDS = r"TAB|TABS|TABLET|TABLETS|CAP|CAPS|CAPSULE|CAPSULES|AMP|AMPS|VIAL|VIALS|SACHET|SACHETS|SACH|SUPP|SUPPS"
_PACK_RE = re.compile(rf"\b\d+\s*({_PACK_WORDS})\b")
_NORM_RE = re.compile(r"[^A-Z0-9.]+")
# "1GM" / "7.5MG" written without a space — split the boundary so both sides
# normalise identically ("1 GM", "7.5 MG").
_DIGIT_ALPHA_RE = re.compile(r"(?<=[0-9])(?=[A-Z])|(?<=[A-Z])(?=[0-9])")


def norm(s: str | None) -> str:
    """Join key: uppercase, punctuation to spaces, digit/letter boundaries
    split, collapsed whitespace. '.' survives so 7.5 MG != 75 MG."""
    if not s:
        return ""
    up = _NORM_RE.sub(" ", s.upper())
    up = _DIGIT_ALPHA_RE.sub(" ", up)
    return " ".join(up.replace(" .", " ").replace(". ", " ").split()).strip(".")


def norm_no_pack(s: str | None) -> str:
    """Join key with the box-count token removed (see _PACK_RE note)."""
    n = norm(s)
    return " ".join(_PACK_RE.sub(r"\1", n).split())


def norm_token_sorted(s: str | None) -> str:
    """Order-free key: pack-stripped tokens, sorted. Catches "SPRAY NASAL" vs
    "NASAL SPRAY" while still requiring the exact same token multiset."""
    return " ".join(sorted(norm_no_pack(s).split()))


def _field(rec: bytes, sl: slice) -> str | None:
    """Decode one fixed-width cp1256 field; NUL terminates, spaces pad."""
    raw = rec[sl].split(b"\x00", 1)[0]
    if b"\xef\xbf\xbd" in raw:
        # The export already lost this text (literal UTF-8 replacement chars).
        return None
    text = raw.decode("cp1256", errors="replace").strip()
    if not text or text.count("�") > len(text) // 3:
        return None
    return text


def parse_record(slot: int, rec: bytes) -> dict | None:
    """One tar.phy slot -> row dict, or None for an unused/blank slot."""
    name_en = _field(rec, F_NAME_EN)
    if not name_en:
        return None
    return {
        "titan_drug_id": slot + 1,  # 1-based, stable: Titan appends to slots
        "name_en": name_en[:60],
        "name_ar": (_field(rec, F_NAME_AR) or None),
        "manufacturer": _field(rec, F_MANUFACTURER),
        "scientific_name": _field(rec, F_SCIENTIFIC),
        "category": _field(rec, F_CATEGORY),
        "name_norm": norm(name_en)[:80],
        "sci_norm": (norm(_field(rec, F_SCIENTIFIC)) or None),
    }


def parse_tar_phy(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("rb") as f:
        for slot in range(MAX_SLOTS):
            rec = f.read(RECORD_SIZE)
            if len(rec) < RECORD_SIZE:
                break
            row = parse_record(slot, rec)
            if row:
                rows.append(row)
    return rows


def build_match_index(titan_rows: list[dict]) -> list[tuple[str, int, dict[str, dict]]]:
    """Lookup tiers, best first: (method, score, key -> titan row).

    A key that maps to more than one Titan drug is ambiguous and dropped —
    a wrong clinical link is worse than no link.
    """
    tiers = [
        ("exact_name", 100, lambda r: norm(r["name_en"])),
        ("name_no_pack", 90, lambda r: norm_no_pack(r["name_en"])),
        ("name_tokens", 85, lambda r: norm_token_sorted(r["name_en"])),
    ]
    out = []
    for method, score, keyfn in tiers:
        table: dict[str, list[dict]] = {}
        for r in titan_rows:
            table.setdefault(keyfn(r), []).append(r)
        out.append((method, score, {k: v[0] for k, v in table.items() if len(v) == 1}))
    return out


def match_product(name_en: str | None, tiers: list[tuple[str, int, dict[str, dict]]]) -> tuple[dict, str, int] | None:
    """Resolve one eStock product name to (titan_row, method, score) or None."""
    if not name_en or not norm(name_en):
        return None
    keys = {
        "exact_name": norm(name_en),
        "name_no_pack": norm_no_pack(name_en),
        "name_tokens": norm_token_sorted(name_en),
    }
    for method, score, table in tiers:
        hit = table.get(keys[method])
        if hit:
            return hit, method, score
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--titan-dir", default=r"D:\Labirdo\TITAN.W1", help="Titan installation root")
    ap.add_argument("--dry-run", action="store_true", help="parse + match, write nothing")
    args = ap.parse_args()

    tar = Path(args.titan_dir) / "Files" / "DBI" / "tar.phy"
    if not tar.exists():
        print(f"ERROR: {tar} not found — is Titan installed at {args.titan_dir}?")
        return 1

    print(f"Parsing {tar} ...")
    titan_rows = parse_tar_phy(tar)
    with_sci = sum(1 for r in titan_rows if r["sci_norm"])
    print(f"  {len(titan_rows):,} drugs in {MAX_SLOTS:,} slots | {with_sci:,} with scientific name")
    sci_groups = Counter(r["sci_norm"] for r in titan_rows if r["sci_norm"])
    print(f"  {len(sci_groups):,} distinct active-ingredient combinations")

    tiers = build_match_index(titan_rows)

    from sqlalchemy import text as sql

    from app.db import models  # noqa: F401  (registers titan_drugs on Base)
    from app.db.base import SessionLocal, engine
    from app.db.migrate import ensure_titan_match_columns

    models.Base.metadata.create_all(engine, tables=[models.TitanDrug.__table__])
    ensure_titan_match_columns(engine)

    with SessionLocal() as session:
        products = session.execute(
            sql("SELECT product_id, name_en, scientific_name FROM products WHERE is_deleted = 0")
        ).all()
        print(f"  {len(products):,} ProCare products to map")

        matches: list[dict] = []
        backfills: list[dict] = []
        methods: Counter[str] = Counter()
        for pid, name_en, sci in products:
            m = match_product(name_en, tiers)
            if not m:
                methods["unmapped"] += 1
                continue
            titan_row, method, score = m
            methods[method] += 1
            matches.append(
                {"pid": pid, "tid": titan_row["titan_drug_id"], "method": method, "score": score}
            )
            if (not sci or not sci.strip()) and titan_row["scientific_name"]:
                backfills.append({"pid": pid, "sci": titan_row["scientific_name"]})

        print(f"  matched: {sum(v for k, v in methods.items() if k != 'unmapped'):,} "
              f"({dict(methods)})")
        print(f"  scientific-name backfills available: {len(backfills):,}")

        if args.dry_run:
            print("DRY RUN — nothing written.")
            return 0

        # 1) Reload the mirror atomically.
        session.execute(sql("DELETE FROM titan_drugs"))
        session.bulk_insert_mappings(models.TitanDrug, titan_rows)

        # 2) Product mapping (recomputed from scratch so re-runs self-heal).
        session.execute(sql(
            "UPDATE products SET titan_drug_id = NULL, titan_match_method = NULL, "
            "titan_match_score = NULL WHERE titan_match_method IS NOT NULL"
        ))
        session.execute(
            sql("UPDATE products SET titan_drug_id = :tid, titan_match_method = :method, "
                "titan_match_score = :score WHERE product_id = :pid"),
            matches,
        )

        # 3) Backfill blank scientific names (never overwrites eStock's own).
        if backfills:
            session.execute(
                sql("UPDATE products SET scientific_name = :sci "
                    "WHERE product_id = :pid AND (scientific_name IS NULL OR scientific_name = '')"),
                backfills,
            )
        session.commit()

        # 4) The figures the eStock-edit decision needs.
        total, with_sci_after = session.execute(sql(
            "SELECT COUNT(*), SUM(CASE WHEN scientific_name IS NOT NULL AND scientific_name <> '' "
            "THEN 1 ELSE 0 END) FROM products WHERE is_deleted = 0"
        )).one()
        groups = session.execute(sql(
            "SELECT COUNT(*) FROM (SELECT scientific_name FROM products "
            "WHERE is_deleted = 0 AND scientific_name IS NOT NULL AND scientific_name <> '' "
            "GROUP BY scientific_name HAVING COUNT(*) >= 2) g"
        )).scalar()
        with_alt = session.execute(sql(
            "SELECT COUNT(*) FROM products p WHERE p.is_deleted = 0 "
            "AND p.scientific_name IS NOT NULL AND p.scientific_name <> '' "
            "AND EXISTS (SELECT 1 FROM products a WHERE a.is_deleted = 0 "
            "AND a.scientific_name = p.scientific_name AND a.product_id <> p.product_id)"
        )).scalar()

        print("\n=== Consolidation figures ===")
        print(f"titan_drugs mirror:          {len(titan_rows):,} rows")
        print(f"products mapped to Titan:    {len(matches):,} / {total:,}")
        print(f"products with scientific:    {with_sci_after:,} / {total:,} "
              f"(backfilled {len(backfills):,} this run)")
        print(f"substitution groups (>=2):   {groups:,}")
        print(f"products with >=1 alternative in catalogue: {with_alt:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
