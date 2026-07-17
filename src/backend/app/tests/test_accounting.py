"""Accounting sales-summary tests: paid-amount split by payment type."""
from __future__ import annotations

from sqlalchemy import func, select

from app.db import models as m
from app.services import accounting, pos
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


def test_sales_summary_splits_paid_amount_by_payment_type(session):
    before = accounting.sales_summary(session, branch_id=1, days=365)

    pid, _ = _product_with_live_stock(session, 1)

    # Cash sale: cash_paid defaults to net, card_paid 0.
    cash_sale = pos.create_sale(session, branch_id=1, lines=[pos.SaleLineInput(pid, 1)])

    # Card sale: paid entirely by card.
    card_sale = pos.create_sale(
        session, branch_id=1, lines=[pos.SaleLineInput(pid, 1)],
        cash_paid=0.0, card_paid=50.0,
    )

    # Credit sale: unpaid, on account (override to bypass any limit).
    over = next(
        c for c in session.scalars(select(m.Customer)).all()
        if c.credit_limit and c.current_balance > c.credit_limit
    )
    admin = session.scalar(select(m.Employee).where(m.Employee.can_sale_credit == True))  # noqa: E712
    credit_sale = pos.create_sale(
        session, branch_id=1, lines=[pos.SaleLineInput(pid, 1)],
        customer_id=over.customer_id, is_credit=True, override_by=admin.employee_id,
    )
    session.commit()

    after = accounting.sales_summary(session, branch_id=1, days=365)

    # New keys are present.
    for key in ("cash_paid", "card_paid", "total_paid", "credit_sales"):
        assert key in after

    assert after["cash_paid"] - before["cash_paid"] == float(cash_sale.total_net)
    assert after["card_paid"] - before["card_paid"] == 50.0
    assert after["credit_sales"] - before["credit_sales"] == float(credit_sale.total_net)
    assert after["total_paid"] == round(after["cash_paid"] + after["card_paid"], 2)
