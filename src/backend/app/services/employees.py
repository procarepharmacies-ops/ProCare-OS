"""Employee management."""
from __future__ import annotations

import re
import secrets

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import models as m
from app.services import auth as auth_svc

ROLES = ("ceo", "manager", "assistant")


def _job_map(session: Session) -> dict[int, str]:
    rows = session.execute(select(m.Job.job_id, m.Job.name_ar)).all()
    return {jid: name for jid, name in rows}


def _branch_name(session: Session, branch_id: int | None) -> str | None:
    if not branch_id:
        return None
    return session.scalar(select(m.Branch.name_ar).where(m.Branch.branch_id == branch_id))


def list_employees(session: Session, branch_id: int | None = None, limit: int = 200) -> list[dict]:
    q = select(m.Employee).order_by(m.Employee.employee_id)
    if branch_id:
        q = q.where(m.Employee.branch_id == branch_id)

    rows = session.scalars(q.limit(limit)).all()
    jobs = _job_map(session)
    return [
        {
            "employee_id": e.employee_id,
            "name_ar": e.name_ar,
            "name_en": e.name_en,
            "username": e.username,
            "role": e.role,
            "job_id": e.job_id,
            "job_name": jobs.get(e.job_id) if e.job_id else None,
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
    e = session.scalar(select(m.Employee).where(m.Employee.employee_id == employee_id))
    if not e:
        return None

    jobs = _job_map(session)
    return {
        "employee_id": e.employee_id,
        "name_ar": e.name_ar,
        "name_en": e.name_en,
        "username": e.username,
        "role": e.role,
        "job_id": e.job_id,
        "job_name": jobs.get(e.job_id) if e.job_id else None,
        "branch_id": e.branch_id,
        "branch_name": _branch_name(session, e.branch_id),
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
    rows = session.scalars(select(m.Job).order_by(m.Job.job_id)).all()
    return [{"job_id": j.job_id, "name_ar": j.name_ar, "name_en": j.name_en} for j in rows]


def employee_summary(session: Session, branch_id: int | None = None) -> dict:
    q_total = select(func.count()).select_from(m.Employee)
    q_active = select(func.count()).select_from(m.Employee).where(m.Employee.is_active == True)  # noqa: E712

    if branch_id:
        q_total = q_total.where(m.Employee.branch_id == branch_id)
        q_active = q_active.where(m.Employee.branch_id == branch_id)

    total = int(session.scalar(q_total) or 0)
    active = int(session.scalar(q_active) or 0)

    return {
        "total_employees": total,
        "active_employees": active,
        "inactive_employees": total - active,
    }


def _slugify_username(session: Session, name_en: str | None, name_ar: str) -> str:
    """A short, unique, login-shaped username from a name. ASCII only — falls
    back to a generic prefix when the name has no Latin characters (Arabic
    names with no name_en given)."""
    base = re.sub(r"[^a-z0-9]+", "", (name_en or "").lower()) or "staff"
    candidate = base
    n = 1
    existing = set(session.scalars(select(m.Employee.username)).all())
    while candidate in existing:
        n += 1
        candidate = f"{base}{n}"
    return candidate


def create_employee(
    session: Session,
    name_ar: str,
    name_en: str | None = None,
    role: str | None = None,
    branch_id: int | None = None,
    job_id: int | None = None,
    basic_salary: float = 0,
    username: str | None = None,
    password: str | None = None,
    has_login: bool = True,
) -> dict:
    """Create an employee. When ``has_login`` is False (e.g. cleaning staff,
    anyone who shouldn't sign into ProCare), an inert, never-disclosed
    username/password is generated instead — the row still satisfies the
    schema's NOT NULL columns, but nobody can ever authenticate as them."""
    if role and role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")

    if has_login:
        final_username = (username or "").strip() or _slugify_username(session, name_en, name_ar)
        final_password = password or secrets.token_urlsafe(12)
        final_role = role or "assistant"
    else:
        final_username = f"nologin-{secrets.token_hex(6)}"
        final_password = secrets.token_urlsafe(24)
        final_role = role or "assistant"

    emp = m.Employee(
        name_ar=name_ar,
        name_en=name_en,
        username=final_username,
        password_hash=auth_svc.hash_password(final_password),
        role=final_role,
        branch_id=branch_id,
        job_id=job_id,
        basic_salary=basic_salary,
    )
    session.add(emp)
    session.commit()
    session.refresh(emp)

    return {
        "employee_id": emp.employee_id,
        "name_ar": emp.name_ar,
        "name_en": emp.name_en,
        "username": emp.username if has_login else None,
        # Only ever returned once, at creation time — never stored in plain
        # text and never retrievable again after this response.
        "password": final_password if has_login else None,
        "role": emp.role,
        "has_login": has_login,
        "branch_id": emp.branch_id,
    }
