"""Daily staff tasks endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db import models as m
from app.db.base import get_session
from app.services import tasks as tasks_svc

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    details: str | None = None
    assignee_id: int | None = None
    branch_id: int | None = None
    due_date: date | None = None


class StatusIn(BaseModel):
    status: str  # pending | done


@router.get("")
def list_tasks(
    assignee_id: int | None = Query(None),
    branch_id: int | None = Query(None),
    status: str | None = Query(None),
    _auth=Depends(auth_guard()),
    session: Session = Depends(get_session),
):
    return {
        "tasks": tasks_svc.list_tasks(session, assignee_id, branch_id, status),
        "summary": tasks_svc.summary(session, branch_id=branch_id, assignee_id=assignee_id),
    }


@router.post("")
def create_task(
    payload: TaskIn,
    auth=Depends(auth_guard(("ceo", "manager"))),
    session: Session = Depends(get_session),
):
    return tasks_svc.create_task(
        session,
        title=payload.title,
        details=payload.details,
        assignee_id=payload.assignee_id,
        branch_id=payload.branch_id,
        due_date=payload.due_date,
        created_by=(auth or {}).get("employee_id"),
    )


@router.post("/{task_id}/status")
def set_status(
    task_id: int,
    payload: StatusIn,
    _auth=Depends(auth_guard()),
    session: Session = Depends(get_session),
):
    try:
        result = tasks_svc.set_status(session, task_id, payload.status)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.get("/assignees")
def assignees(
    _auth=Depends(auth_guard(("ceo", "manager"))),
    session: Session = Depends(get_session),
):
    """The assignable-staff dropdown — lighter than the CEO-only employees
    router, so managers can assign tasks without seeing salaries."""
    rows = session.scalars(
        select(m.Employee).where(m.Employee.is_active == True).order_by(m.Employee.name_ar)  # noqa: E712
    ).all()
    return {
        "assignees": [
            {
                "employee_id": e.employee_id,
                "name_ar": e.name_ar,
                "name_en": e.name_en,
                "role": e.role,
                "branch_id": e.branch_id,
            }
            for e in rows
            if not e.username.startswith("nologin-")
        ]
    }
