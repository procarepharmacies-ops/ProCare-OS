"""End-to-end sync tests.

Seeds an eStock-shaped SQLite source with the realistic generator, runs one sync
cycle, and asserts ProCare's own DB is populated and cleaned. Then appends a new
sale to the source and re-syncs to prove the mirror reflects live activity — the
core of "keeps in sync". Proves the whole pipeline on SQLite; the identical code
runs against SQL Server / the real eStock on a host that can reach it.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select

from app.db import estock_seed, models as m
from app.db.base import SessionLocal
from app.db.seed import reset_and_seed
from app.services import sync


@pytest.fixture
def estock_source(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'estock_src.db'}")
    estock_seed.seed_estock_source(eng, days=20)
    yield eng
    eng.dispose()


def test_sync_mirrors_source_into_procare(estock_source):
    try:
        res = sync.run_once(source_engine=estock_source)
        assert res["ran"] is True
        counts = res["counts"]
        assert counts["products"] == len(estock_seed.DRUGS)
        assert counts["customers"] == len(estock_seed.CUSTOMERS)
        assert counts["sales"] > 0

        with SessionLocal() as s:
            assert s.scalar(select(func.count()).select_from(m.Product)) == len(estock_seed.DRUGS)
            # Data-quality rules applied by the mirror: stock never negative.
            min_amount = s.scalar(select(func.min(m.StockBatch.amount)))
            assert float(min_amount) >= 0
            # Returns flagged separately from sales.
            assert s.scalar(select(func.count()).select_from(m.Sale).where(m.Sale.is_return == True)) >= 1  # noqa: E712

        # status() reflects the successful run.
        st = sync.status()
        assert st["last_status"] == "ok"
        assert st["runs"] >= 1
    finally:
        reset_and_seed()


def test_sync_reflects_new_source_activity(estock_source):
    """A new counter sale on eStock shows up in ProCare after the next cycle."""
    try:
        sync.run_once(source_engine=estock_source)
        with SessionLocal() as s:
            before = s.scalar(select(func.count()).select_from(m.Sale))

        estock_seed.add_live_sale(estock_source)  # simulate a live sale
        sync.run_once(source_engine=estock_source)
        with SessionLocal() as s:
            after = s.scalar(select(func.count()).select_from(m.Sale))

        assert after == before + 1
    finally:
        reset_and_seed()


def test_sync_idle_without_source():
    # No configured eStock source in the example config => safe idle, no crash.
    res = sync.run_once()
    assert res["ran"] is False
    assert sync.is_enabled() is False
