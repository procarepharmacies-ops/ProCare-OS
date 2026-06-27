"""Stock transfer management between branches."""
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import models as m


def list_transfers(session: Session, branch_id: int | None = None, status: str | None = None, limit: int = 200) -> list[dict]:
    """Fetch stock transfers, optionally filtered by branch/status."""
    q = select(m.StockTransfer).order_by(m.StockTransfer.created_at.desc())

    if branch_id:
        q = q.where((m.StockTransfer.from_branch_id == branch_id) | (m.StockTransfer.to_branch_id == branch_id))
    if status:
        q = q.where(m.StockTransfer.status == status)

    rows = session.scalars(q.limit(limit)).all()
    return [
        {
            "transfer_id": t.transfer_id,
            "from_branch_id": t.from_branch_id,
            "from_branch_name": (
                session.scalar(select(m.Branch.name_ar).where(m.Branch.branch_id == t.from_branch_id))
                or "Unknown"
            ),
            "to_branch_id": t.to_branch_id,
            "to_branch_name": (
                session.scalar(select(m.Branch.name_ar).where(m.Branch.branch_id == t.to_branch_id))
                or "Unknown"
            ),
            "status": t.status,
            "requested_by": t.requested_by,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "shipped_at": t.shipped_at.isoformat() if t.shipped_at else None,
            "received_at": t.received_at.isoformat() if t.received_at else None,
        }
        for t in rows
    ]


def transfer_detail(session: Session, transfer_id: int) -> dict | None:
    """Fetch a single transfer with its lines."""
    t = session.scalar(select(m.StockTransfer).where(m.StockTransfer.transfer_id == transfer_id))
    if not t:
        return None

    lines = session.scalars(
        select(m.StockTransferLine).where(m.StockTransferLine.transfer_id == transfer_id)
    ).all()

    return {
        "transfer_id": t.transfer_id,
        "from_branch_id": t.from_branch_id,
        "from_branch_name": (
            session.scalar(select(m.Branch.name_ar).where(m.Branch.branch_id == t.from_branch_id))
            or "Unknown"
        ),
        "to_branch_id": t.to_branch_id,
        "to_branch_name": (
            session.scalar(select(m.Branch.name_ar).where(m.Branch.branch_id == t.to_branch_id))
            or "Unknown"
        ),
        "status": t.status,
        "requested_by": t.requested_by,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "shipped_at": t.shipped_at.isoformat() if t.shipped_at else None,
        "received_at": t.received_at.isoformat() if t.received_at else None,
        "lines": [
            {
                "line_id": tl.line_id,
                "product_id": tl.product_id,
                "product_name": (
                    session.scalar(select(m.Product.name_ar).where(m.Product.product_id == tl.product_id))
                    or "Unknown"
                ),
                "amount": float(tl.amount or 0),
                "buy_price": float(tl.buy_price or 0),
                "exp_date": tl.exp_date.isoformat() if tl.exp_date else None,
            }
            for tl in lines
        ],
    }


def transfer_summary(session: Session, branch_id: int | None = None) -> dict:
    """Summary: pending transfers, completed, by branch."""
    q_pending = select(func.count()).select_from(m.StockTransfer).where(m.StockTransfer.status.in_(["requested", "in_transit"]))
    q_completed = select(func.count()).select_from(m.StockTransfer).where(m.StockTransfer.status == "received")
    q_total = select(func.count()).select_from(m.StockTransfer)

    if branch_id:
        q_pending = q_pending.where(
            (m.StockTransfer.from_branch_id == branch_id) | (m.StockTransfer.to_branch_id == branch_id)
        )
        q_completed = q_completed.where(
            (m.StockTransfer.from_branch_id == branch_id) | (m.StockTransfer.to_branch_id == branch_id)
        )
        q_total = q_total.where(
            (m.StockTransfer.from_branch_id == branch_id) | (m.StockTransfer.to_branch_id == branch_id)
        )

    pending = session.scalar(q_pending) or 0
    completed = session.scalar(q_completed) or 0
    total = session.scalar(q_total) or 0

    return {
        "pending_transfers": int(pending),
        "completed_transfers": int(completed),
        "total_transfers": int(total),
    }
