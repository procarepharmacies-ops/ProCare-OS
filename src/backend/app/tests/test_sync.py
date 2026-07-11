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
        counts = res["counts"]["source"]  # run_once reports per-source counts
        # Every source product lands exactly once: created new, or matched an
        # existing catalogue row (and refreshed in place).
        assert counts["products"] + counts["products_updated"] == len(estock_seed.DRUGS)
        assert counts["customers"] + counts["customers_updated"] == len(estock_seed.CUSTOMERS)
        assert counts["sales"] > 0

        with SessionLocal() as s:
            # Branch-scoped sync: the shared catalogue keeps the demo products
            # AND gains every mirrored drug (different code series, no matches).
            assert s.scalar(select(func.count()).select_from(m.Product)) >= len(estock_seed.DRUGS)
            # Data-quality rules applied by the mirror: stock never negative.
            min_amount = s.scalar(select(func.min(m.StockBatch.amount)))
            assert float(min_amount) >= 0
            # Returns flagged separately from sales.
            assert s.scalar(select(func.count()).select_from(m.Sale).where(m.Sale.is_return == True)) >= 1  # noqa: E712

        # status() reflects the successful run.
        st = sync.status()
        assert st["last_status"] == "ok"
        assert st["runs"] >= 1

        # Re-running is stable: matched by code, nothing is created twice.
        res2 = sync.run_once(source_engine=estock_source)
        assert res2["ran"] is True
        assert res2["counts"]["source"]["products"] == 0
        with SessionLocal() as s:
            assert s.scalar(select(func.count()).select_from(m.Product)) >= len(estock_seed.DRUGS)
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


def test_two_sources_branch_scoped(tmp_path):
    """Two branch servers (Elsanta + Mashala) sync into ONE ProCare database.

    Each source refreshes only its own branch: repeated cycles never duplicate,
    never touch the other branch, share one deduped catalogue, and an appended
    historical branch survives every cycle — the multi-branch production shape.
    """
    from app.services import etl

    src_a = create_engine(f"sqlite:///{tmp_path / 'elsanta.db'}")
    src_b = create_engine(f"sqlite:///{tmp_path / 'mashala.db'}")
    estock_seed.seed_estock_source(src_a, days=15)
    estock_seed.seed_estock_source(src_b, days=15)
    map_a = {1: "ELSANTA", 2: "ELSANTA"}
    map_b = {1: "MASHALA", 2: "MASHALA"}

    def counts_by_branch(s):
        rows = s.execute(
            select(m.Branch.code, func.count(m.Sale.sale_id))
            .join(m.Sale, m.Sale.branch_id == m.Branch.branch_id)
            .group_by(m.Branch.code)
        ).all()
        return dict(rows)

    try:
        with SessionLocal() as s:
            # A historical branch that must survive live cycles untouched.
            hist_counts = etl.mirror(src_b, s, wipe=False, force_branch_code="HIST")
            s.commit()
            assert hist_counts["sales"] > 0
            hist_total = hist_counts["sales"] + hist_counts.get("returns", 0)

        for cycle in range(2):  # two full cycles: second must be a no-op growthwise
            with SessionLocal() as s:
                etl.mirror(src_a, s, map_a, branch_scoped=True)
                s.commit()
            with SessionLocal() as s:
                etl.mirror(src_b, s, map_b, branch_scoped=True)
                s.commit()

        with SessionLocal() as s:
            by_branch = counts_by_branch(s)
            assert by_branch.get("ELSANTA", 0) > 0
            assert by_branch.get("MASHALA", 0) > 0
            assert by_branch.get("HIST", 0) == hist_total  # history intact
            # Shared catalogue deduped: both sources carry the same drug codes.
            n_products = s.scalar(select(func.count()).select_from(m.Product))

        # A third cycle of source A: no duplication anywhere, B untouched.
        with SessionLocal() as s:
            before_b = counts_by_branch(s).get("MASHALA", 0)
        with SessionLocal() as s:
            c = etl.mirror(src_a, s, map_a, branch_scoped=True)
            s.commit()
            assert c["products"] == 0  # everything matched, nothing re-created
        with SessionLocal() as s:
            assert counts_by_branch(s).get("MASHALA", 0) == before_b
            assert s.scalar(select(func.count()).select_from(m.Product)) == n_products
    finally:
        src_a.dispose()
        src_b.dispose()
        reset_and_seed()
