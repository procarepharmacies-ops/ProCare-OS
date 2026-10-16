#!/usr/bin/env python3
"""
repair_arabic.py — restore corrupted Arabic text from eStock source.

Remediation tool for data corrupted by SQL Server collation issues.
Re-fetches corrupted names from eStock source and updates ProCare database.

Supports:
  --dry-run: Preview changes without modifying database
  --limit N: Process only N rows
  --table: Specific table to repair (customers|vendors; default: both)

Usage:
    python repair_arabic.py [--dry-run] [--limit 100] [--table customers]
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, List, Tuple

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import Customer, Vendor
from app.db.database import get_session, get_engine
from app.services.etl import _ResilientSource


class ArabicRepair:
    """Repair corrupted Arabic text by re-fetching from eStock."""

    def __init__(self, dry_run: bool = False, limit: Optional[int] = None):
        self.dry_run = dry_run
        self.limit = limit
        self.session = get_session()
        self.source = _ResilientSource()
        self.repair_log: List[Tuple[str, int, str, str]] = []
        self.stats = {
            "examined": 0,
            "corrupted_found": 0,
            "repaired": 0,
            "errors": 0,
        }

    def repair_customers(self) -> int:
        """Repair corrupted customer names from eStock source."""

        print("\n" + "=" * 70)
        print("REPAIRING CUSTOMERS")
        print("=" * 70)

        query = self.session.query(Customer).filter(
            Customer.name_ar.like('%?%')
        )

        if self.limit:
            query = query.limit(self.limit)

        corrupted = query.all()

        print(f"\nFound {len(corrupted)} corrupted customer records")

        if not corrupted:
            return 0

        for customer in corrupted:
            self.stats["examined"] += 1
            self.stats["corrupted_found"] += 1

            try:
                # Fetch from eStock source by code
                source_customer = self.source.fetchone(
                    "SELECT * FROM Customer WHERE Customer_code = ?",
                    (customer.code,)
                )

                if not source_customer or not source_customer.get("Customer_name_ar"):
                    self.repair_log.append(
                        ("customer", customer.id, "ERROR", "Not found in eStock")
                    )
                    self.stats["errors"] += 1
                    continue

                old_name = customer.name_ar
                new_name = source_customer["Customer_name_ar"]

                if not self.dry_run:
                    customer.name_ar = new_name
                    self.session.add(customer)

                self.repair_log.append(
                    ("customer", customer.id, old_name, new_name)
                )
                self.stats["repaired"] += 1

                print(f"  ✓ Customer {customer.code}: {old_name[:30]}... → {new_name[:30]}...")

            except Exception as e:
                self.repair_log.append(
                    ("customer", customer.id, "ERROR", str(e))
                )
                self.stats["errors"] += 1
                print(f"  ✗ Customer {customer.code}: {str(e)}")

        if not self.dry_run and self.stats["repaired"] > 0:
            self.session.commit()
            print(f"\n✓ Committed {self.stats['repaired']} customer repairs")

        return self.stats["repaired"]

    def repair_vendors(self) -> int:
        """Repair corrupted vendor names from eStock source."""

        print("\n" + "=" * 70)
        print("REPAIRING VENDORS")
        print("=" * 70)

        query = self.session.query(Vendor).filter(
            Vendor.name_ar.like('%?%')
        )

        if self.limit:
            query = query.limit(self.limit)

        corrupted = query.all()

        print(f"\nFound {len(corrupted)} corrupted vendor records")

        if not corrupted:
            return 0

        for vendor in corrupted:
            self.stats["examined"] += 1
            self.stats["corrupted_found"] += 1

            try:
                # Fetch from eStock source by code
                source_vendor = self.source.fetchone(
                    "SELECT * FROM Vendor WHERE Vendor_code = ?",
                    (vendor.code,)
                )

                if not source_vendor or not source_vendor.get("Vendor_name_ar"):
                    self.repair_log.append(
                        ("vendor", vendor.id, "ERROR", "Not found in eStock")
                    )
                    self.stats["errors"] += 1
                    continue

                old_name = vendor.name_ar
                new_name = source_vendor["Vendor_name_ar"]

                if not self.dry_run:
                    vendor.name_ar = new_name
                    self.session.add(vendor)

                self.repair_log.append(
                    ("vendor", vendor.id, old_name, new_name)
                )
                self.stats["repaired"] += 1

                print(f"  ✓ Vendor {vendor.code}: {old_name[:30]}... → {new_name[:30]}...")

            except Exception as e:
                self.repair_log.append(
                    ("vendor", vendor.id, "ERROR", str(e))
                )
                self.stats["errors"] += 1
                print(f"  ✗ Vendor {vendor.code}: {str(e)}")

        if not self.dry_run and self.stats["repaired"] > 0:
            self.session.commit()
            print(f"\n✓ Committed {self.stats['repaired']} vendor repairs")

        return self.stats["repaired"]

    def print_summary(self):
        """Print repair summary and audit log."""

        print("\n" + "=" * 70)
        print("REPAIR SUMMARY")
        print("=" * 70)

        print(f"\nRecords examined:     {self.stats['examined']}")
        print(f"Corrupted found:      {self.stats['corrupted_found']}")
        print(f"Successfully repaired: {self.stats['repaired']}")
        print(f"Errors:               {self.stats['errors']}")

        if self.dry_run:
            print("\n⚠️  DRY RUN MODE — No changes committed to database")
        else:
            print("\n✓ Changes committed to database")

        print("\n" + "-" * 70)
        print("AUDIT LOG")
        print("-" * 70)

        for table, record_id, old_val, new_val in self.repair_log:
            if "ERROR" in old_val or "ERROR" in new_val:
                print(f"❌ {table} #{record_id}: {new_val}")
            else:
                print(f"✓ {table} #{record_id}")
                if old_val != "ERROR":
                    print(f"   Before: {old_val[:50]}")
                    print(f"   After:  {new_val[:50]}")

        print("=" * 70 + "\n")

    def close(self):
        """Close database session."""
        try:
            self.session.close()
        except:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Repair corrupted Arabic text from eStock source"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying database"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only N corrupted records"
    )
    parser.add_argument(
        "--table",
        type=str,
        choices=["customers", "vendors", "both"],
        default="both",
        help="Which table to repair (default: both)"
    )

    args = parser.parse_args()

    try:
        repair = ArabicRepair(
            dry_run=args.dry_run,
            limit=args.limit
        )

        repaired = 0

        if args.table in ("customers", "both"):
            repaired += repair.repair_customers()

        if args.table in ("vendors", "both"):
            repaired += repair.repair_vendors()

        repair.print_summary()
        repair.close()

        # Exit code: 0 if successful, 1 if errors occurred
        sys.exit(0 if repair.stats["errors"] == 0 else 1)

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
