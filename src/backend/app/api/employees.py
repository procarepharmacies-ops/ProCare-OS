"""Employee management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import employees

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("/list")
def employee_list(
    branch_id: int | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"employees": employees.list_employees(session, branch_id, limit)}


@router.get("/{employee_id}")
def employee_detail(
    employee_id: int,
    session: Session = Depends(get_session),
):
    result = employees.employee_detail(session, employee_id)
    if not result:
        return {"error": "Employee not found"}
    return result


@router.get("/jobs/list")
def jobs_list(session: Session = Depends(get_session)):
    return {"jobs": employees.list_jobs(session)}


@router.get("/summary")
def employee_summary(
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return employees.employee_summary(session, branch_id)
