"""Read-only audit: does the real catalogue's ``product_code`` hold barcodes?

The barcode scanner resolves a scanned GTIN through ``product_barcodes`` first
and falls back to ``Product.code``. Whether that fallback is worth anything
depends entirely on what eStock's ``product_code`` actually contains — the dev
seed uses "P1000"-style internal codes, and nothing in the repo proves the live
data is different.

Run this against the live mirror BEFORE relying on the fallback:

    cd src/backend && python tools/gtin_audit.py

* Many valid GTINs -> run the CEO-only backfill and most scans resolve on day
  one (``POST /api/catalogue/gtin-backfill``).
* Few or none      -> expected; the map builds itself through learn-on-scan as
  staff count, converging over the first few sessions.

Writes nothing. Safe to run on production.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import models as m  # noqa: E402
from app.db.base import SessionLocal  # noqa: E402
from app.services import gs1  # noqa: E402


def audit(limit: int | None = None) -> dict:
    with SessionLocal() as session:
        stmt = select(m.Product.product_id, m.Product.code, m.Product.fast_code).where(
            m.Product.is_deleted == False  # noqa: E712
        )
        if limit:
            stmt = stmt.limit(limit)  # .limit() only — .offset() breaks SQL Server 2008
        rows = session.execute(stmt).all()

    lengths: Counter[int] = Counter()
    digits_only = valid_code = valid_fast = missing = 0
    samples: list[dict] = []

    for pid, code, fast in rows:
        if not code:
            missing += 1
        else:
            lengths[len(code)] += 1
            if code.isdigit():
                digits_only += 1
            if gs1.normalize_gtin(code):
                valid_code += 1
                if len(samples) < 20:
                    samples.append({"product_id": pid, "code": code,
                                    "gtin": gs1.normalize_gtin(code)})
        if fast and gs1.normalize_gtin(fast):
            valid_fast += 1

    return {
        "products": len(rows),
        "code_missing": missing,
        "code_digits_only": digits_only,
        "code_valid_gtin": valid_code,
        "fast_code_valid_gtin": valid_fast,
        "code_length_histogram": dict(sorted(lengths.items())),
        "samples": samples,
    }


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    r = audit(limit)
    total = r["products"] or 1
    pct = 100.0 * r["code_valid_gtin"] / total

    print("=" * 62)
    print("GTIN audit — is Product.code a real barcode?")
    print("=" * 62)
    print(f"  products scanned      : {r['products']:,}")
    print(f"  code missing/empty    : {r['code_missing']:,}")
    print(f"  code digits-only      : {r['code_digits_only']:,}")
    print(f"  code IS a valid GTIN  : {r['code_valid_gtin']:,}  ({pct:.1f}%)")
    print(f"  fast_code valid GTIN  : {r['fast_code_valid_gtin']:,}")
    print(f"  code length histogram : {r['code_length_histogram']}")
    if r["samples"]:
        print("\n  samples:")
        for s in r["samples"]:
            print(f"    #{s['product_id']:<8} {s['code']:<16} -> {s['gtin']}")

    print()
    if pct >= 50:
        print(f"  => {pct:.0f}% already carry barcodes. Preview then run the backfill:")
        print("     GET  /api/catalogue/gtin-backfill/preview")
        print("     POST /api/catalogue/gtin-backfill   (CEO only)")
    else:
        print("  => The catalogue uses internal codes, not barcodes.")
        print("     Expected. The map builds itself via learn-on-scan during الجرد;")
        print("     no data-entry project needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
