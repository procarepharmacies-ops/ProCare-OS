"""Sales-rep commission calculator (حاسبة عمولة مندوب البيع).

eStock's rep-commission screen: pick a period and a percentage, the system
totals each sales rep's net sales and pays ``sales_value × rate``. ProCare
mirrors it over its own clean schema — sales are attributed to a rep via
``sales.cashier_id`` (populated by the ETL from eStock's Sales_header).

Two halves:
  * ``compute_commissions`` — a **read-only** preview. Net sales per rep in the
    window (sales minus return invoices), the effective rate (a per-rep
    override or the run's default), and the resulting commission.
  * ``post_commission_run`` — snapshots that preview into a ``commission_runs``
    row + one ``commission_run_lines`` per rep, atomically. The posted run is
    the auditable payout record; voiding keeps it (status='void').

Rate is always in **percent** (5 → 5%). Sales with a NULL ``cashier_id`` have
no rep to pay, so they are excluded from both the preview and the payout.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import branch_filter, money, sql_day


def _net_sales_by_rep(session: Session, start: date, end: date, branch_id: int | None):
    """Per-rep (sales_value, bills_count) for [start, end] inclusive.

    ``sales_value`` is NET of returns: the sum of non-return invoice totals
    minus the sum of return-invoice totals, both attributed to the same rep.
    ``bills_count`` counts only the non-return invoices (a return is not a
    "sale" the rep made). Reps with a NULL cashier_id are skipped.
    """
    # Signed total per invoice: returns subtract, sales add. Grouping this way
    # keeps it to a single scan and works identically on SQLite / SQL Server.
    signed_total = func.sum(
        func.coalesce(m.Sale.total_net, 0)
        * case((m.Sale.is_return == True, -1), else_=1)  # noqa: E712
    )
    bills = func.sum(case((m.Sale.is_return == True, 0), else_=1))  # noqa: E712

    rows = session.execute(
        select(
            m.Sale.cashier_id,
            signed_total.label("sales_value"),
            bills.label("bills_count"),
        )
        .where(
            m.Sale.cashier_id.is_not(None),
            branch_filter(m.Sale, branch_id),
            sql_day(m.Sale.sale_date) >= start,
            sql_day(m.Sale.sale_date) <= end,
        )
        .group_by(m.Sale.cashier_id)
    ).all()
    return {r.cashier_id: (money(r.sales_value), int(r.bills_count or 0)) for r in rows}


def compute_commissions(
    session: Session,
    start: date,
    end: date,
    branch_id: int | None = None,
    default_rate_pct: float = 0.0,
    rep_rates: dict[int, float] | None = None,
) -> dict:
    """Read-only commission preview for the period.

    Args:
        start, end: inclusive day range.
        branch_id: scope to one branch (None/0 = consolidated).
        default_rate_pct: percent applied to reps without an override.
        rep_rates: {employee_id: rate_pct} per-rep overrides.

    Returns a dict with one row per rep who had activity in the window, each
    carrying its net ``sales_value``, effective ``rate_pct`` and ``commission``,
    plus the run totals.
    """
    rep_rates = rep_rates or {}
    default_rate = round(float(default_rate_pct or 0), 2)
    by_rep = _net_sales_by_rep(session, start, end, branch_id)

    # Resolve names for the reps that showed up (one query, not per-row).
    emp_ids = list(by_rep.keys())
    names: dict[int, m.Employee] = {}
    if emp_ids:
        for emp in session.scalars(
            select(m.Employee).where(m.Employee.employee_id.in_(emp_ids))
        ):
            names[emp.employee_id] = emp

    reps = []
    total_sales = 0.0
    total_commission = 0.0
    for emp_id, (sales_value, bills) in by_rep.items():
        rate = round(float(rep_rates.get(emp_id, default_rate) or 0), 2)
        commission = money(sales_value * rate / 100.0)
        emp = names.get(emp_id)
        reps.append({
            "employee_id": emp_id,
            "name_ar": emp.name_ar if emp else None,
            "name_en": emp.name_en if emp else None,
            "sales_value": sales_value,
            "bills_count": bills,
            "rate_pct": rate,
            "commission": commission,
        })
        total_sales += sales_value
        total_commission += commission

    # Highest earners first — that's the order a manager settles in.
    reps.sort(key=lambda r: r["commission"], reverse=True)

    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "branch_id": branch_id or 0,
        "default_rate_pct": default_rate,
        "rep_count": len(reps),
        "reps": reps,
        "total_sales": money(total_sales),
        "total_commission": money(total_commission),
    }


def _serialize_run(run: m.CommissionRun, emp_names: dict[int, m.Employee] | None = None) -> dict:
    emp_names = emp_names or {}
    return {
        "run_id": run.run_id,
        "branch_id": run.branch_id or 0,
        "period_start": run.period_start.isoformat(),
        "period_end": run.period_end.isoformat(),
        "default_rate_pct": money(run.default_rate_pct),
        "total_sales": money(run.total_sales),
        "total_commission": money(run.total_commission),
        "status": run.status,
        "note": run.note,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "posted_by": run.posted_by,
        "voided_at": run.voided_at.isoformat() if run.voided_at else None,
        "lines": [
            {
                "line_id": ln.line_id,
                "employee_id": ln.employee_id,
                "name_ar": emp_names[ln.employee_id].name_ar if ln.employee_id in emp_names else None,
                "name_en": emp_names[ln.employee_id].name_en if ln.employee_id in emp_names else None,
                "sales_value": money(ln.sales_value),
                "bills_count": ln.bills_count,
                "rate_pct": money(ln.rate_pct),
                "commission": money(ln.commission),
            }
            for ln in sorted(run.lines, key=lambda x: x.commission, reverse=True)
        ],
    }


def post_commission_run(
    session: Session,
    start: date,
    end: date,
    branch_id: int | None = None,
    default_rate_pct: float = 0.0,
    rep_rates: dict[int, float] | None = None,
    note: str | None = None,
    posted_by: int | None = None,
) -> dict:
    """Recompute the preview and persist it as a posted commission run.

    Recomputing inside the same transaction (rather than trusting a
    client-supplied preview) guarantees the payout matches live sales data at
    post time. Atomic: one run header + its rep lines commit together. Reps
    with a zero commission are still recorded (audit completeness).
    """
    preview = compute_commissions(session, start, end, branch_id, default_rate_pct, rep_rates)

    run = m.CommissionRun(
        branch_id=branch_id or None,
        period_start=start,
        period_end=end,
        default_rate_pct=round(float(default_rate_pct or 0), 2),
        total_sales=preview["total_sales"],
        total_commission=preview["total_commission"],
        status="posted",
        note=(note or None),
        posted_by=posted_by,
    )
    for rep in preview["reps"]:
        run.lines.append(
            m.CommissionRunLine(
                employee_id=rep["employee_id"],
                sales_value=rep["sales_value"],
                bills_count=rep["bills_count"],
                rate_pct=rep["rate_pct"],
                commission=rep["commission"],
            )
        )
    session.add(run)
    session.commit()
    session.refresh(run)

    emp_names = {
        e.employee_id: e
        for e in session.scalars(
            select(m.Employee).where(
                m.Employee.employee_id.in_([ln.employee_id for ln in run.lines] or [-1])
            )
        )
    }
    return _serialize_run(run, emp_names)


def list_runs(session: Session, branch_id: int | None = None, limit: int = 50) -> dict:
    """Recent posted/void commission runs (headers only), newest first."""
    limit = max(1, min(limit, 200))
    stmt = select(m.CommissionRun).order_by(m.CommissionRun.run_id.desc()).limit(limit)
    if branch_id:
        stmt = stmt.where(m.CommissionRun.branch_id == branch_id)
    runs = session.scalars(stmt).all()
    return {
        "runs": [
            {
                "run_id": r.run_id,
                "branch_id": r.branch_id or 0,
                "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(),
                "default_rate_pct": money(r.default_rate_pct),
                "total_sales": money(r.total_sales),
                "total_commission": money(r.total_commission),
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ],
        "count": len(runs),
    }


def get_run(session: Session, run_id: int) -> dict | None:
    """One commission run with its rep lines, or None if it doesn't exist."""
    run = session.get(m.CommissionRun, run_id)
    if run is None:
        return None
    emp_names = {
        e.employee_id: e
        for e in session.scalars(
            select(m.Employee).where(
                m.Employee.employee_id.in_([ln.employee_id for ln in run.lines] or [-1])
            )
        )
    }
    return _serialize_run(run, emp_names)


def void_run(session: Session, run_id: int) -> dict | None:
    """Void a posted run (keeps the row + lines for the audit trail).

    Idempotent: voiding an already-void run is a no-op. Returns None if the run
    doesn't exist.
    """
    run = session.get(m.CommissionRun, run_id)
    if run is None:
        return None
    if run.status != "void":
        run.status = "void"
        run.voided_at = datetime.utcnow()
        session.commit()
        session.refresh(run)
    return get_run(session, run_id)
