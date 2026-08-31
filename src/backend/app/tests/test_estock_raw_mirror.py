"""100% eStock coverage: the generic raw mirror.

28 eStock tables have dedicated loaders in ``app.services.etl``; the other 86 on
the live Elsanta database are dumped verbatim into ``estock_raw_mirror`` so
ProCare holds every source table. These tests pin the parts of that pass that
are easy to get quietly wrong:

  * a COMPOSITE primary key must key on the whole key. Keying on its first
    column alone collapsed Branches_Product_amount_Change's 1.05M rows onto the
    two distinct branch_id values;
  * a table with NO declared key (Product_amount_Change, 533K rows on Elsanta)
    must still dedup, by row digest;
  * re-running a sync must never double-insert -- the pharmacy syncs every five
    minutes, so a non-idempotent mirror doubles the database daily;
  * a table eStock EDITS in place must come back verbatim, not append-only.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from app.db import models as m
from app.db.base import SessionLocal
from app.db.seed import reset_and_seed
from app.services import etl
from app.tests.test_etl import _build_estock_source


def _build_source(path):
    """The eStock-shaped SQLite source the mirror tests already use, plus one
    uncovered table in each of the shapes the real database actually has."""
    eng = _build_estock_source(path)
    with eng.begin() as c:
        # Composite PK, like Branches_Product_amount_Change (branch_id, id) and
        # Branches_shortcoming (branch_id, product_id, store_id) on Elsanta.
        c.execute(text(
            "CREATE TABLE Branches_shortcoming (branch_id INT, product_id INT, store_id INT, "
            "amount REAL, PRIMARY KEY (branch_id, product_id, store_id))"
        ))
        c.execute(text(
            "INSERT INTO Branches_shortcoming VALUES (1,101,1,5),(1,102,1,7),(1,103,2,9)"
        ))

        # No declared key at all, like Product_amount_Change (533K rows).
        c.execute(text("CREATE TABLE Flag (flag_code TEXT, flag_name TEXT)"))
        c.execute(text("INSERT INTO Flag VALUES ('A','نقدي'),('B','آجل')"))

        # Single integer PK -- the watermark shape.
        c.execute(text(
            "CREATE TABLE Gedo_customers (gc_id INTEGER PRIMARY KEY, customer_id INT, total REAL)"
        ))
        c.execute(text("INSERT INTO Gedo_customers VALUES (1,5,100.0),(2,6,250.0)"))

        # Empty source table -- still counts as covered.
        c.execute(text("CREATE TABLE Checks (check_id INTEGER PRIMARY KEY, money REAL)"))
    return eng


@pytest.fixture
def source(tmp_path):
    eng = _build_source(tmp_path / "estock_raw.db")
    yield eng
    eng.dispose()


def _raw_rows(session, table: str) -> list[tuple]:
    return session.execute(
        text(
            "SELECT source_id, raw, branch_id FROM estock_raw_mirror "
            "WHERE source_table = :t ORDER BY source_id"
        ),
        {"t": table},
    ).all()


def _counts(source_engine) -> dict:
    with SessionLocal() as dst:
        return etl.mirror(source_engine, dst, store_branch_map={1: 1, 2: 2})


def test_every_uncovered_table_is_mirrored_and_covered_ones_are_not(source):
    try:
        counts = _counts(source)

        # Dedicated loaders + raw mirror together account for EVERY source
        # table -- that is what "100% of eStock" means operationally.
        assert (
            counts["raw_tables_dedicated"] + counts["raw_tables_mirrored"]
            == counts["raw_tables_total"]
        )
        assert counts["raw_tables_mirrored"] == 4         # the four added above
        assert counts["raw_coverage_pct"] == 100.0
        assert counts["raw_failed"] == []
        assert counts["raw_ok"] is True

        with SessionLocal() as s:
            mirrored = {
                r[0]
                for r in s.execute(
                    text("SELECT DISTINCT source_table FROM estock_raw_mirror")
                ).all()
            }
            # Tables with a dedicated loader must not be mirrored twice.
            assert not ({t.lower() for t in mirrored}
                        & {t.lower() for t in etl.COVERED_SOURCE_TABLES})
            assert {"Branches_shortcoming", "Flag", "Gedo_customers"} <= mirrored
    finally:
        reset_and_seed()


def test_composite_primary_key_keys_on_the_whole_key(source):
    """The bug this pins: keying on the FIRST pk column only. All three rows
    share branch_id=1 on two of them, so a first-column key would store 2 rows
    (or 1) instead of 3."""
    try:
        _counts(source)
        with SessionLocal() as s:
            rows = _raw_rows(s, "Branches_shortcoming")
            assert len(rows) == 3
            assert len({r[0] for r in rows}) == 3
            # store_id 2 maps to branch 2, store_id 1 to branch 1.
            assert sorted(r[2] for r in rows) == [1, 1, 2]
    finally:
        reset_and_seed()


def test_keyless_table_is_mirrored_and_deduped_by_row_digest(source):
    try:
        _counts(source)
        with SessionLocal() as s:
            rows = _raw_rows(s, "Flag")
            assert len(rows) == 2
            # No store_id column -> source-wide row, no branch attribution.
            assert {r[2] for r in rows} == {None}
            assert "نقدي" in "".join(r[1] for r in rows)
    finally:
        reset_and_seed()


def test_resync_does_not_duplicate(source):
    """The pharmacy syncs every five minutes. A mirror that appends blindly
    doubles the table on each cycle."""
    try:
        _counts(source)
        with SessionLocal() as s:
            first = s.execute(text("SELECT COUNT(*) FROM estock_raw_mirror")).scalar()

        second_counts = _counts(source)
        with SessionLocal() as s:
            second = s.execute(text("SELECT COUNT(*) FROM estock_raw_mirror")).scalar()

        assert first == second
        assert second_counts["raw_coverage_pct"] == 100.0
    finally:
        reset_and_seed()


def test_edited_source_row_is_refreshed_not_appended(source):
    """Small tables are the ones eStock edits in place (balances, config), so
    they are refreshed wholesale rather than appended to."""
    try:
        _counts(source)
        with source.begin() as c:
            c.execute(text("UPDATE Gedo_customers SET total = 999.0 WHERE gc_id = 1"))
        _counts(source)

        with SessionLocal() as s:
            rows = _raw_rows(s, "Gedo_customers")
            assert len(rows) == 2                       # not 3, not 4
            assert "999" in "".join(r[1] for r in rows)
            assert "100.0" not in "".join(r[1] for r in rows)
    finally:
        reset_and_seed()


def test_empty_source_table_counts_as_covered(source):
    try:
        counts = _counts(source)
        assert counts["raw_tables_mirrored"] == 4       # Checks included
        with SessionLocal() as s:
            assert _raw_rows(s, "Checks") == []
    finally:
        reset_and_seed()


def test_watermark_path_reads_rows_with_negative_keys(source, monkeypatch):
    """eStock issues negative ids -- Branches_shortcoming.product_id reaches
    -21670 on Elsanta. An incremental read anchored at 0 skips every row beneath
    it and reports success, so the first fill must start below the smallest key."""
    try:
        with source.begin() as c:
            c.execute(text("INSERT INTO Gedo_customers VALUES (-5, 9, 1.0)"))
            c.execute(text("INSERT INTO Gedo_customers VALUES (-1, 9, 2.0)"))
        monkeypatch.setenv("RAW_MIRROR_REFRESH_MAX_ROWS", "1")   # force incremental
        _counts(source)

        with SessionLocal() as s:
            ids = {r[0] for r in _raw_rows(s, "Gedo_customers")}
            assert {"-5", "-1", "1", "2"} <= ids
    finally:
        reset_and_seed()


def test_row_at_the_highest_key_is_not_skipped(source, monkeypatch):
    """Branches_convert_details holds 62K rows spread over 7.3M ids, so the read
    window is sized by key density. Whenever the span divides exactly by that
    width the last window ends ON the maximum key rather than past it -- and the
    watermark still advances, so the newest row would never be read again."""
    try:
        with source.begin() as c:
            c.execute(text("INSERT INTO Gedo_customers VALUES (5000000, 9, 3.0)"))
        monkeypatch.setenv("RAW_MIRROR_REFRESH_MAX_ROWS", "1")   # force incremental
        _counts(source)

        with SessionLocal() as s:
            ids = {r[0] for r in _raw_rows(s, "Gedo_customers")}
            assert "5000000" in ids          # the row at MAX(key) arrives
            assert {"1", "2"} <= ids         # and the dense ones still do too
    finally:
        reset_and_seed()


def test_watermark_path_pulls_only_new_rows(source, monkeypatch):
    """Force every table over the refresh threshold so the incremental branch
    runs, then prove a later row arrives exactly once."""
    try:
        monkeypatch.setenv("RAW_MIRROR_REFRESH_MAX_ROWS", "1")
        _counts(source)
        with SessionLocal() as s:
            assert len(_raw_rows(s, "Gedo_customers")) == 2
            wm = s.execute(
                text("SELECT last_value FROM estock_raw_watermark WHERE source_table = :t"),
                {"t": "Gedo_customers"},
            ).scalar()
            assert int(wm) == 2

        with source.begin() as c:
            c.execute(text("INSERT INTO Gedo_customers VALUES (3,7,42.0)"))
        _counts(source)

        with SessionLocal() as s:
            rows = _raw_rows(s, "Gedo_customers")
            assert len(rows) == 3                       # the new row, and only once
            assert int(
                s.execute(
                    text("SELECT last_value FROM estock_raw_watermark WHERE source_table = :t"),
                    {"t": "Gedo_customers"},
                ).scalar()
            ) == 3
    finally:
        reset_and_seed()


def test_raw_mirror_can_be_switched_off(source, monkeypatch):
    """A pharmacy sharing SQL Server Express with live POS defers the ~1 GB
    first fill to off-peak, exactly as SYNC_ENABLED defers the sync itself."""
    try:
        monkeypatch.setenv("RAW_MIRROR", "0")
        counts = _counts(source)
        assert counts["raw_enabled"] is False
        assert "raw_tables_total" not in counts
        with SessionLocal() as s:
            assert s.execute(text("SELECT COUNT(*) FROM estock_raw_mirror")).scalar() == 0
    finally:
        reset_and_seed()


def test_source_is_never_written(source):
    """GUARDRAIL: ProCare only ever SELECTs eStock."""
    try:
        with source.connect() as c:
            before = {
                t: c.execute(text(f"SELECT COUNT(*) FROM [{t}]")).scalar()
                for t in ("Products", "Customer", "Branches_shortcoming", "Flag",
                          "Gedo_customers", "Checks")
            }
        _counts(source)
        with source.connect() as c:
            after = {
                t: c.execute(text(f"SELECT COUNT(*) FROM [{t}]")).scalar()
                for t in before
            }
        assert before == after
    finally:
        reset_and_seed()


def test_one_unreadable_table_does_not_take_down_the_pass(source, monkeypatch):
    """Fail-soft is on a SAVEPOINT. The raw pass runs inside the mirror's single
    transaction, next to everything the dedicated loaders just wrote, so a bare
    try/except would leave the session needing a rollback and one bad table
    would lose the whole sync."""
    real = etl._mirror_one_raw_table

    def boom(insp, src, dst, tbl, *args, **kwargs):
        if tbl == "Flag":
            # Touch the session first, so the failure has uncommitted work of
            # its own to unwind -- a raise before any write proves nothing.
            dst.execute(
                text(
                    "INSERT INTO estock_raw_mirror "
                    "(source_table, source_id, raw, created_at) "
                    "VALUES ('Flag', 'poison', '{}', CURRENT_TIMESTAMP)"
                )
            )
            raise RuntimeError("source table unreadable")
        return real(insp, src, dst, tbl, *args, **kwargs)

    monkeypatch.setattr(etl, "_mirror_one_raw_table", boom)
    try:
        counts = _counts(source)

        assert counts["raw_failed"] == ["Flag: RuntimeError"]
        assert counts["raw_ok"] is False
        assert counts["raw_tables_mirrored"] == 3        # the other three still ran
        assert counts["raw_coverage_pct"] < 100.0        # and coverage says so

        with SessionLocal() as s:
            # The failed table left nothing behind...
            assert _raw_rows(s, "Flag") == []
            # ...while its neighbours committed, dedicated loaders included.
            assert len(_raw_rows(s, "Gedo_customers")) == 2
            assert s.query(m.Product).count() > 0
    finally:
        reset_and_seed()


def test_dedup_key_is_stable_for_decimal_ids():
    """eStock ids are DECIMAL(18,0). Rendering one run as '123' and the next as
    '1.23E+2' would make every cycle look like a brand-new row."""
    from decimal import Decimal

    a = etl._raw_key({"id": Decimal("123"), "branch_id": Decimal("1")}, ["branch_id", "id"])
    b = etl._raw_key({"id": 123, "branch_id": 1}, ["branch_id", "id"])
    assert a == b == "1|123"


def test_overlong_composite_key_is_hashed_to_fit_the_column():
    key = etl._raw_key({"a": "x" * 80, "b": "y" * 80}, ["a", "b"])
    assert len(key) == 40 and key.isalnum()


def test_raw_mirror_enabled_env_parsing(monkeypatch):
    for value, expected in (("1", True), ("true", True), ("ON", True),
                            ("0", False), ("false", False), ("no", False)):
        monkeypatch.setenv("RAW_MIRROR", value)
        assert etl._raw_mirror_enabled() is expected
    monkeypatch.delenv("RAW_MIRROR", raising=False)
    assert etl._raw_mirror_enabled() is True         # default: on

    monkeypatch.setenv("RAW_MIRROR_REFRESH_MAX_ROWS", "not-a-number")
    assert etl._raw_refresh_max_rows() == 50_000     # fail-soft to the default


def test_os_env_default_does_not_leak_between_tests():
    assert os.environ.get("RAW_MIRROR") in (None, "1")
