"""Daily staff tasks — assignment, completion, and a small daily summary.

CEO/managers create tasks (optionally scoped to a branch and/or a specific
employee); everyone can list their own and mark them done. All reads/writes go
through here so the API layer stays thin.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import case, func, select
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
    # Order: pending first, then high→low priority, then earliest due.
    priority_rank = case(
        (m.EmployeeTask.priority == "high", 0),
        (m.EmployeeTask.priority == "normal", 1),
        else_=2,
    )
    q = select(m.EmployeeTask).order_by(
        m.EmployeeTask.status.desc(), priority_rank, m.EmployeeTask.due_date, m.EmployeeTask.task_id.desc()
    )
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
            "priority": t.priority,
            "category": t.category,
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
    priority: str = "normal",
    category: str = "general",
) -> dict:
    t = m.EmployeeTask(
        title=title.strip(),
        details=(details or "").strip() or None,
        assignee_id=assignee_id,
        branch_id=branch_id,
        due_date=due_date,
        created_by=created_by,
        priority=priority if priority in ("high", "normal", "low") else "normal",
        category=category or "general",
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


# --- Recurring weekly operations tasks ---------------------------------------
# The pharmacy's standing weekly routine (owner-defined operations checklist):
# stocktake, merchandising/shelf-place check, expiry sweep, reorder review.
# Title carries the ISO-week tag so creation is idempotent per week per branch.
WEEKLY_OPS_TEMPLATES = [
    (
        "جرد أسبوعي للمخزون",
        "عد فعلي للأصناف عالية الحركة ومطابقة الكميات مع النظام — أي فرق يُسجل من شاشة تسوية المخزون.",
    ),
    (
        "مراجعة أماكن المنتجات والعرض (ميرشندايزينج)",
        "مراجعة أماكن الأصناف على الأرفف حسب خانة (المكان) في شاشة المخزون، وإبراز العروض والأصناف الموسمية.",
    ),
    (
        "مراجعة الصلاحيات القريبة",
        "مراجعة تنبيهات الصلاحية (٩٠/٣٠/٧ يوم) وتقديم الأقرب انتهاءً للأمام (FEFO) أو عرضه بخصم.",
    ),
    (
        "مراجعة النواقص وإعادة الطلب",
        "مراجعة مسودات إعادة الطلب الذكية واعتماد أوامر الشراء للموردين.",
    ),
]


def ensure_weekly_ops_tasks(session: Session) -> int:
    """Create this ISO-week's standard operations tasks for every active
    branch (once — safe to call at every startup). Returns how many were
    created. Due date = end of the ISO week (Sunday)."""
    from datetime import date, timedelta

    today = date.today()
    year, week, weekday = today.isocalendar()
    tag = f"[أسبوع {week}/{year}]"
    due = today + timedelta(days=7 - weekday)  # ISO Sunday

    branches = session.scalars(select(m.Branch).where(m.Branch.is_active == True)).all()  # noqa: E712
    created = 0
    for branch in branches:
        for title, details in WEEKLY_OPS_TEMPLATES:
            full_title = f"{title} {tag}"
            # One per (title, branch, week): the week tag is in the title.
            if session.scalar(
                select(func.count())
                .select_from(m.EmployeeTask)
                .where(m.EmployeeTask.title == full_title, m.EmployeeTask.branch_id == branch.branch_id)
            ):
                continue
            session.add(
                m.EmployeeTask(
                    title=full_title,
                    details=details,
                    branch_id=branch.branch_id,
                    due_date=due,
                    status="pending",
                )
            )
            created += 1
    if created:
        session.commit()
    return created
