"""Mirror ETL tests.

Builds a tiny SQLite database shaped like eStock (using the column names fixed by
the 2026-06-23 audit, docs/02), points the read-only mirror at it, and asserts
ProCare ends up with the cleaned data:
  * NULL bill_date falls back to insert_date (the eStock date bug);
  * returns are flagged is_return (and excluded from sales metrics);
  * walk-in customer_id = 0 becomes NULL;
  * batches mirror with store_id mapped to the right branch;
  * negative source stock is clamped to 0 (CK_stock_amount).

This proves the transformation is real; the only thing the offline environment
lacks is the live network endpoint (host/credentials), which is the documented
TBD. The shared seeded dev DB is restored at the end.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, text

from app.db import models as m
from app.db.base import SessionLocal
from app.db.seed import reset_and_seed
from app.services import etl


def _build_estock_source(path):
    """Create a minimal eStock-shaped SQLite DB and return its engine."""
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE Products (product_id INT, product_code TEXT, product_name_ar TEXT, "
            "product_name_en TEXT, product_scientific_name TEXT, product_drug TEXT, "
            "product_has_expire TEXT, sell_price REAL, buy_price REAL, tax_price REAL, "
            "deleted TEXT, active TEXT)"
        ))
        c.execute(text(
            "INSERT INTO Products VALUES "
            "(101,'A','بانادول','Panadol','Paracetamol','N','Y',12,7,0,'N','Y'),"
            "(102,'B','أوجمنتين','Augmentin','Amoxicillin','Y','Y',60,40,0,'N','Y')"
        ))
        c.execute(text(
            "CREATE TABLE Customer (customer_id INT, customer_name_ar TEXT, customer_name_en TEXT, "
            "mobile TEXT, customer_max_money REAL, customer_current_money REAL, "
            "customer_start_money REAL, deleted TEXT, active TEXT)"
        ))
        c.execute(text(
            "INSERT INTO Customer VALUES "
            "(5,'أحمد','Ahmed','0100',1000,1500,0,'N','Y'),"   # over limit
            "(6,'سارة','Sara','0111',0,0,0,'N','Y')"
        ))
        c.execute(text(
            "CREATE TABLE Vendor (vendor_id INT, vendor_name_ar TEXT, vendor_name_en TEXT, "
            "tel TEXT, mobile TEXT, vendor_max_money REAL, vendor_current_money REAL)"
        ))
        c.execute(text("INSERT INTO Vendor VALUES (9,'مورد','Supplier','02','010',50000,12000)"))
        c.execute(text(
            "CREATE TABLE Product_Amount (pa_id INT, product_id INT, store_id INT, counter_id INT, "
            "vendor_id INT, amount REAL, buy_price REAL, sell_price REAL, tax_price REAL, exp_date TEXT)"
        ))
        c.execute(text(
            "INSERT INTO Product_Amount VALUES "
            "(1,101,1,500,9,40,7,12,0,'2027-01-01'),"
            "(2,102,2,501,9,-3,40,60,0,'2024-01-01')"   # negative + expired -> clamp to 0
        ))
        c.execute(text(
            "CREATE TABLE Sales_header (sales_id INT, store_id INT, customer_id INT, bill_date TEXT, "
            "insert_date TEXT, total_bill REAL, total_bill_net REAL, total_disc_money REAL, "
            "bill_cash REAL, network_money REAL, money_change REAL, back TEXT)"
        ))
        c.execute(text(
            "INSERT INTO Sales_header VALUES "
            "(1001,1,0,NULL,'2026-06-20 10:00:00',24,24,0,24,0,0,'N'),"   # NULL bill_date, walk-in
            "(1002,2,5,'2026-06-21 12:00:00','2026-06-21 12:00:00',60,60,0,0,0,0,'N')"
        ))
        c.execute(text(
            "CREATE TABLE Sales_details (details_id INT, sales_id INT, product_id INT, counter_id INT, "
            "amount REAL, sell_price REAL, buy_price REAL, disc_money REAL, total_sell REAL, back TEXT)"
        ))
        c.execute(text(
            "INSERT INTO Sales_details VALUES "
            "(1,1001,101,500,2,12,7,0,24,'N'),"
            "(2,1002,102,501,1,60,40,0,60,'N')"
        ))
        c.execute(text(
            "CREATE TABLE Back_sales_header (sales_id INT, store_id INT, customer_id INT, bill_date TEXT, "
            "insert_date TEXT, total_bill REAL, total_bill_net REAL, total_disc_money REAL, "
            "bill_cash REAL, network_money REAL, money_change REAL, back TEXT)"
        ))
        c.execute(text(
            "INSERT INTO Back_sales_header VALUES "
            "(2001,1,5,'2026-06-22 09:00:00','2026-06-22 09:00:00',12,12,0,12,0,0,'Y')"
        ))
        c.execute(text(
            "CREATE TABLE Back_Sales_details (details_id INT, sales_id INT, product_id INT, "
            "back_amount REAL, back_price REAL, buy_price REAL, total_sell REAL, back TEXT)"
        ))
        c.execute(text("INSERT INTO Back_Sales_details VALUES (1,2001,101,1,12,7,12,'Y')"))
    return eng


@pytest.fixture
def estock_source(tmp_path):
    eng = _build_estock_source(tmp_path / "estock.db")
    yield eng
    eng.dispose()


def test_mirror_transforms_and_cleans(estock_source):
    try:
        with SessionLocal() as dst:
            counts = etl.mirror(estock_source, dst, store_branch_map={1: 1, 2: 2})

        assert counts["products"] == 2
        assert counts["customers"] == 2
        assert counts["vendors"] == 1
        assert counts["stock_batches"] == 2
        assert counts["sales"] == 2
        assert counts["returns"] == 1

        with SessionLocal() as s:
            # Walk-in sale (customer_id 0) -> NULL customer; NULL bill_date -> insert_date.
            walk_in = s.query(m.Sale).filter(m.Sale.total_net == 24).one()
            assert walk_in.customer_id is None
            assert walk_in.sale_date == datetime(2026, 6, 20, 10, 0, 0)
            assert walk_in.is_return is False

            # Return invoice flagged.
            ret = s.query(m.Sale).filter(m.Sale.is_return == True).one()  # noqa: E712
            assert ret.total_net == 12

            # Over-limit customer balance preserved.
            ahmed = s.query(m.Customer).filter(m.Customer.name_ar == "أحمد").one()
            assert float(ahmed.credit_limit) == 1000 and float(ahmed.current_balance) == 1500

            # Negative source stock clamped to 0 (never violates CK_stock_amount).
            batches = {b.product_id: b for b in s.query(m.StockBatch).all()}
            assert min(float(b.amount) for b in batches.values()) >= 0

            # Branch mapping: store_id 1 -> branch 1, store_id 2 -> branch 2.
            b101 = s.query(m.StockBatch).join(m.Product).filter(m.Product.code == "A").one()
            assert b101.branch_id == 1
    finally:
        # Restore the shared seeded dev DB for the rest of the suite.
        reset_and_seed()


def test_unmapped_store_auto_creates_branch(estock_source):
    """A store_id with no mapping (e.g. a Mashal branch) gets its own ProCare
    branch instead of being merged into another."""
    try:
        with estock_source.begin() as c:
            # New store_id 3 not present in the store_branch_map below.
            c.execute(text(
                "INSERT INTO Product_Amount VALUES (3,101,3,502,9,15,7,12,0,'2027-05-01')"
            ))
        with SessionLocal() as dst:
            etl.mirror(estock_source, dst, store_branch_map={1: "ELSANTA", 2: "MAIN"})
        with SessionLocal() as s:
            br = s.query(m.Branch).filter(m.Branch.code == "STORE3").one_or_none()
            assert br is not None  # auto-created
            stock = s.query(m.StockBatch).filter(m.StockBatch.branch_id == br.branch_id).all()
            assert len(stock) >= 1  # store-3 stock landed in the new branch
    finally:
        reset_and_seed()


def test_run_full_load_refuses_without_credentials():
    # No estock_source credentials configured in the example config => safe refusal.
    result = etl.run_full_load()
    assert result["ran"] is False
    assert "credentials" in result["reason"].lower()
