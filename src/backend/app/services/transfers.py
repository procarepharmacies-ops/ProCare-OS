"""Stock transfer management between branches."""
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import models as m


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
