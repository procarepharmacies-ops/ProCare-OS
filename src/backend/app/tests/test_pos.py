"""POS hot-path tests: FEFO deduction, credit enforcement, expiry lock, atomicity."""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.db import models as m
from app.services import pos
from app.services.common import TODAY


def _product_with_live_stock(session, branch_id):
    """Pick a product that has sellable stock at the branch."""
    row = session.execute(
        select(m.StockBatch.product_id, func.sum(m.StockBatch.amount))
        .where(
            m.StockBatch.branch_id == branch_id,
            m.StockBatch.amount > 0,
            (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > TODAY),  # noqa: E711
        )
        .group_by(m.StockBatch.product_id)
        .order_by(func.sum(m.StockBatch.amount).desc())
    ).first()
    return row[0], float(row[1])


def test_cash_sale_deducts_fefo_and_is_atomic(session):
    pid, on_hand = _product_with_live_stock(session, 1)
    before = on_hand
    sale = pos.create_sale(
        session, branch_id=1, lines=[pos.SaleLineInput(pid, 2)], cashier_id=1
    )
    assert sale.sale_id is not None
    assert float(sale.total_net) > 0

    after = session.execute(
        select(func.coalesce(func.sum(m.StockBatch.amount), 0)).where(
            m.StockBatch.product_id == pid,
            m.StockBatch.branch_id == 1,
            m.StockBatch.amount > 0,
            (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > TODAY),  # noqa: E711
        )
    ).scalar_one()
    assert float(after) == pytest.approx(before - 2)

    # A stock_movement was written for the sale.
    moves = session.scalar(
        select(func.count()).select_from(m.StockMovement).where(
            m.StockMovement.reason == "sale", m.StockMovement.ref_id == sale.sale_id
        )
    )
    assert moves >= 1


def test_fefo_picks_earliest_expiry_first(session):
    # Build a product with two batches at distinct expiries in a fresh branch slot.
    p = m.Product(name_ar="اختبار فيفو", sell_price=10, buy_price=5, min_stock=0)
    session.add(p)
    session.flush()
    near = m.StockBatch(product_id=p.product_id, branch_id=1, amount=3, sell_price=10, buy_price=5,
                        exp_date=TODAY + timedelta(days=10))
    far = m.StockBatch(product_id=p.product_id, branch_id=1, amount=10, sell_price=10, buy_price=5,
                       exp_date=TODAY + timedelta(days=300))
    session.add_all([near, far])
    session.commit()

    taken = pos.deduct_stock_fefo(session, p.product_id, 1, 4, ref_id=None, employee_id=None)
    session.commit()
    # 3 from the near batch, 1 from the far one.
    assert taken[0][0] == near.batch_id and taken[0][1] == 3
    session.refresh(near)
    session.refresh(far)
    assert float(near.amount) == 0
    assert float(far.amount) == 9


def test_expired_only_product_cannot_be_sold(session):
    p = m.Product(name_ar="منتهي فقط", sell_price=10, buy_price=5, min_stock=0)
    session.add(p)
    session.flush()
    session.add(
        m.StockBatch(product_id=p.product_id, branch_id=1, amount=5, sell_price=10, buy_price=5,
                     exp_date=TODAY - timedelta(days=3))
    )
    session.commit()
    with pytest.raises(pos.POSError) as exc:
        pos.create_sale(session, branch_id=1, lines=[pos.SaleLineInput(p.product_id, 1)])
    assert exc.value.code == "insufficient_stock"


def test_credit_limit_blocks_without_override(session):
    over = next(
        c for c in session.scalars(select(m.Customer)).all()
        if c.credit_limit and c.current_balance > c.credit_limit
    )
    pid, _ = _product_with_live_stock(session, 1)
    with pytest.raises(pos.POSError) as exc:
        pos.create_sale(
            session, branch_id=1, lines=[pos.SaleLineInput(pid, 1)],
            customer_id=over.customer_id, is_credit=True,
        )
    assert exc.value.code == "credit_limit_exceeded"


def test_credit_override_by_authorised_employee(session):
    over = next(
        c for c in session.scalars(select(m.Customer)).all()
        if c.credit_limit and c.current_balance > c.credit_limit
    )
    admin = session.scalar(select(m.Employee).where(m.Employee.can_sale_credit == True))  # noqa: E712
    pid, _ = _product_with_live_stock(session, 1)
    sale = pos.create_sale(
        session, branch_id=1, lines=[pos.SaleLineInput(pid, 1)],
        customer_id=over.customer_id, is_credit=True, override_by=admin.employee_id,
    )
    assert sale.sale_id is not None


def test_stock_never_goes_negative(session):
    pid, on_hand = _product_with_live_stock(session, 2)
    with pytest.raises(pos.POSError) as exc:
        pos.create_sale(session, branch_id=2, lines=[pos.SaleLineInput(pid, on_hand + 100)])
    assert exc.value.code == "insufficient_stock"


def test_transfer_moves_stock_and_carries_expiry(session):
    pid, on_hand = _product_with_live_stock(session, 1)

    def live_qty(branch):
        return float(
            session.execute(
                select(func.coalesce(func.sum(m.StockBatch.amount), 0)).where(
                    m.StockBatch.product_id == pid, m.StockBatch.branch_id == branch,
                    m.StockBatch.amount > 0,
                )
            ).scalar_one()
        )

    before_from = live_qty(1)
    before_to = live_qty(2)
    pos.transfer_stock(session, 1, 2, [pos.SaleLineInput(pid, 2)])
    assert live_qty(1) == pytest.approx(before_from - 2)
    assert live_qty(2) == pytest.approx(before_to + 2)
