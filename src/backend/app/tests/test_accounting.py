"""Accounting sales-summary tests: paid-amount split by payment type."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, func, select

from app.db import models as m
from app.db.base import SessionLocal
from app.services import accounting, pos
from app.services.common import today

# A far-out account_ref no seeded ledger row uses, so the statement /
# adjustments tests only ever see rows this file created.
_ACC_REF = 987654


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


@pytest.fixture
def clean_ledger():
    """Drop this file's synthetic account_ref rows before + after each test."""
    def _clear():
        s = SessionLocal()
        try:
            # Our synthetic account rows, plus any test-created adjustments
            # (ref_type='adjust' is never produced by the seed/ETL) so the
            # adjustments report — which aggregates across accounts — stays
            # isolated between tests.
            s.execute(
                delete(m.LedgerEntry).where(
                    (m.LedgerEntry.account_ref == _ACC_REF) | (m.LedgerEntry.ref_type == "adjust")
                )
            )
            s.commit()
        finally:
            s.close()
    _clear()
    yield
    _clear()


def _add(session, *, debit=0.0, credit=0.0, days_ago=1, reason_code=None, ref_type="manual"):
    session.add(
        m.LedgerEntry(
            branch_id=1,
            account_type="customer",
            account_ref=_ACC_REF,
            ref_type=ref_type,
            reason_code=reason_code,
            entry_date=datetime.now() - timedelta(days=days_ago),
            debit=debit,
            credit=credit,
        )
    )


def test_account_statement_running_balance(session, clean_ledger):
    # One entry BEFORE the 30-day window (opening), two inside it.
    _add(session, debit=1000, days_ago=60)   # opening: +1000
    _add(session, debit=300, days_ago=10)    # -> 1300
    _add(session, credit=200, days_ago=5)    # -> 1100
    session.commit()

    st = accounting.account_statement(session, "customer", _ACC_REF, days=30, branch_id=1)
    assert st["opening_balance"] == 1000.0
    assert [l["balance"] for l in st["lines"]] == [1300.0, 1100.0]
    assert st["total_debit"] == 300.0 and st["total_credit"] == 200.0
    assert st["closing_balance"] == 1100.0
    # Chronological order (oldest first).
    assert st["lines"][0]["debit"] == 300.0


def test_account_statement_bad_type_raises(session):
    with pytest.raises(pos.POSError):
        accounting.account_statement(session, "not_a_type")


def test_journal_with_reason_is_tagged_adjustment(session, clean_ledger):
    out = accounting.create_journal_entry(
        session, 1, "cash", credit=50, reason_code="cash_short",
    )
    assert out["ref_type"] == "adjust"
    assert out["reason_code"] == "cash_short"
    entry = session.get(m.LedgerEntry, out["entry_id"])
    assert entry.ref_type == "adjust" and entry.reason_code == "cash_short"


def test_journal_bad_reason_rejected(session):
    with pytest.raises(pos.POSError):
        accounting.create_journal_entry(session, 1, "cash", credit=50, reason_code="nope")


def test_journal_without_reason_stays_manual(session):
    out = accounting.create_journal_entry(session, 1, "cash", debit=10)
    assert out["ref_type"] == "manual" and out["reason_code"] is None


def test_adjustments_report_groups_by_reason(session, clean_ledger):
    _add(session, debit=100, reason_code="bad_debt", ref_type="adjust")
    _add(session, debit=40, reason_code="bad_debt", ref_type="adjust")
    _add(session, credit=25, reason_code="cash_short", ref_type="adjust")
    _add(session, debit=999, ref_type="manual")  # not an adjustment -> excluded
    session.commit()

    rep = accounting.adjustments_report(session, branch_id=1, days=30)
    by_code = {g["reason_code"]: g for g in rep["groups"]}
    assert by_code["bad_debt"]["count"] == 2
    assert by_code["bad_debt"]["debit"] == 140.0
    assert by_code["cash_short"]["credit"] == 25.0
    # The plain manual 999 must not leak into the adjustments totals.
    assert rep["total_debit"] == 140.0
    assert rep["total_credit"] == 25.0


def test_adjustment_reasons_catalogue():
    reasons = accounting.adjustment_reasons()
    codes = {r["code"] for r in reasons}
    assert {"opening_balance", "bad_debt", "cash_short", "other"} <= codes
    assert all(r["ar"] and r["en"] for r in reasons)
