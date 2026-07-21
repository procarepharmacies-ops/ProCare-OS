"""Phase 6 tests: sales-rep commission calculator (حاسبة عمولة مندوب البيع).

Uses a far-future sale-date window (2030-03) so the ~1100 seeded sales per
cashier (dated 2026) never leak into the assertions — every test controls its
own net-sales figures.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import delete

from app.db import models as m
from app.db.base import SessionLocal
from app.services import commissions as svc

WIN_START = date(2030, 3, 1)
WIN_END = date(2030, 3, 31)


def _mk_sale(session, cashier_id, total_net, *, is_return=False, day=10, branch_id=1):
    session.add(
        m.Sale(
            branch_id=branch_id,
            cashier_id=cashier_id,
            sale_date=datetime(2030, 3, day, 12, 0, 0),
            total_gross=total_net,
            total_net=total_net,
            is_return=is_return,
        )
    )


@pytest.fixture(autouse=True)
def clean_slate():
    """Remove any commission runs and the test window's sales before each test."""
    s = SessionLocal()
    try:
        s.execute(delete(m.CommissionRunLine))
        s.execute(delete(m.CommissionRun))
        # Drop only our synthetic window so we don't touch the seed's sales.
        s.execute(
            delete(m.Sale).where(
                m.Sale.sale_date >= datetime(2030, 3, 1),
                m.Sale.sale_date < datetime(2030, 4, 1),
            )
        )
        s.commit()
    finally:
        s.close()
    yield


# ---------------------------------------------------------------- compute --

def test_preview_nets_returns_and_applies_rate():
    s = SessionLocal()
    try:
        _mk_sale(s, cashier_id=2, total_net=1000)
        _mk_sale(s, cashier_id=2, total_net=500)
        _mk_sale(s, cashier_id=2, total_net=200, is_return=True)  # nets out
        s.commit()

        out = svc.compute_commissions(s, WIN_START, WIN_END, branch_id=1, default_rate_pct=5)
        rep = next(r for r in out["reps"] if r["employee_id"] == 2)
        # 1000 + 500 - 200 = 1300 net; 5% => 65
        assert rep["sales_value"] == 1300.0
        assert rep["bills_count"] == 2  # returns don't count as bills
        assert rep["rate_pct"] == 5.0
        assert rep["commission"] == 65.0
        assert out["total_commission"] == 65.0
    finally:
        s.close()


def test_preview_skips_null_cashier():
    s = SessionLocal()
    try:
        _mk_sale(s, cashier_id=None, total_net=9999)
        _mk_sale(s, cashier_id=2, total_net=100)
        s.commit()
        out = svc.compute_commissions(s, WIN_START, WIN_END, branch_id=1, default_rate_pct=10)
        assert all(r["employee_id"] is not None for r in out["reps"])
        assert out["total_sales"] == 100.0
    finally:
        s.close()


def test_preview_window_excludes_out_of_range_sales():
    s = SessionLocal()
    try:
        _mk_sale(s, cashier_id=2, total_net=100, day=10)  # in window
        _mk_sale(s, cashier_id=2, total_net=999, day=10, branch_id=1)
        # A sale on 2030-04-05 is outside [03-01, 03-31].
        s.add(
            m.Sale(
                branch_id=1, cashier_id=2, sale_date=datetime(2030, 4, 5),
                total_gross=777, total_net=777, is_return=False,
            )
        )
        s.commit()
        out = svc.compute_commissions(s, WIN_START, WIN_END, branch_id=1, default_rate_pct=0)
        rep = next(r for r in out["reps"] if r["employee_id"] == 2)
        assert rep["sales_value"] == 1099.0  # 100 + 999, not 777
    finally:
        # clean the stray April sale
        s.execute(delete(m.Sale).where(m.Sale.sale_date == datetime(2030, 4, 5)))
        s.commit()
        s.close()


# ------------------------------------------------------------------- post --

def test_post_persists_run_with_per_rep_override():
    s = SessionLocal()
    try:
        _mk_sale(s, cashier_id=2, total_net=1000)
        _mk_sale(s, cashier_id=4, total_net=2000, branch_id=2)
        s.commit()

        run = svc.post_commission_run(
            s, WIN_START, WIN_END, branch_id=None, default_rate_pct=3,
            rep_rates={4: 10},  # rep 4 negotiated 10%
            note="March payout", posted_by=1,
        )
        assert run["status"] == "posted"
        lines = {l["employee_id"]: l for l in run["lines"]}
        assert lines[2]["rate_pct"] == 3.0 and lines[2]["commission"] == 30.0
        assert lines[4]["rate_pct"] == 10.0 and lines[4]["commission"] == 200.0
        assert run["total_commission"] == 230.0

        # Round-trips through get_run.
        fetched = svc.get_run(s, run["run_id"])
        assert fetched["total_commission"] == 230.0
        assert len(fetched["lines"]) == 2
    finally:
        s.close()


def test_repost_creates_new_run_history_preserved():
    s = SessionLocal()
    try:
        _mk_sale(s, cashier_id=2, total_net=1000)
        s.commit()
        r1 = svc.post_commission_run(s, WIN_START, WIN_END, branch_id=1, default_rate_pct=5)
        r2 = svc.post_commission_run(s, WIN_START, WIN_END, branch_id=1, default_rate_pct=5)
        assert r1["run_id"] != r2["run_id"]
        assert svc.list_runs(s, branch_id=1)["count"] == 2
    finally:
        s.close()


def test_void_keeps_row_and_lines():
    s = SessionLocal()
    try:
        _mk_sale(s, cashier_id=2, total_net=1000)
        s.commit()
        run = svc.post_commission_run(s, WIN_START, WIN_END, branch_id=1, default_rate_pct=5)
        voided = svc.void_run(s, run["run_id"])
        assert voided["status"] == "void"
        assert voided["voided_at"] is not None
        assert len(voided["lines"]) == 1  # lines survive
        # Idempotent second void.
        again = svc.void_run(s, run["run_id"])
        assert again["status"] == "void"
    finally:
        s.close()


# -------------------------------------------------------------------- API --

def test_api_preview_and_post_and_void(client):
    # Seed two sales for the window directly (the API stamps real-today dates).
    s = SessionLocal()
    try:
        _mk_sale(s, cashier_id=2, total_net=1000)
        s.commit()
    finally:
        s.close()

    p = client.get(
        "/api/commissions/preview",
        params={"period_start": "2030-03-01", "period_end": "2030-03-31",
                "branch_id": 1, "default_rate_pct": 5},
    )
    assert p.status_code == 200
    body = p.json()
    assert body["total_sales"] == 1000.0
    assert body["total_commission"] == 50.0

    posted = client.post(
        "/api/commissions/runs",
        json={"period_start": "2030-03-01", "period_end": "2030-03-31",
              "branch_id": 1, "default_rate_pct": 5, "note": "api test"},
    )
    assert posted.status_code == 200
    run_id = posted.json()["run_id"]
    assert posted.json()["total_commission"] == 50.0

    got = client.get(f"/api/commissions/runs/{run_id}")
    assert got.status_code == 200 and got.json()["status"] == "posted"

    voided = client.post(f"/api/commissions/runs/{run_id}/void")
    assert voided.status_code == 200 and voided.json()["status"] == "void"


def test_api_bad_period_400(client):
    r = client.get(
        "/api/commissions/preview",
        params={"period_start": "2030-03-31", "period_end": "2030-03-01"},
    )
    assert r.status_code == 400


def test_api_missing_run_404(client):
    assert client.get("/api/commissions/runs/999999").status_code == 404
    assert client.post("/api/commissions/runs/999999/void").status_code == 404
