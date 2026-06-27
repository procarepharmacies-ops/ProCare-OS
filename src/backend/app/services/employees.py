"""Employee management."""
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import models as m


def list_employees(session: Session, branch_id: int | None = None, limit: int = 200) -> list[dict]:
    """Fetch employees, optionally filtered by branch."""
    q = select(m.Employee).order_by(m.Employee.employee_id)

    if branch_id:
        q = q.where(m.Employee.branch_id == branch_id)

    rows = session.scalars(q.limit(limit)).all()
    return [
        {
            "employee_id": e.employee_id,
            "name_ar": e.name_ar,
            "name_en": e.name_en,
            "username": e.username,
            "job_id": e.job_id,
            "job_name": (
                session.scalar(select(m.Job.name_ar).where(m.Job.job_id == e.job_id))
                if e.job_id
                else None
            ),
            "branch_id": e.branch_id,
            "basic_salary": float(e.basic_salary or 0),
            "max_disc_per": float(e.max_disc_per or 0),
            "permissions": {
                "can_see_buy_price": e.can_see_buy_price,
                "can_edit_sell_price": e.can_edit_sell_price,
                "can_sale_credit": e.can_sale_credit,
                "can_return": e.can_return,
                "can_void": e.can_void,
                "can_change_shift": e.can_change_shift,
            },
            "is_active": e.is_active,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]


def employee_detail(session: Session, employee_id: int) -> dict | None:
    """Fetch a single employee with full details."""
    e = session.scalar(select(m.Employee).where(m.Employee.employee_id == employee_id))
    if not e:
        return None

    return {
        "employee_id": e.employee_id,
        "name_ar": e.name_ar,
        "name_en": e.name_en,
        "username": e.username,
        "job_id": e.job_id,
        "job_name": (
            session.scalar(select(m.Job.name_ar).where(m.Job.job_id == e.job_id)) if e.job_id else None
        ),
        "branch_id": e.branch_id,
        "branch_name": (
            session.scalar(select(m.Branch.name_ar).where(m.Branch.branch_id == e.branch_id))
            if e.branch_id
            else None
        ),
        "basic_salary": float(e.basic_salary or 0),
        "max_disc_per": float(e.max_disc_per or 0),
        "permissions": {
            "can_see_buy_price": e.can_see_buy_price,
            "can_edit_sell_price": e.can_edit_sell_price,
            "can_sale_credit": e.can_sale_credit,
            "can_return": e.can_return,
            "can_void": e.can_void,
            "can_change_shift": e.can_change_shift,
        },
        "is_active": e.is_active,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def list_jobs(session: Session) -> list[dict]:
    """Fetch all job titles."""
    rows = session.scalars(select(m.Job).order_by(m.Job.job_id)).all()
    return [{"job_id": j.job_id, "name_ar": j.name_ar, "name_en": j.name_en} for j in rows]


def employee_summary(session: Session, branch_id: int | None = None) -> dict:
    """Summary: total staff, by branch, active/inactive."""
    q_total = select(func.count()).select_from(m.Employee)
    q_active = select(func.count()).select_from(m.Employee).where(m.Employee.is_active == True)

    if branch_id:
        q_total = q_total.where(m.Employee.branch_id == branch_id)
        q_active = q_active.where(m.Employee.branch_id == branch_id)

    total = session.scalar(q_total) or 0
    active = session.scalar(q_active) or 0

    return {
        "total_employees": int(total),
        "active_employees": int(active),
        "inactive_employees": int(total - active),
    }
