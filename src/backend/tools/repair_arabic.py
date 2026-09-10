"""Repair Arabic text that VARCHAR storage destroyed, and report what is left.

Background
----------
ProCare's own database has collation SQL_Latin1_General_CP1_CI_AS, whose
codepage contains no Arabic. A VARCHAR column in that database therefore
cannot hold Arabic at all: SQL Server replaces every Arabic character with
'?' *at write time*, silently. Reading it back gives '????' and the original
text is gone -- there is nothing left in the row to decode.

So a repair has two halves, and both are needed:

1. ensure_arabic_columns_unicode (app/db/migrate.py, runs at startup) widens
   the affected columns to NVARCHAR so that new writes survive.
2. This tool re-fetches the lost values from the one place that still holds
   them -- the live eStock database, whose own tables are Arabic_CI_AS -- and
   writes them back through the now-Unicode columns.

Run --check first: it reports how many rows are still damaged per column
without writing anything.

Usage
-----
    python tools/repair_arabic.py --check
    python tools/repair_arabic.py --apply
    python tools/repair_arabic.py --apply --only customers,vendors
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.base import engine  # noqa: E402

# Columns worth reporting on: the ones a pharmacist actually reads on screen.
_CHECK_COLUMNS = [
    ("customers", "name_ar"),
    ("customers", "name_en"),
    ("vendors", "name_ar"),
    ("vendors", "name_en"),
    ("products", "name_ar"),
    ("products", "name_en"),
    ("products", "scientific_name"),
    ("employees", "name_ar"),
    ("employees", "name_en"),
    ("companies", "name_ar"),
    ("product_groups", "name_ar"),
    ("gl_journal_entries", "notes"),
    ("gl_journal_entries", "actual_cashier"),
    ("employee_tasks", "title"),
    ("employee_tasks", "details"),
]

# How to re-pull each repairable table from eStock:
#   dest table, dest key, source table, source key, [(dest col, source col)]
# The key is eStock's own primary key, which ProCare stores verbatim as its
# own id for these mirrored master tables.
_REPAIRS = [
    (
        "products",
        "product_id",
        "Products",
        "product_id",
        [
            ("name_ar", "product_name_ar"),
            ("name_en", "product_name_en"),
            ("scientific_name", "product_scientific_name"),
        ],
    ),
    (
        "vendors",
        "vendor_id",
        "Vendor",
        "vendor_id",
        [("name_ar", "vendor_name_ar"), ("name_en", "vendor_name_en")],
    ),
    (
        "customers",
        "customer_id",
        "Customer",
        "customer_id",
        [("name_ar", "customer_name_ar"), ("name_en", "customer_name_en")],
    ),
]


def _damaged(conn, table: str, column: str) -> int:
    """Rows whose value contains a run of '?' -- the mojibake signature."""
    try:
        return (
            conn.execute(
                text(
                    f"SELECT COUNT(*) FROM [{table}] "
                    f"WHERE CAST([{column}] AS NVARCHAR(MAX)) LIKE N'%[?][?]%'"
                )
            ).scalar()
            or 0
        )
    except Exception:  # noqa: BLE001 -- a missing table is not an error here
        return -1


def _column_type(conn, table: str, column: str) -> str:
    row = conn.execute(
        text(
            """
            SELECT ty.name FROM sys.columns c
            JOIN sys.types ty ON ty.user_type_id = c.user_type_id
            WHERE c.object_id = OBJECT_ID(:t) AND c.name = :c
            """
        ),
        {"t": table, "c": column},
    ).first()
    return row[0] if row else "-"


def check() -> int:
    """Report damage per column. Returns the number of damaged columns."""
    bad = 0
    with engine.connect() as conn:
        print(f"{'column':<42} {'type':<10} {'damaged':>10} {'total':>12}")
        print("-" * 80)
        for table, column in _CHECK_COLUMNS:
            n = _damaged(conn, table, column)
            if n < 0:
                continue
            typ = _column_type(conn, table, column)
            total = conn.execute(text(f"SELECT COUNT(*) FROM [{table}]")).scalar() or 0
            flag = ""
            if typ in ("varchar", "char", "text"):
                flag = "  <- STILL VARCHAR, cannot hold Arabic"
            if n:
                bad += 1
            print(f"{table + '.' + column:<42} {typ:<10} {n:>10,} {total:>12,}{flag}")
    return bad


def repair(only: set[str] | None) -> None:
    """Re-pull Arabic master data from eStock into the (now NVARCHAR) columns."""
    url = settings.estock_sqlalchemy_url()
    if not url:
        print("eStock source is not configured -- nothing to repair from.")
        return
    source = create_engine(url)

    for dest, dest_key, src_table, src_key, cols in _REPAIRS:
        if only and dest not in only:
            continue
        with engine.connect() as conn:
            types = {c: _column_type(conn, dest, c) for c, _ in cols}
        narrow = [c for c, t in types.items() if t in ("varchar", "char", "text")]
        if narrow:
            print(
                f"{dest}: SKIPPED -- {', '.join(narrow)} is still VARCHAR. Restart the "
                "backend (which runs ensure_arabic_columns_unicode) first, otherwise "
                "this rewrite would store '?' all over again."
            )
            continue

        src_cols = ", ".join([src_key] + [s for _, s in cols])
        with source.connect() as sc:
            rows = sc.execute(text(f"SELECT {src_cols} FROM [{src_table}]")).mappings().all()

        payload = [
            {"k": r[src_key], **{f"c{i}": r[s] for i, (_, s) in enumerate(cols)}}
            for r in rows
            if r[src_key] is not None
        ]
        if not payload:
            print(f"{dest}: source returned no rows -- skipped.")
            continue

        sets = ", ".join(f"[{d}] = :c{i}" for i, (d, _) in enumerate(cols))
        stmt = text(f"UPDATE [{dest}] SET {sets} WHERE [{dest_key}] = :k")

        updated = 0
        with engine.begin() as conn:
            for i in range(0, len(payload), 1000):
                updated += conn.execute(stmt, payload[i : i + 1000]).rowcount or 0
        print(f"{dest}: re-pulled {len(payload):,} source rows, {updated:,} rows updated.")


def repair_by_mobile() -> None:
    """Repair customer names by matching on mobile instead of on the row id.

    ProCare assigns its own autoincrement customer_id, so the source id is not
    stored anywhere and an id-keyed repair matches nothing. The mobile number
    is ASCII, so it survived the VARCHAR corruption intact and is the only
    uncorrupted natural key the two databases share.

    This covers every customer that carries a phone number -- which is every
    customer that loyalty, WhatsApp and the statement screens actually use.
    Rows with no mobile AND a destroyed name cannot be matched by any key;
    they are duplicates of the real rows (see the register-rebuild note in the
    module docstring) and are reported rather than guessed at.
    """
    url = settings.estock_sqlalchemy_url()
    if not url:
        print("eStock source is not configured -- nothing to repair from.")
        return
    source = create_engine(url)

    with engine.connect() as conn:
        for col in ("name_ar", "name_en"):
            if _column_type(conn, "customers", col) in ("varchar", "char", "text"):
                print(f"customers: SKIPPED -- {col} is still VARCHAR.")
                return

    with source.connect() as sc:
        rows = sc.execute(
            text("SELECT customer_name_ar, customer_name_en, mobile FROM [Customer]")
        ).mappings().all()

    by_mobile: dict[str, tuple] = {}
    for r in rows:
        mob = (r["mobile"] or "").strip()
        if mob and mob not in by_mobile:
            by_mobile[mob] = (r["customer_name_ar"], r["customer_name_en"])

    with engine.connect() as conn:
        damaged = conn.execute(
            text(
                "SELECT customer_id, mobile FROM customers "
                "WHERE name_ar LIKE N'%[?][?]%' "
                "AND mobile IS NOT NULL AND LTRIM(RTRIM(mobile)) <> ''"
            )
        ).all()

    payload = []
    for cid, mob in damaged:
        hit = by_mobile.get((mob or "").strip())
        if hit:
            payload.append({"k": cid, "a": hit[0], "e": hit[1]})

    if not payload:
        print("customers: no mobile matched the source register.")
        return

    stmt = text("UPDATE customers SET name_ar = :a, name_en = :e WHERE customer_id = :k")
    with engine.begin() as conn:
        for i in range(0, len(payload), 1000):
            conn.execute(stmt, payload[i : i + 1000])
    print(
        f"customers: matched {len(payload):,} of {len(damaged):,} damaged rows "
        f"by mobile and rewrote their names."
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Repair Arabic damaged by VARCHAR storage.")
    ap.add_argument("--check", action="store_true", help="report damage, write nothing")
    ap.add_argument("--apply", action="store_true", help="re-pull Arabic from eStock")
    ap.add_argument("--only", default="", help="comma-separated tables to repair")
    args = ap.parse_args()

    if not args.check and not args.apply:
        ap.error("pass --check or --apply")

    print("=== damage report (before) ===")
    check()

    if args.apply:
        only = {t.strip() for t in args.only.split(",") if t.strip()} or None
        print("\n=== repairing from eStock ===")
        repair(only)
        print("\n=== repairing customers (by mobile) ===")
        repair_by_mobile()
        print("\n=== damage report (after) ===")
        check()


if __name__ == "__main__":
    main()
