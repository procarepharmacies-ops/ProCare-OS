"""Daily/weekly ops task templates: idempotency, priority, role assignment."""
from __future__ import annotations

from sqlalchemy import select

from app.db import models as m
from app.services import tasks as tasks_svc


def test_daily_ops_idempotent_per_day(session):
    # Ensure today's tasks exist (may already have been created by app startup
    # on the shared DB), then assert a repeat call creates nothing new and the
    # count is stable — that's the idempotency guarantee.
    tasks_svc.ensure_daily_ops_tasks(session)
    before = len(tasks_svc.list_tasks(session))
    n2 = tasks_svc.ensure_daily_ops_tasks(session)
    assert n2 == 0
    assert len(tasks_svc.list_tasks(session)) == before


def test_daily_ops_have_priority_and_category(session):
    tasks_svc.ensure_daily_ops_tasks(session)
    rows = tasks_svc.list_tasks(session)
    opening = [t for t in rows if t["category"] == "opening"]
    assert opening, "expected opening-category daily tasks"
    assert any(t["priority"] == "high" for t in opening)


def test_daily_ops_auto_assign_by_role(session):
    tasks_svc.ensure_daily_ops_tasks(session)
    # Cash-count/closing templates target the assistant role; at least one of the
    # created tasks should be assigned when a matching employee exists.
    branch = session.scalars(select(m.Branch)).first().branch_id
    has_assistant = session.scalars(
        select(m.Employee).where(m.Employee.branch_id == branch, m.Employee.role == "assistant")
    ).first()
    if not has_assistant:
        return
    assigned = [t for t in tasks_svc.list_tasks(session, branch_id=branch) if t["assignee_id"]]
    assert assigned, "expected at least one role-assigned daily task"
