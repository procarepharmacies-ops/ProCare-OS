#!/usr/bin/env python3
"""
assess_arabic_damage.py — quantify Arabic text corruption in ProCare database.

SQL Server collation (SQL_Latin1_General_CP1_AS) lacked Arabic codepage support.
This script counts rows where name_ar contains '?' corruption markers,
establishing a baseline before repair and verifying success after.

Usage:
    python assess_arabic_damage.py [--db procare.db|--connection-string]
"""

import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models import (
    Customer, Vendor, Product, Employee, Branch, Job, Unit
)
from app.db.database import get_session, get_engine


def assess_corruption(session) -> dict:
    """Count corruption extent across tables."""

    results = {
        "tables": {},
        "total_rows": 0,
        "corrupted_rows": 0,
        "corruption_pct": 0.0,
    }

    tables = [
        ("customers", Customer, "name_ar"),
        ("vendors", Vendor, "name_ar"),
        ("products", Product, "name_ar"),
        ("employees", Employee, "name_ar"),
        ("branches", Branch, "name_ar"),
        ("jobs", Job, "name_ar"),
        ("units", Unit, "name_ar"),
    ]

    for table_name, model, field_name in tables:
        try:
            # Count total rows
            total = session.query(model).count()

            # Count corrupted rows (contain '?')
            corrupted = session.query(model).filter(
                getattr(model, field_name).like('%?%')
            ).count()

            pct = (corrupted / total * 100) if total > 0 else 0.0

            results["tables"][table_name] = {
                "total": total,
                "corrupted": corrupted,
                "pct": round(pct, 2),
            }

            results["total_rows"] += total
            results["corrupted_rows"] += corrupted

        except Exception as e:
            results["tables"][table_name] = {
                "error": str(e),
                "total": None,
                "corrupted": None,
                "pct": None,
            }

    if results["total_rows"] > 0:
        results["corruption_pct"] = round(
            results["corrupted_rows"] / results["total_rows"] * 100, 2
        )

    return results


def print_report(results: dict):
    """Print formatted assessment report."""

    print("\n" + "=" * 70)
    print("ARABIC TEXT CORRUPTION ASSESSMENT")
    print("=" * 70)

    print(f"\nTotal rows examined:     {results['total_rows']}")
    print(f"Corrupted rows:          {results['corrupted_rows']}")
    print(f"Corruption rate:         {results['corruption_pct']}%")

    print("\n" + "-" * 70)
    print(f"{'Table':<15} {'Total':<10} {'Corrupted':<10} {'Rate':<10}")
    print("-" * 70)

    for table_name in sorted(results["tables"].keys()):
        info = results["tables"][table_name]

        if "error" in info:
            print(f"{table_name:<15} ERROR: {info['error']}")
        else:
            total = info["total"]
            corrupted = info["corrupted"]
            pct = info["pct"]
            print(f"{table_name:<15} {total:<10} {corrupted:<10} {pct}%")

    print("-" * 70)

    # Priority ranking
    priority = sorted(
        [(t, info) for t, info in results["tables"].items() if "error" not in info],
        key=lambda x: x[1]["corrupted"],
        reverse=True
    )

    if priority:
        print("\nREPAIR PRIORITY (by count):")
        for table_name, info in priority:
            if info["corrupted"] > 0:
                print(f"  {table_name:<15} {info['corrupted']} rows")

    print("\n" + "=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Assess Arabic text corruption in ProCare database"
    )
    parser.add_argument(
        "--db",
        type=str,
        help="SQLite database path (overrides env PROCARE_DB)"
    )
    parser.add_argument(
        "--connection-string",
        type=str,
        help="SQL Server connection string (overrides env PROCARE_CONNECTION_STRING)"
    )

    args = parser.parse_args()

    try:
        # Initialize database
        engine = get_engine()
        session = get_session()

        # Run assessment
        results = assess_corruption(session)

        # Print report
        print_report(results)

        # Exit code: 0 if no corruption, 1 if corruption found
        sys.exit(0 if results["corrupted_rows"] == 0 else 1)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    finally:
        try:
            session.close()
        except:
            pass


if __name__ == "__main__":
    main()
