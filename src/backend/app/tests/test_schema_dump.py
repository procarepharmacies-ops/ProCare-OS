"""Phase 7 tests: the read-only eStock schema-dump / coverage tool."""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from tools import estock_schema_dump as dumptool  # noqa: E402


def _source(path):
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as c:
        # One table the ETL covers, one it does not.
        c.execute(text("CREATE TABLE Products (product_id INT, product_name_ar TEXT, sell_price REAL)"))
        c.execute(text("INSERT INTO Products VALUES (1,'صنف',10.0)"))
        c.execute(text("CREATE TABLE Branches_Product_Amount (bpa_id INT, product_id INT, store_id INT, amount REAL)"))
        c.execute(text("INSERT INTO Branches_Product_Amount VALUES (1,1,2,5.0),(2,1,2,7.0)"))
    return eng


def test_dump_flags_coverage_and_columns(tmp_path):
    eng = _source(tmp_path / "estock.db")
    try:
        dump = dumptool.dump_schema(eng, with_counts=True)
        assert dump["total_tables"] == 2
        # Products is in COVERED_SOURCE_TABLES; Branches_Product_Amount is not.
        assert "Products" in dump["covered"]
        assert "Branches_Product_Amount" in dump["uncovered"]
        assert dump["covered_count"] == 1 and dump["uncovered_count"] == 1

        products = next(t for t in dump["tables"] if t["name"] == "Products")
        assert {c["name"] for c in products["columns"]} == {"product_id", "product_name_ar", "sell_price"}
        assert products["row_count"] == 1

        bpa = next(t for t in dump["tables"] if t["name"] == "Branches_Product_Amount")
        assert bpa["row_count"] == 2 and bpa["covered"] is False
    finally:
        eng.dispose()


def test_coverage_is_case_insensitive(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'ci.db'}")
    try:
        with eng.begin() as c:
            c.execute(text("CREATE TABLE products (id INT)"))  # lowercase
        dump = dumptool.dump_schema(eng)
        assert "products" in dump["covered"]  # matched despite casing
    finally:
        eng.dispose()


def test_render_markdown_has_gap_section(tmp_path):
    eng = _source(tmp_path / "md.db")
    try:
        md = dumptool.render_markdown(dumptool.dump_schema(eng))
        assert "Coverage gap" in md
        assert "Branches_Product_Amount" in md
        assert "✅ `Products`" in md
    finally:
        eng.dispose()
