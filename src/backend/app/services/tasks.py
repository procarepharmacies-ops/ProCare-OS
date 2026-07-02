"""Daily staff tasks — assignment, completion, and a small daily summary.

CEO/managers create tasks (optionally scoped to a branch and/or a specific
employee); everyone can list their own and mark them done. All reads/writes go
through here so the API layer stays thin.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m


def _emp_names(session: Session) -> dict[int, str]:
    rows = session.execute(select(m.Employee.employee_id, m.Employee.name_ar)).all()
    return dict(rows)


def list_tasks(
    session: Session,
    assignee_id: int | None = None,
    branch_id: int | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict]:
    q = select(m.EmployeeTask).order_by(m.EmployeeTask.status.desc(), m.EmployeeTask.due_date, m.EmployeeTask.task_id.desc())
    if assignee_id:
        q = q.where(m.EmployeeTask.assignee_id == assignee_id)
    if branch_id:
        q = q.where(m.EmployeeTask.branch_id == branch_id)
    if status:
        q = q.where(m.EmployeeTask.status == status)

    names = _emp_names(session)
    return [
        {
            "task_id": t.task_id,
            "title": t.title,
            "details": t.details,
            "assignee_id": t.assignee_id,
            "assignee_name": names.get(t.assignee_id),
            "branch_id": t.branch_id,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "status": t.status,
            "created_by": t.created_by,
            "created_by_name": names.get(t.created_by),
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in session.scalars(q.limit(limit))
    ]


def create_task(
    session: Session,
    title: str,
    details: str | None = None,
    assignee_id: int | None = None,
    branch_id: int | None = None,
    due_date: date | None = None,
    created_by: int | None = None,
) -> dict:
    t = m.EmployeeTask(
        title=title.strip(),
        details=(details or "").strip() or None,
        assignee_id=assignee_id,
        branch_id=branch_id,
        due_date=due_date,
        created_by=created_by,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return {"task_id": t.task_id, "title": t.title, "status": t.status}


def set_status(session: Session, task_id: int, status: str) -> dict | None:
    if status not in ("pending", "done"):
        raise ValueError("status must be 'pending' or 'done'")
    t = session.get(m.EmployeeTask, task_id)
    if t is None:
        return None
    t.status = status
    t.completed_at = datetime.now() if status == "done" else None
    session.commit()
    return {"task_id": t.task_id, "status": t.status}


def summary(session: Session, branch_id: int | None = None, assignee_id: int | None = None) -> dict:
    """Pending / done-today counts for the tasks KPI row."""
    base = select(func.count()).select_from(m.EmployeeTask)
    if branch_id:
        base = base.where(m.EmployeeTask.branch_id == branch_id)
    if assignee_id:
        base = base.where(m.EmployeeTask.assignee_id == assignee_id)

    pending = session.scalar(base.where(m.EmployeeTask.status == "pending")) or 0
    # Midnight-boundary compare (portable: SQLite and SQL Server alike).
    start_of_today = datetime.combine(datetime.now().date(), datetime.min.time())
    done_today = session.scalar(
        base.where(m.EmployeeTask.status == "done", m.EmployeeTask.completed_at >= start_of_today)
    ) or 0
    return {"pending": int(pending), "done_today": int(done_today)}
