"""Payroll depth (الرواتب) — read views over the ``Employee_salary`` mirror.

Surfaces a per-employee payroll panel: base / commission / deductions /
advances / net, with the monthly history behind it. Read-only.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import money


def _record_out(p: m.PayrollRecord) -> dict:
    return {
        "payroll_id": p.payroll_id,
        "period": p.period,
        "state": p.state,
        "basic_salary": money(p.basic_salary),
        "commission": money(p.commission),
        "over_commission": money(p.over_commission),
        "deduction": money(p.deduction),
        "absence_money": money(p.absence_money),
        "cash_advance": money(p.cash_advance),
        "source_total": money(p.source_total),
        "net": money(p.net),
    }


def employee_payroll(session: Session, employee_id: int) -> dict | None:
    """One employee's payroll panel: the latest monthly record broken into
    base / commission (regular + over) / deductions (deduction + absence) /
    advances / net, plus the full monthly history. ``None`` if the employee
    doesn't exist; ``records: []`` when payroll hasn't been mirrored yet."""
    emp = session.get(m.Employee, employee_id)
    if emp is None:
        return None

    records = session.scalars(
        select(m.PayrollRecord)
        .where(m.PayrollRecord.employee_id == employee_id)
        .order_by(m.PayrollRecord.payroll_id.desc())
    ).all()

    # Individual salary advances (سلف) ledger — a detail list separate from the
    # monthly payroll roll-up, newest first.
    advance_rows = session.scalars(
        select(m.SalaryAdvance)
        .where(m.SalaryAdvance.employee_id == employee_id)
        .order_by(m.SalaryAdvance.advance_id.desc())
    ).all()
    advances = [
        {
            "advance_id": a.advance_id,
            "amount": money(a.amount),
            "advance_type": a.advance_type,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in advance_rows
    ]
    advances_total = money(sum(float(a.amount or 0) for a in advance_rows))

    latest = records[0] if records else None
    summary = None
    if latest is not None:
        commission = float(latest.commission or 0) + float(latest.over_commission or 0)
        deductions = float(latest.deduction or 0) + float(latest.absence_money or 0)
        summary = {
            "period": latest.period,
            "basic_salary": money(latest.basic_salary),
            "commission": money(commission),
            "deductions": money(deductions),
            "advances": money(latest.cash_advance),
            "net": money(latest.net),
        }

    return {
        "employee_id": emp.employee_id,
        "name_ar": emp.name_ar,
        "name_en": emp.name_en,
        # The Employee row's own basic salary (from the Employee master mirror),
        # shown as a fallback when no monthly payroll record exists yet.
        "base_salary_on_file": money(emp.basic_salary),
        "has_records": bool(records),
        "summary": summary,
        "records": [_record_out(p) for p in records],
        "advances": advances,
        "advances_total": advances_total,
    }
