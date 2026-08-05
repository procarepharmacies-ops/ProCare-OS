"""Phase 6 tests: shareholders / owners mirror + register (company_Owner)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, delete, text

from app.db import models as m
from app.db.base import SessionLocal
from app.services import etl
from app.services import shareholders as svc


@pytest.fixture(autouse=True)
def clean_shareholders():
    s = SessionLocal()
    try:
        s.execute(delete(m.DividendPayment))
        s.execute(delete(m.Shareholder))
        s.commit()
    finally:
        s.close()
    yield


def _seed(session):
    a = m.Shareholder(source_id=1, code="O1", name_ar="أحمد", current_capital=600000, start_capital=500000)
    b = m.Shareholder(source_id=2, code="O2", name_ar="سارة", current_capital=400000, start_capital=400000)
    session.add_all([a, b])
    session.flush()
    session.add_all([
        m.DividendPayment(shareholder_id=a.shareholder_id, year=2025, amount=50000),
        m.DividendPayment(shareholder_id=a.shareholder_id, year=2026, amount=60000),
        m.DividendPayment(shareholder_id=b.shareholder_id, year=2026, amount=40000),
    ])
    session.commit()
    return a, b


def test_list_shareholders_capital_dividends_and_share_pct():
    s = SessionLocal()
    try:
        _seed(s)
        out = svc.list_shareholders(s)
        assert out["count"] == 2
        assert out["total_capital"] == 1_000_000.0
        assert out["total_dividends"] == 150_000.0
        ahmed = next(r for r in out["shareholders"] if r["code"] == "O1")
        assert ahmed["total_dividends"] == 110_000.0
        assert ahmed["share_pct"] == 60.0  # 600k / 1000k
    finally:
        s.close()


def test_shareholder_detail_history_by_year():
    s = SessionLocal()
    try:
        a, _ = _seed(s)
        d = svc.shareholder_detail(s, a.shareholder_id)
        years = {h["year"]: h["amount"] for h in d["dividend_history"]}
        assert years == {2025: 50000.0, 2026: 60000.0}
        assert d["dividend_history"][0]["year"] == 2026  # newest first
        assert d["total_dividends"] == 110_000.0
    finally:
        s.close()


def test_shareholder_detail_missing_returns_none():
    s = SessionLocal()
    try:
        assert svc.shareholder_detail(s, 999999) is None
    finally:
        s.close()


def _mini_source(path):
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE company_Owner (coow_id INT, coow_code TEXT, coow_name_ar TEXT, "
            "coow_name_en TEXT, tel TEXT, mobile TEXT, address TEXT, coow_current_money REAL, "
            "coow_start_money REAL, active INT, deleted INT)"
        ))
        c.execute(text(
            "INSERT INTO company_Owner VALUES "
            "(1,'O1','مالك','Owner','02','010','طنطا',600000,500000,1,0),"
            "(9,'O9','محذوف','Gone',NULL,NULL,NULL,0,0,1,1)"
        ))
        c.execute(text(
            "CREATE TABLE Gedo_Dividends_paied (dividends_id INT, coow_id INT, yaer_id INT, "
            "gf_id INT, paied_money REAL)"
        ))
        c.execute(text("INSERT INTO Gedo_Dividends_paied VALUES (1,1,2026,900,70000),(2,55,2026,0,5)"))
    return eng


def test_etl_load_shareholders_upserts_and_skips_deleted(tmp_path):
    src = _mini_source(tmp_path / "own.db")
    try:
        from sqlalchemy import inspect

        insp = inspect(src)
        with src.connect() as conn, SessionLocal() as dst:
            counts: dict = {}
            etl._load_shareholders(insp, conn, dst, counts)
            dst.commit()
            # The deleted owner (coow_id 9) is skipped; only owner 1 mirrored.
            assert counts["shareholders"] == 1
            # The dividend for an unknown owner (coow_id 55) is skipped.
            assert counts["dividends"] == 1

            sh = dst.query(m.Shareholder).filter_by(source_id=1).one()
            assert float(sh.current_capital) == 600000.0
            assert dst.query(m.DividendPayment).filter_by(shareholder_id=sh.shareholder_id).count() == 1

            # Re-running upserts (no duplicate shareholder or dividend).
            counts2: dict = {}
            etl._load_shareholders(insp, conn, dst, counts2)
            dst.commit()
            assert dst.query(m.Shareholder).filter_by(source_id=1).count() == 1
            assert dst.query(m.DividendPayment).count() == 1
    finally:
        src.dispose()
        s = SessionLocal()
        try:
            s.execute(delete(m.DividendPayment))
            s.execute(delete(m.Shareholder))
            s.commit()
        finally:
            s.close()


def test_api_shareholders(client):
    s = SessionLocal()
    try:
        _seed(s)
    finally:
        s.close()
    r = client.get("/api/shareholders")
    assert r.status_code == 200
    assert r.json()["count"] == 2

    sid = r.json()["shareholders"][0]["shareholder_id"]
    d = client.get(f"/api/shareholders/{sid}")
    assert d.status_code == 200
    assert "dividend_history" in d.json()

    assert client.get("/api/shareholders/999999").status_code == 404
