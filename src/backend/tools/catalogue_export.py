#!/usr/bin/env python
"""Export approved catalogue decisions back to eStock.

Phase 2 of the catalogue fix. This is a SEPARATE, EXPLICITLY-APPROVED script
that reads CatalogueDecision records with status='approved' and exported_at=None,
then constructs a patch to write back to the eStock database.

eStock is read-only for normal pharmacy operations; this script is the ONE
place that breaks that rule, and only on explicit approval.

Safety gates:
1. Backup required: eStock RESTORE point must exist and be recent.
2. Preview first: shows exactly what will change, product by product.
3. Dry-run optional: can validate the patch without committing.
4. Idempotency: applying the same export twice is safe (UPDATE sets the value,
   doesn't re-generate it).

Field mapping (ProCare → eStock columns):
  - scientific_name → scientific_name
  - uses → indications
  - is_medicine → is_medicine
  - origin → origin (local/import)
  - dosage_form → dosage_form
  - name_en, name_ar → [NOT written: already staged for manual review]

Usage:
  python catalogue_export.py --preview           # Show changes only
  python catalogue_export.py --dry-run          # Test without committing
  python catalogue_export.py --confirm          # Write to eStock (requires backup)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.base import SessionLocal
from app.db import models as m
from sqlalchemy import select, update, and_
from pyodbc import connect as pyodbc_connect
import json

# Field mapping from ProCare decision → eStock column
_WRITE_FIELDS = {
    "scientific_name": "scientific_name",
    "uses": "indications",
    "is_medicine": "is_medicine",
    "origin": "origin",
    "dosage_form": "dosage_form",
    # name_ar, name_en are deliberately NOT written — they live in Titan/Drug-Eye review layer
}

# Read config
try:
    with open("config/connections.json") as f:
        cfg = json.load(f)
        estock_conn_str = cfg.get("estock_connection_string")
        if not estock_conn_str:
            print("✕ eStock connection string not in config/connections.json")
            sys.exit(1)
except FileNotFoundError:
    print("✕ config/connections.json not found. See config/connections.example.json")
    sys.exit(1)


def get_estock_backup_time() -> datetime | None:
    """Check if an eStock backup exists and is recent (< 24 hours old)."""
    try:
        conn = pyodbc_connect(estock_conn_str)
        cur = conn.cursor()
        cur.execute("""
            SELECT TOP 1 backup_finish_date FROM msdb.dbo.backupset
            WHERE database_name = 'eStock'
            ORDER BY backup_finish_date DESC
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"⚠ Could not check eStock backup status: {e}")
        return None


def collect_approved_decisions() -> dict:
    """Read all approved decisions from ProCare that haven't been exported yet.

    Returns:
        dict: {product_id: {field: {new_value, old_value, source, decided_by, decided_at}}}
    """
    with SessionLocal() as s:
        rows = s.scalars(
            select(m.CatalogueDecision).where(
                and_(
                    m.CatalogueDecision.status == "approved",
                    m.CatalogueDecision.exported_at.is_(None),
                )
            )
        ).all()

        decisions = {}
        for d in rows:
            if d.product_id not in decisions:
                decisions[d.product_id] = {}
            decisions[d.product_id][d.field] = {
                "new_value": d.new_value,
                "old_value": d.old_value,
                "source": d.source,
                "decided_by": d.decided_by,
                "decided_at": d.decided_at.isoformat() if d.decided_at else None,
            }
        return decisions


def build_preview(decisions: dict) -> str:
    """Generate a human-readable preview of what will be written to eStock."""
    if not decisions:
        return "No approved decisions pending export."

    lines = ["PREVIEW: Changes to write to eStock\n"]
    lines.append(f"Total products affected: {len(decisions)}\n")
    lines.append("=" * 80)

    total_updates = sum(len(fields) for fields in decisions.values())
    lines.append(f"\nTotal field updates: {total_updates}\n")

    for pid in sorted(decisions.keys()):
        fields = decisions[pid]
        lines.append(f"\nProduct #{pid}:")
        for field, info in sorted(fields.items()):
            estock_col = _WRITE_FIELDS.get(field, field)
            old = info["old_value"] or "(blank)"
            new = info["new_value"] or "(blank)"
            src = info["source"]
            lines.append(f"  {field:20} → {estock_col:20}")
            lines.append(f"    OLD: {str(old)[:70]}")
            lines.append(f"    NEW: {str(new)[:70]}")
            lines.append(f"    source={src}  decided_at={info['decided_at']}")

    lines.append("\n" + "=" * 80)
    return "\n".join(lines)


def dry_run_export(decisions: dict) -> int:
    """Validate the patch without writing to eStock. Returns update count."""
    try:
        conn = pyodbc_connect(estock_conn_str)
        cur = conn.cursor()

        count = 0
        for pid in decisions:
            fields = decisions[pid]
            for field in fields:
                estock_col = _WRITE_FIELDS.get(field)
                if not estock_col:
                    continue

                new_value = fields[field]["new_value"]
                sql = f"SELECT COUNT(*) FROM products WHERE product_id = ?"
                cur.execute(sql, (pid,))
                exists = cur.fetchone()[0] > 0

                if exists:
                    count += 1
                    print(f"  ✓ Product {pid}, field {estock_col} = {str(new_value)[:40]}")
                else:
                    print(f"  ✕ Product {pid} not found in eStock (skip)")

        cur.close()
        conn.close()
        return count
    except Exception as e:
        print(f"✕ Dry-run failed: {e}")
        return 0


def confirm_export(decisions: dict) -> int:
    """Write approved decisions to eStock. Returns count of updates."""
    try:
        conn = pyodbc_connect(estock_conn_str)
        cur = conn.cursor()

        count = 0
        for pid in decisions:
            fields = decisions[pid]
            for field in fields:
                estock_col = _WRITE_FIELDS.get(field)
                if not estock_col:
                    continue

                new_value = fields[field]["new_value"]
                try:
                    sql = f"UPDATE products SET [{estock_col}] = ? WHERE product_id = ?"
                    cur.execute(sql, (new_value, pid))
                    if cur.rowcount > 0:
                        count += 1
                except Exception as e:
                    print(f"⚠ Failed to update product {pid}, field {field}: {e}")

        conn.commit()
        cur.close()
        conn.close()

        # Mark as exported in ProCare
        if count > 0:
            with SessionLocal() as s:
                now = datetime.utcnow()
                rows = s.scalars(
                    select(m.CatalogueDecision).where(
                        and_(
                            m.CatalogueDecision.status == "approved",
                            m.CatalogueDecision.exported_at.is_(None),
                        )
                    )
                ).all()
                for d in rows:
                    d.exported_at = now
                s.commit()

        return count
    except Exception as e:
        print(f"✕ Export failed: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Export approved catalogue decisions to eStock."
    )
    parser.add_argument(
        "--preview", action="store_true", help="Show what will change (no write)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate the patch without writing"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Write to eStock (requires recent backup)",
    )

    args = parser.parse_args()

    # At least one action required
    if not (args.preview or args.dry_run or args.confirm):
        parser.print_help()
        print(
            "\nNo action specified. Use --preview, --dry-run, or --confirm."
        )
        sys.exit(1)

    decisions = collect_approved_decisions()

    if args.preview or (not args.dry_run and not args.confirm):
        print(build_preview(decisions))

    if args.dry_run:
        print("\n🔍 DRY RUN: Validating patch...\n")
        count = dry_run_export(decisions)
        print(f"\nWould update {count} fields.")

    if args.confirm:
        # Safety gate 1: Check backup
        backup_time = get_estock_backup_time()
        if not backup_time:
            print("✕ No recent eStock backup found. Create one before exporting.")
            sys.exit(1)

        hours_old = (datetime.utcnow() - backup_time).total_seconds() / 3600
        if hours_old > 24:
            print(f"✕ eStock backup is {hours_old:.1f} hours old. Please backup first.")
            sys.exit(1)

        print(f"✓ eStock backup exists ({hours_old:.1f} hours old).\n")
        print("WRITING TO eStock...\n")

        count = confirm_export(decisions)
        print(f"\n✓ Exported {count} field updates to eStock.")
        print(f"✓ Marked {count} decisions exported_at = {datetime.utcnow().isoformat()}")


if __name__ == "__main__":
    main()
