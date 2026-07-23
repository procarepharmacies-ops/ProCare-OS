"""Phase 6 tests: POS partial-fill → shortage-sheet auto-insert (Shortcoming)."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db import models as m
from app.services import pos
from app.services.common import today


def _product_with_live_stock(session, branch_id):
    row = session.execute(
        select(m.StockBatch.product_id, func.sum(m.StockBatch.amount))
        .where(
            m.StockBatch.branch_id == branch_id,
            m.StockBatch.amount > 0,
            (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > today()),  # noqa: E711
        )
        .group_by(m.StockBatch.product_id)
        .order_by(func.sum(m.StockBatch.amount).desc())
    ).first()
    return row[0], float(row[1])


def _open_shortages(session, product_id):
    return session.scalars(
        select(m.ShortageItem).where(
            m.ShortageItem.product_id == product_id,
            m.ShortageItem.status == "open",
            m.ShortageItem.note.like("%auto from POS%"),
        )
    ).all()


def test_partial_fill_sells_available_and_logs_remainder(session):
    pid, available = _product_with_live_stock(session, 1)
    before = len(_open_shortages(session, pid))
    request = available + 5  # 5 more than we can sell

    sale = pos.create_sale(
        session, branch_id=1, lines=[pos.SaleLineInput(pid, request)],
        cashier_id=1, allow_partial=True,
    )

    # Sold exactly what was on hand; the line reflects the capped amount.
    line = next(sl for sl in sale.lines if sl.product_id == pid)
    assert float(line.amount) == pytest.approx(available)

    # Stock is now drained to zero (sellable).
    on_hand = float(session.scalar(
        select(func.coalesce(func.sum(m.StockBatch.amount), 0)).where(
            m.StockBatch.product_id == pid, m.StockBatch.branch_id == 1,
            m.StockBatch.amount > 0,
            (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > today()),  # noqa: E711
        )
    ) or 0)
    assert on_hand == pytest.approx(0.0)

    # The unmet 5 units were auto-logged onto the shortage sheet.
    shorts = _open_shortages(session, pid)
    assert len(shorts) == before + 1
    assert float(shorts[-1].qty_requested) == pytest.approx(5.0)
    assert shorts[-1].reported_by == 1


def test_strict_mode_still_raises_on_insufficient_stock(session):
    pid, available = _product_with_live_stock(session, 1)
    with pytest.raises(pos.POSError) as ei:
        pos.create_sale(
            session, branch_id=1, lines=[pos.SaleLineInput(pid, available + 1)], cashier_id=1,
        )
    assert ei.value.code == "insufficient_stock"
    # No shortage row leaked from the failed (rolled-back) attempt.
    assert session.scalar(
        select(func.count()).select_from(m.ShortageItem).where(
            m.ShortageItem.product_id == pid, m.ShortageItem.note.like("%auto from POS%"),
        )
    ) == 0


def test_partial_fill_with_nothing_sellable_refuses_sale(session):
    # A product with zero sellable stock at branch 1.
    pid = session.scalar(
        select(m.Product.product_id).where(
            m.Product.is_deleted == False,  # noqa: E712
            ~m.Product.product_id.in_(
                select(m.StockBatch.product_id).where(
                    m.StockBatch.branch_id == 1, m.StockBatch.amount > 0
                )
            ),
        )
    )
    assert pid is not None
    with pytest.raises(pos.POSError) as ei:
        pos.create_sale(
            session, branch_id=1, lines=[pos.SaleLineInput(pid, 3)],
            cashier_id=1, allow_partial=True,
        )
    assert ei.value.code == "no_sellable_stock"


def test_api_partial_fill_echoes_filled_lines(client, session):
    pid, available = _product_with_live_stock(session, 2)
    r = client.post(
        "/api/sales",
        json={
            "branch_id": 2, "cashier_id": 4, "allow_partial": True,
            "lines": [{"product_id": pid, "amount": available + 3}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    sold = next(l for l in body["lines"] if l["product_id"] == pid)
    assert sold["amount"] == pytest.approx(available)
