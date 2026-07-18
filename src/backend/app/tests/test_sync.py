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


def test_comm_error_classification():
    """Only dropped-connection errors are retryable; data errors never are."""
    from app.services import etl

    assert etl._is_comm_error(Exception(
        "('08S01', '[08S01] Communication link failure: TCP Provider: An existing "
        "connection was forcibly closed by the remote host. (10054)')"
    ))
    assert etl._is_comm_error(Exception("connection reset by peer"))
    assert not etl._is_comm_error(Exception("FOREIGN KEY constraint failed"))
    assert not etl._is_comm_error(Exception("CHECK constraint CK_products_prices violated"))


def test_sync_survives_flaky_wan(estock_source, monkeypatch):
    """The Elsanta failure mode: the WAN drops the connection (10054) mid-pull
    of the big sales tables. The chunked loader must retry the failed chunk on
    a fresh connection and complete the mirror with NO rows lost or duplicated.
    """
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    from app.services import etl

    monkeypatch.setattr(etl, "_CHUNK_ROWS", 5)  # force many chunk queries
    monkeypatch.setattr(etl, "_RETRY_BACKOFF_SECONDS", 0.0)
    # Both runs must be FULL loads so their counts are comparable 1:1.
    monkeypatch.setenv("SYNC_INCREMENTAL_DAYS", "0")

    flakes = {"n": 0}

    @event.listens_for(estock_source, "before_cursor_execute")
    def _drop_link(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        # Drop the first two Sales_details chunk fetches — exercising the full
        # retry budget (attempt 3 of 3 succeeds) with Elsanta's exact signature.
        if "Sales_details" in statement and "BETWEEN" in statement and flakes["n"] < 2:
            flakes["n"] += 1
            raise OperationalError(
                statement, parameters,
                Exception(
                    "('08S01', '[08S01] Communication link failure: TCP Provider: "
                    "An existing connection was forcibly closed by the remote host. (10054)')"
                ),
            )

    try:
        res = sync.run_once(source_engine=estock_source)
        assert flakes["n"] == 2  # the drops really happened...
        assert res["ran"] is True  # ...and were fully recovered
        assert "errors" not in res
        flaky_counts = res["counts"]["source"]
        assert flaky_counts["sales_lines"] > 0

        # Control cycle with a healthy link: branch-scoped sync wipes and
        # reloads this branch, so identical counts == nothing was lost or
        # inserted twice during the retried chunks.
        event.remove(estock_source, "before_cursor_execute", _drop_link)
        clean_counts = sync.run_once(source_engine=estock_source)["counts"]["source"]
        for key in ("sales", "sales_lines", "returns", "returns_lines", "purchases"):
            assert flaky_counts.get(key) == clean_counts.get(key), key
    finally:
        if event.contains(estock_source, "before_cursor_execute", _drop_link):
            event.remove(estock_source, "before_cursor_execute", _drop_link)
        reset_and_seed()


def test_sync_soft_fails_when_source_keeps_dropping(estock_source, monkeypatch):
    """A source whose WAN never recovers must exhaust its retries and be
    reported as a per-source error — never a crash, never a hung pharmacy."""
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    from app.services import etl

    monkeypatch.setattr(etl, "_RETRY_BACKOFF_SECONDS", 0.0)

    @event.listens_for(estock_source, "before_cursor_execute")
    def _always_drop(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        if "Sales_header" in statement:
            raise OperationalError(
                statement, parameters,
                Exception("Communication link failure (10054)"),
            )

    try:
        res = sync.run_once(source_engine=estock_source)
        assert res["ran"] is False
        assert "source" in res["errors"]
        assert "10054" in res["errors"]["source"]
        assert sync.status()["last_status"] == "error"
    finally:
        event.remove(estock_source, "before_cursor_execute", _always_drop)
        reset_and_seed()


def test_incremental_sync_window(estock_source, monkeypatch):
    """After the initial full load, a cycle re-pulls only the trailing window:
    a fresh source sale still lands, all older history survives untouched, and
    nothing is duplicated. This is the fast path for the flaky Elsanta WAN."""
    monkeypatch.setenv("SYNC_INCREMENTAL_DAYS", "7")
    try:
        res1 = sync.run_once(source_engine=estock_source)
        assert res1["counts"]["source"]["sync_mode"] == "branch_full"  # first fill
        with SessionLocal() as s:
            before_total = s.scalar(select(func.count()).select_from(m.Sale))
            before_lines = s.scalar(select(func.count()).select_from(m.SaleLine))

        estock_seed.add_live_sale(estock_source)
        res2 = sync.run_once(source_engine=estock_source)
        c2 = res2["counts"]["source"]
        assert c2["sync_mode"] == "incremental(7d)"
        # Only the window crossed the wire — far fewer rows than the full load.
        assert c2["sales"] < res1["counts"]["source"]["sales"]

        with SessionLocal() as s:
            assert s.scalar(select(func.count()).select_from(m.Sale)) == before_total + 1
            assert s.scalar(select(func.count()).select_from(m.SaleLine)) == before_lines + 1

        # A third cycle with no source activity is a no-op growthwise.
        sync.run_once(source_engine=estock_source)
        with SessionLocal() as s:
            assert s.scalar(select(func.count()).select_from(m.Sale)) == before_total + 1
    finally:
        reset_and_seed()


def test_treasury_snapshot_not_double_counted(estock_source):
    """Cash_depots is a balance SNAPSHOT — repeated branch-scoped cycles must
    replace it, never stack copies (the treasury total crept up every cycle)."""
    from sqlalchemy import text as sql_text

    with estock_source.begin() as c:
        c.execute(sql_text(
            "CREATE TABLE Cash_depots (cash_depot_id INTEGER PRIMARY KEY, "
            "cash_depot_name_ar TEXT, cash_depot_current_money REAL, bank_id INTEGER)"
        ))
        c.execute(sql_text(
            "INSERT INTO Cash_depots VALUES (1, 'الخزنة الرئيسية', 5000, NULL), "
            "(2, 'حساب البنك', 12000, 1)"
        ))

    def depot_totals():
        with SessionLocal() as s:
            n = s.scalar(select(func.count()).select_from(m.LedgerEntry)
                         .where(m.LedgerEntry.ref_type == "depot"))
            total = s.scalar(
                select(func.coalesce(func.sum(m.LedgerEntry.debit - m.LedgerEntry.credit), 0))
                .where(m.LedgerEntry.ref_type == "depot")
            )
            return n, float(total)

    try:
        sync.run_once(source_engine=estock_source)
        n1, total1 = depot_totals()
        assert n1 == 2 and total1 == 17000.0

        sync.run_once(source_engine=estock_source)
        sync.run_once(source_engine=estock_source)
        n3, total3 = depot_totals()
        assert (n3, total3) == (n1, total1)  # replaced, not stacked
    finally:
        reset_and_seed()


def test_sync_mirrors_employees_with_permissions(estock_source):
    """eStock Employee master → ProCare employees: permission flags map 1:1,
    plaintext eStock passwords are NEVER imported (unusable sentinel instead),
    and a matched ProCare employee keeps their password/role untouched."""
    from sqlalchemy import text as sql_text

    from app.services.auth import verify_password

    with SessionLocal() as s:
        anchor = s.query(m.Employee).filter(m.Employee.username.is_not(None)).first()
        anchor_username = anchor.username
        anchor_hash = anchor.password_hash
        anchor_role = anchor.role

    with estock_source.begin() as c:
        c.execute(sql_text(
            "CREATE TABLE Employee (emp_id INTEGER PRIMARY KEY, emp_name_ar TEXT, "
            "emp_name_en TEXT, username TEXT, pass TEXT, mobile TEXT, basic_salary REAL, "
            "max_disc_per REAL, emp_edit_sell_price TEXT, allaw_sale_credit TEXT, "
            "allaw_r_sale TEXT, allaw_un_sale TEXT, emp_change_cash_disk TEXT, "
            "emp_show_money TEXT, active TEXT, deleted TEXT)"
        ))
        c.execute(sql_text(
            "INSERT INTO Employee VALUES "
            "(1, 'فاطمة', 'Fatma', 'fatma.estock', 'plaintext123', '0100000000', 4500, "
            " 10, 'Y', 'Y', 'N', 'N', 'Y', 'N', '1', '0'), "
            f"(2, 'مدير النظام', 'Sysadmin', '{anchor_username}', 'plaintext456', NULL, 0, "
            " 5, 'N', 'N', 'N', 'N', 'N', 'N', '1', '0'), "
            "(3, 'بدون حساب', NULL, NULL, NULL, NULL, 0, "
            " 0, 'N', 'N', 'N', 'N', 'N', 'N', '1', '0')"
        ))

    try:
        res = sync.run_once(source_engine=estock_source)
        counts = res["counts"]["source"]
        assert counts["employees"] == 1  # fatma created; anchor matched; row 3 skipped
        assert counts["employees_updated"] >= 1

        with SessionLocal() as s:
            fatma = s.query(m.Employee).filter(m.Employee.username == "fatma.estock").one()
            assert fatma.role == "assistant"  # most restrictive tier by default
            assert fatma.max_disc_per == 10
            assert fatma.can_edit_sell_price is True
            assert fatma.can_sale_credit is True
            assert fatma.can_return is False
            assert fatma.can_change_shift is True
            # The eStock plaintext password must NOT work (or be stored).
            assert not verify_password("plaintext123", fatma.password_hash)
            assert "plaintext123" not in fatma.password_hash

            anchor2 = s.query(m.Employee).filter(m.Employee.username == anchor_username).one()
            assert anchor2.password_hash == anchor_hash  # login untouched
            assert anchor2.role == anchor_role
            assert anchor2.max_disc_per == 5  # ...but flags refreshed from source

        # Idempotent: second cycle matches everyone, creates no one.
        res2 = sync.run_once(source_engine=estock_source)
        assert res2["counts"]["source"]["employees"] == 0
    finally:
        reset_and_seed()


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
