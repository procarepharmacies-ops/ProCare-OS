#!/usr/bin/env python3
"""
Repair Arabic text corruption in ProCare database by re-syncing from eStock.

The SQL Server collation (SQL_Latin1_General_CP1_CI_AS) lacks Arabic codepage support,
causing Arabic characters to be silently replaced with '?' on write. The backend fix
converted VARCHAR columns to NVARCHAR, which prevents NEW corruption.

This script repairs EXISTING corruption by re-fetching corrupted customer and vendor
names directly from the eStock source and updating them in place.

IMPORTANT: Run this AFTER the backend has been deployed with NVARCHAR columns.
           Otherwise, re-synced names will be corrupted again on write.

Usage:
    # Assess damage first
    python assess_arabic_damage.py

    # Then repair (off-peak, non-blocking)
    python repair_arabic.py --table customers --table vendors

    # Verify the repair
    python assess_arabic_damage.py

Flags:
    --table customers    Repair customer.name_ar
    --table vendors      Repair vendor.name_ar
    --dry-run            Show what would be updated without making changes
    --limit N            Process only N rows (for testing)
"""

import argparse
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.db.base import DATABASE_URL
from app.db.models import Customer, Vendor
from app.services.etl import _ResilientSource
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def get_estock_connection():
    """Get connection to eStock source database."""
    from app.config import ESTOCK_CONNECTIONS
    from app.services.etl import _ResilientSource

    # Use the first available branch connection (usually Elsanta)
    for branch_id, creds in ESTOCK_CONNECTIONS.items():
        if creds.get('enabled', True):
            logger.info(f"Connecting to eStock ({branch_id})...")
            return _ResilientSource(
                server=creds['server'],
                database=creds['database'],
                username=creds['username'],
                password=creds['password'],
                branch_id=branch_id
            )

    raise ValueError("No enabled eStock connections found in config")


def repair_customers(session, estock, dry_run=False, limit=None):
    """Repair corrupted customer names by re-fetching from eStock."""
    logger.info("Repairing customers...")

    # Find all corrupted customer rows (those with '?' in name_ar)
    corrupted = session.query(Customer).filter(
        Customer.name_ar.ilike('%?%')
    )

    if limit:
        corrupted = corrupted.limit(limit)

    rows = corrupted.all()

    if not rows:
        logger.info("  ✅ No corrupted customers found")
        return 0

    logger.info(f"  Found {len(rows):,} corrupted customers")

    # Fetch fresh data from eStock
    estock_customers = {}
    try:
        result = estock.execute(
            "SELECT cust_id, cust_name_ar, cust_name_en FROM Customar WHERE deleted=0"
        )
        for row in result.fetchall():
            estock_customers[row[0]] = {
                'name_ar': row[1],
                'name_en': row[2],
            }
        logger.info(f"  Fetched {len(estock_customers):,} customers from eStock")
    except Exception as e:
        logger.error(f"  ❌ Failed to fetch from eStock: {e}")
        return 0

    # Update corrupted rows
    updated = 0
    for customer in rows:
        if customer.source_id in estock_customers:
            estock_data = estock_customers[customer.source_id]
            old_name_ar = customer.name_ar
            new_name_ar = estock_data['name_ar']

            if old_name_ar != new_name_ar:
                if dry_run:
                    logger.info(
                        f"  [DRY-RUN] Would update customer {customer.source_id}: "
                        f"'{old_name_ar[:20]}...' → '{new_name_ar[:20]}...'"
                    )
                else:
                    customer.name_ar = new_name_ar
                    # Also update name_en if eStock has a different value
                    if customer.name_en != estock_data['name_en']:
                        customer.name_en = estock_data['name_en']
                    updated += 1
        else:
            logger.warning(f"  ⚠️  Customer {customer.source_id} not found in eStock")

    if not dry_run and updated > 0:
        session.commit()
        logger.info(f"  ✅ Updated {updated:,} customers")

    return updated


def repair_vendors(session, estock, dry_run=False, limit=None):
    """Repair corrupted vendor names by re-fetching from eStock."""
    logger.info("Repairing vendors...")

    # Find all corrupted vendor rows (those with '?' in name_ar)
    corrupted = session.query(Vendor).filter(
        Vendor.name_ar.ilike('%?%')
    )

    if limit:
        corrupted = corrupted.limit(limit)

    rows = corrupted.all()

    if not rows:
        logger.info("  ✅ No corrupted vendors found")
        return 0

    logger.info(f"  Found {len(rows):,} corrupted vendors")

    # Fetch fresh data from eStock
    estock_vendors = {}
    try:
        result = estock.execute(
            "SELECT Vendor_id, vendor_name_ar, vendor_name_en FROM Vendor WHERE deleted=0"
        )
        for row in result.fetchall():
            estock_vendors[row[0]] = {
                'name_ar': row[1],
                'name_en': row[2],
            }
        logger.info(f"  Fetched {len(estock_vendors):,} vendors from eStock")
    except Exception as e:
        logger.error(f"  ❌ Failed to fetch from eStock: {e}")
        return 0

    # Update corrupted rows
    updated = 0
    for vendor in rows:
        if vendor.source_id in estock_vendors:
            estock_data = estock_vendors[vendor.source_id]
            old_name_ar = vendor.name_ar
            new_name_ar = estock_data['name_ar']

            if old_name_ar != new_name_ar:
                if dry_run:
                    logger.info(
                        f"  [DRY-RUN] Would update vendor {vendor.source_id}: "
                        f"'{old_name_ar[:20]}...' → '{new_name_ar[:20]}...'"
                    )
                else:
                    vendor.name_ar = new_name_ar
                    # Also update name_en if eStock has a different value
                    if vendor.name_en != estock_data['name_en']:
                        vendor.name_en = estock_data['name_en']
                    updated += 1
        else:
            logger.warning(f"  ⚠️  Vendor {vendor.source_id} not found in eStock")

    if not dry_run and updated > 0:
        session.commit()
        logger.info(f"  ✅ Updated {updated:,} vendors")

    return updated


def main():
    parser = argparse.ArgumentParser(
        description="Repair Arabic text corruption in ProCare database"
    )
    parser.add_argument(
        "--table",
        action="append",
        dest="tables",
        choices=["customers", "vendors"],
        help="Table to repair (can be specified multiple times)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only N rows (for testing)"
    )

    args = parser.parse_args()

    if not args.tables:
        parser.print_help()
        return 1

    logger.info("=" * 80)
    logger.info("ProCare Arabic Text Repair")
    logger.info("=" * 80)

    if args.dry_run:
        logger.info("🔍 DRY-RUN MODE - No changes will be made")

    if args.limit:
        logger.info(f"Processing limited to {args.limit} rows")

    logger.info()

    # Set up database connection
    engine = create_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Get eStock connection
    try:
        estock = get_estock_connection()
    except Exception as e:
        logger.error(f"Failed to connect to eStock: {e}")
        return 1

    total_updated = 0

    try:
        # Repair requested tables
        if "customers" in args.tables:
            updated = repair_customers(session, estock, args.dry_run, args.limit)
            total_updated += updated
            logger.info()

        if "vendors" in args.tables:
            updated = repair_vendors(session, estock, args.dry_run, args.limit)
            total_updated += updated
            logger.info()

        logger.info("=" * 80)
        if args.dry_run:
            logger.info(f"Would have updated {total_updated:,} rows (DRY-RUN)")
        else:
            logger.info(f"✅ Repair complete: {total_updated:,} rows updated")
        logger.info("=" * 80)

        # Verification step
        logger.info()
        logger.info("Next steps:")
        logger.info("1. Verify repair by running: python assess_arabic_damage.py")
        logger.info("2. Run search tests in POS to confirm customer/vendor lookups work")
        logger.info("3. Monitor sync logs for any new issues")

        return 0

    except Exception as e:
        logger.error(f"❌ Error during repair: {e}", exc_info=True)
        session.rollback()
        return 1

    finally:
        session.close()


if __name__ == "__main__":
    # Add the backend directory to the path so imports work
    import sys
    sys.path.insert(0, os.path.dirname(__file__))

    sys.exit(main())
