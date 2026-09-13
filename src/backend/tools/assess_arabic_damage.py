#!/usr/bin/env python3
"""
Assess Arabic text corruption damage in ProCare database.

This script counts rows where Arabic characters were replaced with '?' due to
SQL Server collation (SQL_Latin1_General_CP1_CI_AS lacking Arabic codepage support).

Run BEFORE repair_arabic.py to establish a baseline, then re-run AFTER to verify repair.

Usage:
    python assess_arabic_damage.py
"""

from sqlalchemy import create_engine, text, Column, String, Integer
from sqlalchemy.orm import sessionmaker
from app.db.base import DATABASE_URL
from app.db.models import Customer, Vendor, Product, Employee, Branch, Job, Unit
import os


def count_corrupted_names(session, model_class, name_fields):
    """Count rows where name contains '?' characters (corruption marker)."""
    corrupted = {}
    total = 0

    for field_name in name_fields:
        col = getattr(model_class, field_name, None)
        if col is None:
            continue

        # Count rows where the field contains '?' (corruption indicator)
        query = session.query(model_class).filter(col.ilike('%?%'))
        count = query.count()
        if count > 0:
            corrupted[f"{model_class.__tablename__}.{field_name}"] = count
            total += count

    return corrupted, total


def assess_damage():
    """Assess the extent of Arabic corruption in the database."""
    engine = create_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("=" * 80)
    print("ProCare Arabic Corruption Assessment")
    print("=" * 80)
    print()

    assessments = {
        Customer: ["name_ar"],
        Vendor: ["name_ar"],
        Product: ["name_ar"],
        Employee: ["name_ar"],
        Branch: ["branch_name_ar"],
        Job: ["name_ar"],
        Unit: ["name_ar"],
    }

    total_corrupted = 0
    corruption_by_table = {}

    for model_class, fields in assessments.items():
        corrupted, count = count_corrupted_names(session, model_class, fields)
        if corrupted:
            print(f"❌ {model_class.__tablename__}")
            for field, num_rows in corrupted.items():
                print(f"   {field}: {num_rows:,} rows with '?' corruption")
                total_corrupted += num_rows
                table_name = model_class.__tablename__
                if table_name not in corruption_by_table:
                    corruption_by_table[table_name] = {}
                corruption_by_table[table_name][field] = num_rows
        else:
            total_rows = session.query(model_class).count()
            print(f"✅ {model_class.__tablename__}: {total_rows:,} rows, no corruption detected")
        print()

    print("=" * 80)
    print(f"TOTAL CORRUPTED ROWS: {total_corrupted:,}")
    print("=" * 80)
    print()

    # Breakdown by table
    if corruption_by_table:
        print("Summary by Table (for repair prioritization):")
        print()
        sorted_tables = sorted(
            corruption_by_table.items(),
            key=lambda x: sum(x[1].values()),
            reverse=True
        )
        for table_name, fields in sorted_tables:
            total_for_table = sum(fields.values())
            pct = (total_for_table / total_corrupted * 100) if total_corrupted > 0 else 0
            print(f"  {table_name:25} {total_for_table:7,} rows  ({pct:5.1f}%)")
        print()

    # Recommendations
    print("Recommendations:")
    print("-" * 80)
    print("1. Run AFTER backend migration to NVARCHAR columns (prevents new corruption)")
    print("2. Repair Priority:")
    if total_corrupted > 0:
        print(f"   - Critical: customers (staff use lookup daily)")
        print(f"   - Critical: vendors (ordering & payments)")
        print(f"   - Important: products (POS search & sales)")
        print(f"   - Normal: employees, branches, jobs (reference data)")
    else:
        print("   ✅ No corruption detected - data is clean!")
    print()
    print("3. To repair:")
    print("   - Run: python repair_arabic.py --table customers --table vendors")
    print("   - This re-syncs names from eStock source over the corrupted rows")
    print()

    session.close()


if __name__ == "__main__":
    # Add the backend directory to the path so imports work
    import sys
    sys.path.insert(0, os.path.dirname(__file__))

    assess_damage()
