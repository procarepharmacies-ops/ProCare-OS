"""Cash desk / shift management — eStock's Cash_disk_close (1,647 closures).

A cashier opens a shift with a float; at close, expected cash is computed from
cash movements recorded during the shift (cash sales minus cash refunds), and
the variance against the counted drawer is stored — the daily control eStock
ran at every shift change.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.pos import POSError


def current_shift(session: Session, branch_id: int) -> m.CashShift | None:
    return session.scalars(
        select(m.CashShift)
        .where(m.CashShift.branch_id == branch_id, m.CashShift.status == "open")
        .order_by(m.CashShift.opened_at.desc())
    ).first()


def open_shift(
    session: Session, branch_id: int, *, cashier_id: int | None = None, opening_float: float = 0.0
) -> m.CashShift:
    if current_shift(session, branch_id) is not None:
        raise POSError("shift_already_open", "توجد وردية مفتوحة بالفعل / a shift is already open")
    shift = m.CashShift(branch_id=branch_id, cashier_id=cashier_id, opening_float=float(opening_float))
    session.add(shift)
    session.commit()
    session.refresh(shift)
    return shift


def _cash_flow_since(session: Session, branch_id: int, since: datetime) -> float:
    """Net cash into the drawer since ``since``: cash-ledger debits (cash
    sales) minus credits (cash refunds/purchases paid from the drawer)."""
    # 1s tolerance: ledger timestamps are second-precision (DB CURRENT_TIMESTAMP)
    # while ``since`` may carry microseconds — without it, a cash sale in the
    # same second as the shift-open would be missed.
    debit, credit = session.execute(
        select(
            func.coalesce(func.sum(m.LedgerEntry.debit), 0),
            func.coalesce(func.sum(m.LedgerEntry.credit), 0),
        ).where(
            m.LedgerEntry.branch_id == branch_id,
            m.LedgerEntry.account_type == "cash",
            m.LedgerEntry.entry_date >= since - timedelta(seconds=1),
        )
    ).one()
    return float(debit or 0) - float(credit or 0)


def close_shift(session: Session, branch_id: int, *, counted_cash: float) -> m.CashShift:
    shift = current_shift(session, branch_id)
    if shift is None:
        raise POSError("no_open_shift", "لا توجد وردية مفتوحة / no open shift")
    expected = round(float(shift.opening_float) + _cash_flow_since(session, branch_id, shift.opened_at), 2)
    shift.closed_at = datetime.now()
    shift.counted_cash = float(counted_cash)
    shift.expected_cash = expected
    shift.variance = round(float(counted_cash) - expected, 2)
    shift.status = "closed"
    session.commit()
    session.refresh(shift)
    return shift


def shift_dict(shift: m.CashShift) -> dict:
    return {
        "shift_id": shift.shift_id,
        "branch_id": shift.branch_id,
        "cashier_id": shift.cashier_id,
        "status": shift.status,
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else None,
        "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
        "opening_float": float(shift.opening_float or 0),
        "counted_cash": float(shift.counted_cash) if shift.counted_cash is not None else None,
        "expected_cash": float(shift.expected_cash) if shift.expected_cash is not None else None,
        "variance": float(shift.variance) if shift.variance is not None else None,
    }
