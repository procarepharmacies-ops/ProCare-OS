"""Multi-branch consolidation import.

Proves two separate branch databases (Elsanta, Mashala) can be loaded into ONE
ProCare database — appended, each mapped to its own branch, sharing a single
deduped drug catalogue instead of duplicating it. This is the path for folding
the pre-merge D:\\old backups into the new SQL Server Express. Runs on SQLite
here; the identical code runs against the restored SQL Server backups.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select

from app.db import estock_seed, models as m
from app.db.base import SessionLocal
from app.db.seed import reset_and_seed
from app.services import etl


@pytest.fixture
def two_branch_sources(tmp_path):
    e1 = create_engine(f"sqlite:///{tmp_path / 'elsanta.db'}")
    e2 = create_engine(f"sqlite:///{tmp_path / 'mashala.db'}")
    estock_seed.seed_estock_source(e1, days=15)
    estock_seed.seed_estock_source(e2, days=15)
    yield e1, e2
    e1.dispose()
    e2.dispose()


def test_append_two_branches_shares_one_catalogue(two_branch_sources):
    try:
        e1, e2 = two_branch_sources
        # Import Elsanta fresh, then append Mashala.
        with SessionLocal() as dst:
            c1 = etl.mirror(e1, dst, wipe=True, force_branch_code="ELSANTA")
        with SessionLocal() as dst:
            c2 = etl.mirror(e2, dst, wipe=False, force_branch_code="MASHALA")

        with SessionLocal() as s:
            codes = set(s.scalars(select(m.Branch.code)).all())
            assert {"ELSANTA", "MASHALA"} <= codes

            eb = s.scalar(select(m.Branch.branch_id).where(m.Branch.code == "ELSANTA"))
            mb = s.scalar(select(m.Branch.branch_id).where(m.Branch.code == "MASHALA"))

            # Catalogue deduped by product code — not doubled across branches.
            assert s.scalar(select(func.count()).select_from(m.Product)) == len(estock_seed.DRUGS)
            assert c1["products"] == len(estock_seed.DRUGS)
            assert c2["products"] == 0  # append added no duplicate products

            # Each branch's sales landed under its own branch_id.
            e_sales = s.scalar(select(func.count()).select_from(m.Sale).where(m.Sale.branch_id == eb))
            m_sales = s.scalar(select(func.count()).select_from(m.Sale).where(m.Sale.branch_id == mb))
            total = s.scalar(select(func.count()).select_from(m.Sale))
            assert e_sales > 0 and m_sales > 0
            assert total == e_sales + m_sales  # every sale belongs to exactly one branch

            # Stock exists for both branches too.
            assert s.scalar(select(func.count()).select_from(m.StockBatch).where(m.StockBatch.branch_id == eb)) > 0
            assert s.scalar(select(func.count()).select_from(m.StockBatch).where(m.StockBatch.branch_id == mb)) > 0
    finally:
        reset_and_seed()


def test_default_mirror_still_full_refresh(two_branch_sources):
    """The default (no flags) mirror is unchanged: a single-source full refresh."""
    try:
        e1, _ = two_branch_sources
        with SessionLocal() as dst:
            etl.mirror(e1, dst)  # defaults: wipe=True, no forced branch, no dedup
        with SessionLocal() as dst:
            c = etl.mirror(e1, dst)  # a second full refresh replaces, not doubles
        with SessionLocal() as s:
            assert s.scalar(select(func.count()).select_from(m.Product)) == len(estock_seed.DRUGS)
            assert c["products"] == len(estock_seed.DRUGS)
    finally:
        reset_and_seed()
