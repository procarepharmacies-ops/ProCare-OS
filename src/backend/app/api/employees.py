"""Employee management endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db.base import get_session
from app.services import employees

router = APIRouter(prefix="/employees", tags=["employees"])


class EmployeeIn(BaseModel):
    name_ar: str
    name_en: str | None = None
    role: str | None = None  # ceo | manager | assistant — ignored when has_login is False
    branch_id: int | None = None
    job_id: int | None = None
    basic_salary: float = 0
    username: str | None = None
    password: str | None = None
    # False for staff who shouldn't sign into ProCare at all (e.g. cleaning
    # staff) — still recorded as an employee, but with no usable login.
    has_login: bool = True


@router.get("/list")
def employee_list(
    branch_id: int | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"employees": employees.list_employees(session, branch_id, limit)}


@router.get("/jobs/list")
def jobs_list(session: Session = Depends(get_session)):
    return {"jobs": employees.list_jobs(session)}


@router.get("/summary")
def employee_summary(
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return employees.employee_summary(session, branch_id)


@router.post("")
def create_employee(payload: EmployeeIn, session: Session = Depends(get_session)):
    try:
        return employees.create_employee(
            session,
            name_ar=payload.name_ar,
            name_en=payload.name_en,
            role=payload.role,
            branch_id=payload.branch_id,
            job_id=payload.job_id,
            basic_salary=payload.basic_salary,
            username=payload.username,
            password=payload.password,
            has_login=payload.has_login,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{employee_id}")
def employee_detail(
    employee_id: int,
    session: Session = Depends(get_session),
):
    result = employees.employee_detail(session, employee_id)
    if not result:
        return {"error": "Employee not found"}
    return result


class ContactIn(BaseModel):
    phone: str | None = None


@router.patch("/{employee_id}/contact", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def set_contact(employee_id: int, payload: ContactIn, session: Session = Depends(get_session)):
    """Set the WhatsApp phone used for password reset (CEO/manager only)."""
    from app.db import models as m

    emp = session.get(m.Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.phone = (payload.phone or "").strip() or None
    session.commit()
    return {"ok": True, "employee_id": employee_id, "phone": emp.phone}


class AdminResetIn(BaseModel):
    new_password: str = Field(min_length=8)


@router.post("/{employee_id}/reset-password", dependencies=[Depends(auth_guard(("ceo",)))])
def admin_reset_password(employee_id: int, payload: AdminResetIn, session: Session = Depends(get_session)):
    """CEO fallback: set an employee's password directly (e.g. no WhatsApp)."""
    from app.db import models as m
    from app.services import auth as auth_svc

    emp = session.get(m.Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.password_hash = auth_svc.hash_password(payload.new_password)
    emp.reset_code_hash = None
    emp.reset_code_expires = None
    emp.reset_attempts = 0
    session.commit()
    return {"ok": True}


class GoalIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    details: str | None = None
    category: str = "performance"  # performance | training | behavior
    target_date: date | None = None
    created_by: int | None = None


class GoalStatusIn(BaseModel):
    status: str  # active | achieved | dropped


@router.get("/{employee_id}/goals")
def employee_goals(employee_id: int, session: Session = Depends(get_session)):
    """PMP / development plan for one employee."""
    return {"goals": employees.list_goals(session, employee_id)}


@router.post("/{employee_id}/goals")
def create_goal(employee_id: int, payload: GoalIn, session: Session = Depends(get_session)):
    from app.services.pos import POSError

    try:
        return employees.create_goal(
            session,
            employee_id,
            payload.title,
            details=payload.details,
            category=payload.category,
            target_date=payload.target_date,
            created_by=payload.created_by,
        )
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


@router.post("/goals/{goal_id}/status")
def set_goal_status(goal_id: int, payload: GoalStatusIn, session: Session = Depends(get_session)):
    from app.services.pos import POSError

    try:
        return employees.set_goal_status(session, goal_id, payload.status)
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
