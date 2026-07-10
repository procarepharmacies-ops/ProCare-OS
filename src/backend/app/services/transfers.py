"""Stock transfer management between branches."""
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import models as m
from app.services import pos


def _branch_map(session: Session) -> dict[int, str]:
    """Preload branch_id -> name_ar map to avoid N+1 queries."""
    rows = session.execute(select(m.Branch.branch_id, m.Branch.name_ar)).all()
    return {bid: name for bid, name in rows}


def list_transfers(session: Session, branch_id: int | None = None, status: str | None = None, limit: int = 200) -> list[dict]:
    q = select(m.StockTransfer).order_by(m.StockTransfer.created_at.desc())

    if branch_id:
        q = q.where((m.StockTransfer.from_branch_id == branch_id) | (m.StockTransfer.to_branch_id == branch_id))
    if status:
        q = q.where(m.StockTransfer.status == status)

    rows = session.scalars(q.limit(limit)).all()
    names = _branch_map(session)
    return [
        {
            "transfer_id": t.transfer_id,
            "from_branch_id": t.from_branch_id,
            "from_branch_name": names.get(t.from_branch_id, "Unknown"),
            "to_branch_id": t.to_branch_id,
            "to_branch_name": names.get(t.to_branch_id, "Unknown"),
            "status": t.status,
            "requested_by": t.requested_by,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "shipped_at": t.shipped_at.isoformat() if t.shipped_at else None,
            "received_at": t.received_at.isoformat() if t.received_at else None,
        }
        for t in rows
    ]


def transfer_detail(session: Session, transfer_id: int) -> dict | None:
    t = session.scalar(select(m.StockTransfer).where(m.StockTransfer.transfer_id == transfer_id))
    if not t:
        return None

    names = _branch_map(session)
    lines = session.scalars(
        select(m.StockTransferLine).where(m.StockTransferLine.transfer_id == transfer_id)
    ).all()

    product_ids = [tl.product_id for tl in lines]
    prod_names = {}
    if product_ids:
        prod_rows = session.execute(
            select(m.Product.product_id, m.Product.name_ar).where(m.Product.product_id.in_(product_ids))
        ).all()
        prod_names = {pid: name for pid, name in prod_rows}

    return {
        "transfer_id": t.transfer_id,
        "from_branch_id": t.from_branch_id,
        "from_branch_name": names.get(t.from_branch_id, "Unknown"),
        "to_branch_id": t.to_branch_id,
        "to_branch_name": names.get(t.to_branch_id, "Unknown"),
        "status": t.status,
        "requested_by": t.requested_by,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "shipped_at": t.shipped_at.isoformat() if t.shipped_at else None,
        "received_at": t.received_at.isoformat() if t.received_at else None,
        "lines": [
            {
                "line_id": tl.line_id,
                "product_id": tl.product_id,
                "product_name": prod_names.get(tl.product_id, "Unknown"),
                "amount": float(tl.amount or 0),
                "buy_price": float(tl.buy_price or 0),
                "exp_date": tl.exp_date.isoformat() if tl.exp_date else None,
            }
            for tl in lines
        ],
    }


def _branch_manager(session: Session, branch_id: int) -> m.Employee | None:
    """A manager/CEO at the branch to route an approval to (falls back to any
    manager, then any active employee at the branch)."""
    for roles in (("manager", "ceo"), None):
        q = select(m.Employee).where(
            m.Employee.branch_id == branch_id, m.Employee.is_active == True  # noqa: E712
        )
        if roles:
            q = q.where(m.Employee.role.in_(roles))
        emp = session.scalars(q).first()
        if emp:
            return emp
    return None


def request_transfer(
    session: Session,
    from_branch_id: int,
    to_branch_id: int,
    lines: list[tuple[int, float]],
    *,
    requested_by: int | None = None,
) -> dict:
    """Create a transfer REQUEST (no stock moved yet), raise a high-priority
    approval task for the SOURCE branch's manager (they release the stock), and
    notify the manager over WhatsApp. Returns the created request summary."""
    line_inputs = [pos.SaleLineInput(product_id=int(pid), amount=float(qty)) for pid, qty in lines if qty > 0]
    transfer = pos.request_transfer(
        session, from_branch_id, to_branch_id, line_inputs, requested_by=requested_by
    )

    names = _branch_map(session)
    from_name = names.get(from_branch_id, "?")
    to_name = names.get(to_branch_id, "?")

    # Approval task for the source-branch manager (they own the stock).
    from app.services import tasks as tasks_svc

    manager = _branch_manager(session, from_branch_id)
    tasks_svc.create_task(
        session,
        title=f"مراجعة طلب تحويل #{transfer.transfer_id} إلى فرع {to_name}",
        details=(
            f"طلب تحويل {len(line_inputs)} صنف من فرع {from_name} إلى فرع {to_name}. "
            "راجع التوفر واعتمد أو ارفض من شاشة التحويلات."
        ),
        assignee_id=manager.employee_id if manager else None,
        branch_id=from_branch_id,
        created_by=requested_by,
        priority="high",
        category="approval",
    )

    # WhatsApp the manager (self-gating + fail-soft).
    from app.services import whatsapp as wa

    wa.notify_manager(wa.transfer_request_message(transfer.transfer_id, from_name, to_name, len(line_inputs)))

    return {
        "transfer_id": transfer.transfer_id,
        "status": transfer.status,
        "from_branch_id": from_branch_id,
        "to_branch_id": to_branch_id,
        "lines": len(line_inputs),
    }


def approve_transfer(session: Session, transfer_id: int, approved_by: int | None = None) -> dict:
    t = pos.approve_transfer(session, transfer_id, approved_by=approved_by)
    _close_approval_task(session, transfer_id)
    return {"transfer_id": t.transfer_id, "status": t.status}


def reject_transfer(session: Session, transfer_id: int) -> dict:
    t = pos.reject_transfer(session, transfer_id)
    _close_approval_task(session, transfer_id)
    return {"transfer_id": t.transfer_id, "status": t.status}


def _close_approval_task(session: Session, transfer_id: int) -> None:
    """Mark the matching approval task done once the request is resolved."""
    tasks = session.scalars(
        select(m.EmployeeTask).where(
            m.EmployeeTask.title.like(f"مراجعة طلب تحويل #{transfer_id} %"),
            m.EmployeeTask.status == "pending",
        )
    ).all()
    from datetime import datetime

    for t in tasks:
        t.status = "done"
        t.completed_at = datetime.now()
    if tasks:
        session.commit()


def transfer_summary(session: Session, branch_id: int | None = None) -> dict:
    q_pending = select(func.count()).select_from(m.StockTransfer).where(m.StockTransfer.status.in_(["requested", "in_transit"]))
    q_completed = select(func.count()).select_from(m.StockTransfer).where(m.StockTransfer.status == "received")
    q_total = select(func.count()).select_from(m.StockTransfer)

    if branch_id:
        branch_filter = (m.StockTransfer.from_branch_id == branch_id) | (m.StockTransfer.to_branch_id == branch_id)
        q_pending = q_pending.where(branch_filter)
        q_completed = q_completed.where(branch_filter)
        q_total = q_total.where(branch_filter)

    return {
        "pending_transfers": int(session.scalar(q_pending) or 0),
        "completed_transfers": int(session.scalar(q_completed) or 0),
        "total_transfers": int(session.scalar(q_total) or 0),
    }
