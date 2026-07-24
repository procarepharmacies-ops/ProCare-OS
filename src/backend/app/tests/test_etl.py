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

        # Shareholders + dividends (company_Owner / Gedo_Dividends_paied).
        c.execute(text(
            "CREATE TABLE company_Owner (coow_id INT, coow_code TEXT, coow_name_ar TEXT, "
            "coow_name_en TEXT, tel TEXT, mobile TEXT, address TEXT, coow_current_money REAL, "
            "coow_start_money REAL, active INT, deleted INT)"
        ))
        c.execute(text(
            "INSERT INTO company_Owner VALUES "
            "(1,'O1','أحمد المالك','Ahmed','02','010','طنطا',600000,500000,1,0),"
            "(2,'O2','سارة الشريك','Sara','02','011','المحلة',400000,400000,1,0),"
            "(3,'O3','شريك محذوف','Gone',NULL,NULL,NULL,0,0,1,1)"
        ))
        c.execute(text(
            "CREATE TABLE Gedo_Dividends_paied (dividends_id INT, coow_id INT, yaer_id INT, "
            "gf_id INT, paied_money REAL)"
        ))
        c.execute(text(
            "INSERT INTO Gedo_Dividends_paied VALUES "
            "(1,1,2025,900,50000),(2,1,2026,950,60000),(3,2,2026,951,40000),(4,99,2026,0,999)"
        ))
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


def test_product_deleted_flag_is_inverted():
    """eStock ``Products.deleted`` audited 2026-07: '1' = live (53k selling
    products), '0' = removed. Mirroring it literally hid the whole catalogue
    from POS/inventory/prescriptions."""
    assert etl._product_deleted("1") is False   # live product
    assert etl._product_deleted("0") is True    # truly removed
    assert etl._product_deleted("Y") is True    # legacy Y/N convention
    assert etl._product_deleted("N") is False
    assert etl._product_deleted(None) is False


def test_mirror_products_with_real_world_deleted_values(estock_source):
    """deleted='1' products (the live catalogue) must arrive is_deleted=False."""
    try:
        with estock_source.begin() as c:
            c.execute(text(
                "INSERT INTO Products VALUES "
                "(103,'C','ليفتروزول','Letrozol','Letrozole','N','Y',90,60,0,'1','1'),"
                "(104,'D','منتج محذوف','Removed','','N','Y',5,3,0,'0','0')"
            ))
        with SessionLocal() as dst:
            etl.mirror(estock_source, dst, store_branch_map={1: 1, 2: 2})
        with SessionLocal() as s:
            live = s.query(m.Product).filter(m.Product.code == "C").one()
            assert live.is_deleted is False
            removed = s.query(m.Product).filter(m.Product.code == "D").one()
            assert removed.is_deleted is True
    finally:
        reset_and_seed()


def test_update_on_match_preserves_enriched_scientific_name(estock_source):
    """The branch-scoped sync refreshes matched products each cycle. A blank
    eStock scientific name must NOT wipe ProCare's Titan/Drug-Eye enrichment
    (docs/03 §4); a real eStock value still wins (owner cleanups propagate)."""
    try:
        with SessionLocal() as dst:
            etl.mirror(estock_source, dst, store_branch_map={1: 1, 2: 2})
        # Simulate the Titan backfill + an owner cleanup landing on eStock.
        with SessionLocal() as s:
            p = s.query(m.Product).filter(m.Product.code == "A").one()
            p.scientific_name = "PARACETAMOL+CAFFEINE"  # Titan enrichment
            s.commit()
        with estock_source.begin() as c:
            c.execute(text("UPDATE Products SET product_scientific_name = '' WHERE product_id = 101"))
            c.execute(text(
                "UPDATE Products SET product_scientific_name = 'AMOXICILLIN+CLAVULANATE' WHERE product_id = 102"
            ))
        with SessionLocal() as dst:
            etl.mirror(
                estock_source, dst, store_branch_map={1: 1, 2: 2},
                wipe=False, branch_scoped=True, dedup=True,
            )
        with SessionLocal() as s:
            enriched = s.query(m.Product).filter(m.Product.code == "A").one()
            assert enriched.scientific_name == "PARACETAMOL+CAFFEINE"  # kept
            cleaned = s.query(m.Product).filter(m.Product.code == "B").one()
            assert cleaned.scientific_name == "AMOXICILLIN+CLAVULANATE"  # refreshed
    finally:
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
            etl.mirror(estock_source, dst, store_branch_map={1: "ELSANTA", 2: "MASHALA"})
        with SessionLocal() as s:
            br = s.query(m.Branch).filter(m.Branch.code == "STORE3").one_or_none()
            assert br is not None  # auto-created
            stock = s.query(m.StockBatch).filter(m.StockBatch.branch_id == br.branch_id).all()
            assert len(stock) >= 1  # store-3 stock landed in the new branch
    finally:
        reset_and_seed()


def test_distinct_store_ids_discovery(estock_source):
    from sqlalchemy import inspect
    with estock_source.connect() as c:
        ids = etl._distinct_store_ids(inspect(estock_source), c)
    assert ids == {1, 2}  # what preflight reports so branches can be named


def test_run_full_load_refuses_without_credentials():
    # No estock_source credentials configured in the example config => safe refusal.
    result = etl.run_full_load()
    assert result["ran"] is False
    assert "credentials" in result["reason"].lower()


# Phase 7: High-value mirrors (Branches_Product_Amount, Cash_disk_close, Branch_order_*)


def test_load_branch_product_amount(estock_source):
    """Mirror Branches_Product_Amount (per-branch batch stock) alongside Product_Amount."""
    try:
        with estock_source.begin() as c:
            # Inferred schema: product_id, amount, buy_price, sell_price, tax_price, exp_date, store_id
            c.execute(text(
                "CREATE TABLE Branches_Product_Amount ("
                "counter_id INT, product_id INT, amount REAL, buy_price REAL, sell_price REAL, "
                "tax_price REAL, exp_date TEXT, store_id INT)"
            ))
            # Store 2 (MASHALA) branch stock
            c.execute(text(
                "INSERT INTO Branches_Product_Amount VALUES "
                "(201,101,50,7,12,0,'2027-06-01',2),"
                "(202,102,10,40,60,0,'2027-08-15',2)"
            ))
        with SessionLocal() as dst:
            etl.mirror(estock_source, dst, store_branch_map={1: 1, 2: 2})
        with SessionLocal() as s:
            # Check that branch stock was loaded alongside main stock
            mashala_stock = s.query(m.StockBatch).filter(m.StockBatch.branch_id == 2).all()
            assert len(mashala_stock) >= 2  # includes Branches_Product_Amount rows
            # Verify a batch from Branches_Product_Amount
            batch = next((b for b in mashala_stock if b.amount == 50), None)
            assert batch is not None
            prod_a = s.query(m.Product).filter(m.Product.code == "A").one()
            assert batch.product_id == prod_a.product_id
    finally:
        reset_and_seed()


def test_load_cash_shift_closes(estock_source):
    """Mirror Cash_disk_close (shift reconciliation history)."""
    try:
        with estock_source.begin() as c:
            c.execute(text(
                "CREATE TABLE Cash_disk_close ("
                "cdc_id INT, store_id INT, cdc_emp_id INT, cdc_shift_start_time TEXT, "
                "cdc_start_cash REAL, cdc_curr_cash REAL, cdc_act_cash REAL, "
                "cdc_trans_value REAL, cdc_notice TEXT)"
            ))
            c.execute(text(
                "INSERT INTO Cash_disk_close VALUES "
                "(1,1,1,'2026-07-24 08:00:00',0,5000,5050,0,'OK'),"
                "(2,1,1,'2026-07-24 16:00:00',5050,10200,10200,0,'Balanced')"
            ))
        with SessionLocal() as dst:
            etl.mirror(estock_source, dst, store_branch_map={1: 1, 2: 2})
        with SessionLocal() as s:
            shifts = s.query(m.CashShiftClose).filter(m.CashShiftClose.branch_id == 1).all()
            assert len(shifts) >= 2
            shift = shifts[0]
            assert shift.start_cash == 0
            assert shift.current_cash == 5000
            assert shift.actual_cash == 5050
    finally:
        reset_and_seed()


def test_load_branch_orders(estock_source):
    """Mirror Branch_order_header/details (inter-branch transfer history)."""
    try:
        with estock_source.begin() as c:
            c.execute(text(
                "CREATE TABLE Branch_order_header ("
                "bo_id INT, from_store_id INT, to_store_id INT, "
                "order_date TEXT, received_date TEXT, status TEXT, notice TEXT)"
            ))
            c.execute(text(
                "INSERT INTO Branch_order_header VALUES "
                "(1,1,2,'2026-07-20','2026-07-21','received','Transfer OK')"
            ))
            c.execute(text(
                "CREATE TABLE Branch_order_details ("
                "bol_id INT, bo_id INT, product_id INT, qty REAL, received_qty REAL, notice TEXT)"
            ))
            c.execute(text(
                "INSERT INTO Branch_order_details VALUES "
                "(1,1,101,20,20,NULL),"
                "(2,1,102,5,5,NULL)"
            ))
        with SessionLocal() as dst:
            etl.mirror(estock_source, dst, store_branch_map={1: 1, 2: 2})
        with SessionLocal() as s:
            orders = s.query(m.BranchOrderHeader).all()
            assert len(orders) == 1
            order = orders[0]
            assert order.from_branch_id == 1 and order.to_branch_id == 2
            assert order.status == "received"

            lines = s.query(m.BranchOrderLine).filter(m.BranchOrderLine.order_id == order.order_id).all()
            assert len(lines) == 2
            assert lines[0].quantity == 20
            assert lines[0].received_qty == 20
    finally:
        reset_and_seed()


def test_load_gl_accounts(estock_source):
    """Mirror Account_Tree (chart of accounts) verbatim, upserted by source id."""
    try:
        with estock_source.begin() as c:
            c.execute(text(
                "CREATE TABLE Account_Tree ("
                "account_id INT, account_code TEXT, account_name_ar TEXT, account_name_en TEXT, "
                "account_major INT, account_start_money REAL)"
            ))
            c.execute(text(
                "INSERT INTO Account_Tree VALUES "
                "(1,'1000','الأصول','Assets',NULL,0),"
                "(2,'1100','النقدية','Cash',1,5000)"
            ))
        with SessionLocal() as dst:
            etl.mirror(estock_source, dst, store_branch_map={1: 1, 2: 2})
        with SessionLocal() as s:
            accounts = s.query(m.GlAccount).order_by(m.GlAccount.source_id).all()
            assert len(accounts) == 2
            assets, cash = accounts
            assert assets.code == "1000" and assets.parent_source_id is None
            assert cash.code == "1100" and cash.parent_source_id == 1
            assert cash.start_money == 5000

        # Re-run to prove upsert-by-source-id doesn't duplicate.
        with SessionLocal() as dst:
            etl.mirror(estock_source, dst, store_branch_map={1: 1, 2: 2})
        with SessionLocal() as s:
            assert s.query(m.GlAccount).count() == 2
    finally:
        reset_and_seed()


def test_load_gl_journal(estock_source):
    """Mirror Gedo_Financial (central journal) verbatim, upserted by source id."""
    try:
        with estock_source.begin() as c:
            c.execute(text(
                "CREATE TABLE Gedo_Financial ("
                "gf_id INT, gf_code TEXT, gf_gedo_type TEXT, gf_value REAL, "
                "gf_from_type TEXT, gf_from_id INT, gf_to_type TEXT, gf_to_id INT, "
                "gf_notes TEXT, gf_computer TEXT, gf_actual_cashier TEXT, gf_form_type TEXT)"
            ))
            c.execute(text(
                "INSERT INTO Gedo_Financial VALUES "
                "(1,'GF-1','sale',500,'customer',10,'cash',1,'Invoice #1','PC1','admin','sale'),"
                "(2,'GF-2','purchase',-300,'cash',1,'vendor',20,'PO #1','PC1','admin','purchase')"
            ))
        with SessionLocal() as dst:
            etl.mirror(estock_source, dst, store_branch_map={1: 1, 2: 2})
        with SessionLocal() as s:
            entries = s.query(m.GlJournalEntry).order_by(m.GlJournalEntry.source_id).all()
            assert len(entries) == 2
            e1 = entries[0]
            assert e1.code == "GF-1" and e1.value == 500
            assert e1.from_type == "customer" and e1.from_id == 10
            assert e1.to_type == "cash" and e1.to_id == 1
            assert e1.notes == "Invoice #1"

        # Re-run: journal is append-only/immutable — must not duplicate existing source_ids.
        with SessionLocal() as dst:
            etl.mirror(estock_source, dst, store_branch_map={1: 1, 2: 2})
        with SessionLocal() as s:
            assert s.query(m.GlJournalEntry).count() == 2
    finally:
        reset_and_seed()
