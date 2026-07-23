"""Shareholders / owners (المساهمون) — read views over the ``company_Owner`` and
``Gedo_Dividends_paied`` mirror.

Shows each shareholder's capital (starting → current) and the dividends paid to
them, plus a per-shareholder annual dividend history. Read-only.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import money


def list_shareholders(session: Session) -> dict:
    """Active shareholders with capital + total dividends ever paid, plus the
    consolidated totals for the register footer."""
    # Total dividends per shareholder in one grouped scan.
    div_rows = session.execute(
        select(m.DividendPayment.shareholder_id, func.coalesce(func.sum(m.DividendPayment.amount), 0))
        .group_by(m.DividendPayment.shareholder_id)
    ).all()
    div_by_sh = {sid: float(total or 0) for sid, total in div_rows}

    shareholders = session.scalars(
        select(m.Shareholder).where(m.Shareholder.is_active == True).order_by(m.Shareholder.shareholder_id)  # noqa: E712
    ).all()

    rows = []
    total_capital = 0.0
    total_dividends = 0.0
    for s in shareholders:
        paid = div_by_sh.get(s.shareholder_id, 0.0)
        rows.append({
            "shareholder_id": s.shareholder_id,
            "code": s.code,
            "name_ar": s.name_ar,
            "name_en": s.name_en,
            "current_capital": money(s.current_capital),
            "start_capital": money(s.start_capital),
            "total_dividends": money(paid),
        })
        total_capital += float(s.current_capital or 0)
        total_dividends += paid

    # Ownership share (%) of the current capital pool.
    for r in rows:
        r["share_pct"] = round(100.0 * r["current_capital"] / total_capital, 2) if total_capital else 0.0

    return {
        "shareholders": rows,
        "count": len(rows),
        "total_capital": money(total_capital),
        "total_dividends": money(total_dividends),
    }


def shareholder_detail(session: Session, shareholder_id: int) -> dict | None:
    """One shareholder with their dividend history grouped by year (newest first)."""
    s = session.get(m.Shareholder, shareholder_id)
    if s is None:
        return None

    year_rows = session.execute(
        select(
            m.DividendPayment.year,
            func.coalesce(func.sum(m.DividendPayment.amount), 0),
            func.count(m.DividendPayment.dividend_id),
        )
        .where(m.DividendPayment.shareholder_id == shareholder_id)
        .group_by(m.DividendPayment.year)
        .order_by(m.DividendPayment.year.desc())
    ).all()
    history = [
        {"year": year, "amount": money(total), "payments": int(cnt)}
        for year, total, cnt in year_rows
    ]
    return {
        "shareholder_id": s.shareholder_id,
        "code": s.code,
        "name_ar": s.name_ar,
        "name_en": s.name_en,
        "tel": s.tel,
        "mobile": s.mobile,
        "address": s.address,
        "current_capital": money(s.current_capital),
        "start_capital": money(s.start_capital),
        "is_active": bool(s.is_active),
        "total_dividends": money(sum(h["amount"] for h in history)),
        "dividend_history": history,
    }
