"""Wipe paths must survive rows that reference what they delete.

Both wipes clear parents (sales, products, customers) while other tables still
point at them. Every one of these FK relationships was live in main and only
stayed hidden because the tables were empty in test order — on a real till they
never are. A single missed reference fails the parent DELETE with "FOREIGN KEY
constraint failed", and because sync.py soft-fails per source the mirror then
dies on EVERY cycle while /api/health still reports ok.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select

from app.db import estock_seed, models as m
from app.db.base import SessionLocal
from app.db.seed import reset_and_seed
from app.services import etl


@pytest.fixture
def source(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    estock_seed.seed_estock_source(eng, days=10)
    yield eng
    eng.dispose()


def _first(s, model):
    return s.scalars(select(model)).first()


def test_branch_wipe_survives_incentive_rows(source):
    """pos.py writes an IncentiveLedger row per sale, with NOT NULL FKs to the
    sale AND its line — so a branch wipe must clear them before the sale."""
    try:
        etl_map = {"1": "ELSANTA"}
        with SessionLocal() as dst:
            etl.mirror(source, dst, etl_map, branch_scoped=True)
            dst.commit()

        with SessionLocal() as s:
            # MUST be a sale in the MIRRORED branch. The seeded demo data lives
            # in other branches that this wipe never touches, so attaching the
            # incentive to an arbitrary "first" line silently tests nothing.
            elsanta = s.scalars(select(m.Branch).where(m.Branch.code == "ELSANTA")).one()
            sale = s.scalars(
                select(m.Sale).where(m.Sale.branch_id == elsanta.branch_id)
            ).first()
            assert sale is not None, "mirror must load sales into the mapped branch"
            line = s.scalars(
                select(m.SaleLine).where(m.SaleLine.sale_id == sale.sale_id)
            ).first()
            assert line is not None
            s.add(m.IncentiveLedger(
                employee_id=_first(s, m.Employee).employee_id,
                sale_id=sale.sale_id,
                sale_line_id=line.line_id,
                product_id=line.product_id,
                branch_id=sale.branch_id,
                points=1.0,
            ))
            s.commit()
            assert s.scalar(select(func.count()).select_from(m.IncentiveLedger)) == 1

        # The next cycle re-wipes this branch. Before the fix: IntegrityError.
        with SessionLocal() as dst:
            etl.mirror(source, dst, etl_map, branch_scoped=True)
            dst.commit()

        with SessionLocal() as s:
            assert s.scalar(select(func.count()).select_from(m.Sale)) > 0
    finally:
        reset_and_seed()


def test_full_wipe_detaches_rather_than_destroying_local_rows(source):
    """A full wipe clears customers, but a parked cart and a captured
    prescription are local ProCare data the mirror must not delete. Their
    nullable customer_id is detached instead, so the rows survive."""
    try:
        with SessionLocal() as dst:
            etl.mirror(source, dst, {"1": "ELSANTA"}, branch_scoped=False)
            dst.commit()

        with SessionLocal() as s:
            cust = _first(s, m.Customer)
            assert cust is not None
            s.add(m.HeldInvoice(
                branch_id=_first(s, m.Branch).branch_id,
                customer_id=cust.customer_id,
                cart_json="{}",
            ))
            s.commit()
            held_before = s.scalar(select(func.count()).select_from(m.HeldInvoice))
            assert held_before == 1

        # Full wipe + reload. Before the fix: IntegrityError on DELETE customers.
        with SessionLocal() as dst:
            etl.mirror(source, dst, {"1": "ELSANTA"}, branch_scoped=False)
            dst.commit()

        with SessionLocal() as s:
            # The cart SURVIVED (not deleted), just detached from the old customer.
            assert s.scalar(select(func.count()).select_from(m.HeldInvoice)) == held_before
            assert _first(s, m.HeldInvoice).customer_id is None
    finally:
        reset_and_seed()


def test_incremental_window_wipe_survives_incentive_rows(source):
    """The steady-state production path: once a branch is filled, every cycle
    re-pulls only a trailing window. Today's till sales are always inside it,
    and each carries an IncentiveLedger row, so this FK fires first and most
    often — every 300s, soft-failed and therefore silent."""
    try:
        etl_map = {"1": "ELSANTA"}
        with SessionLocal() as dst:
            etl.mirror(source, dst, etl_map, branch_scoped=True)
            dst.commit()

        with SessionLocal() as s:
            elsanta = s.scalars(select(m.Branch).where(m.Branch.code == "ELSANTA")).one()
            sale = s.scalars(
                select(m.Sale)
                .where(m.Sale.branch_id == elsanta.branch_id)
                .order_by(m.Sale.sale_date.desc())
            ).first()
            assert sale is not None
            line = s.scalars(
                select(m.SaleLine).where(m.SaleLine.sale_id == sale.sale_id)
            ).first()
            assert line is not None
            s.add(m.IncentiveLedger(
                employee_id=_first(s, m.Employee).employee_id,
                sale_id=sale.sale_id,
                sale_line_id=line.line_id,
                product_id=line.product_id,
                branch_id=sale.branch_id,
                points=1.0,
            ))
            s.commit()

        # Incremental cycle with a window wide enough to cover that sale.
        with SessionLocal() as dst:
            etl.mirror(source, dst, etl_map, branch_scoped=True, incremental_days=3650)
            dst.commit()

        with SessionLocal() as s:
            assert s.scalar(select(func.count()).select_from(m.Sale)) > 0
    finally:
        reset_and_seed()
