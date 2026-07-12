"""Stocktaking (الجرد) — eStock-style physical inventory counts.

Workflow: create a count session (full / periodic / partial) → the session
snapshots every live batch at the branch as "expected" → staff record the
physically-counted quantities on the count sheet → a manager posts the session,
which applies every difference as a stock adjustment (ضبط الأصناف) through the
normal ``StockMovement`` audit trail (reason='adjust', ref_id=count_id).

Posting is atomic: one transaction adjusts all batches and closes the session.
An open session never blocks sales — if stock moved between snapshot and post,
the applied delta is counted minus the batch's LIVE amount at post time, so the
batch always lands exactly on the physically-counted quantity.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import money
from app.services.pos import POSError


def create_count(
    session: Session,
    branch_id: int,
    count_type: str = "full",
    *,
    note: str | None = None,
    created_by: int | None = None,
    product_ids: list[int] | None = None,
) -> dict:
    """Open a count session and snapshot expected quantities.

    ``full`` snapshots every batch with stock at the branch. ``periodic`` /
    ``partial`` limit the sheet to ``product_ids`` when given (e.g. this
    week's top movers or one shelf).
    """
    if count_type not in ("full", "periodic", "partial"):
        raise POSError("bad_count_type", f"نوع جرد غير صحيح / bad count type: {count_type}")
    branch = session.get(m.Branch, branch_id)
    if branch is None:
        raise POSError("branch_not_found", f"الفرع غير موجود #{branch_id} / branch not found")

    stmt = select(m.StockBatch).where(
        m.StockBatch.branch_id == branch_id, m.StockBatch.amount > 0
    )
    if product_ids:
        stmt = stmt.where(m.StockBatch.product_id.in_(product_ids))
    batches = session.scalars(stmt).all()
    if not batches:
        raise POSError("nothing_to_count", "لا توجد أصناف بها رصيد للجرد / no stock to count")

    count = m.StockCount(
        branch_id=branch_id, count_type=count_type, note=note, created_by=created_by
    )
    session.add(count)
    session.flush()  # count_id
    names = dict(
        session.execute(
            select(m.Product.product_id, m.Product.name_ar).where(
                m.Product.product_id.in_({b.product_id for b in batches})
            )
        ).all()
    )
    for b in batches:
        session.add(
            m.StockCountLine(
                count_id=count.count_id,
                batch_id=b.batch_id,
                product_id=b.product_id,
                name_ar=names.get(b.product_id),
                expected_qty=float(b.amount),
            )
        )
    session.commit()
    return {"count_id": count.count_id, "lines": len(batches), "status": count.status}


def list_counts(session: Session, branch_id: int | None = None, limit: int = 50) -> list[dict]:
    stmt = (
        select(m.StockCount, m.Branch.name_ar, func.count(m.StockCountLine.line_id))
        .join(m.Branch, m.Branch.branch_id == m.StockCount.branch_id)
        .join(m.StockCountLine, m.StockCountLine.count_id == m.StockCount.count_id, isouter=True)
        .group_by(m.StockCount.count_id, m.Branch.name_ar)
        .order_by(m.StockCount.count_id.desc())
        .limit(limit)
    )
    if branch_id:
        stmt = stmt.where(m.StockCount.branch_id == branch_id)
    out = []
    for c, branch_name, n_lines in session.execute(stmt):
        counted = session.scalar(
            select(func.count())
            .select_from(m.StockCountLine)
            .where(m.StockCountLine.count_id == c.count_id, m.StockCountLine.counted_qty.is_not(None))
        )
        out.append(
            {
                "count_id": c.count_id,
                "branch_id": c.branch_id,
                "branch": branch_name,
                "count_type": c.count_type,
                "status": c.status,
                "note": c.note,
                "lines": n_lines,
                "counted": counted or 0,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "posted_at": c.posted_at.isoformat() if c.posted_at else None,
            }
        )
    return out


def get_count(session: Session, count_id: int) -> dict:
    """Count sheet: every line with product identity, expected vs counted, and
    the money value of each variance (at buy price — what a shortage costs)."""
    c = session.get(m.StockCount, count_id)
    if c is None:
        raise POSError("count_not_found", f"جلسة الجرد غير موجودة #{count_id} / count not found")
    # Outer joins: the sync mirror may have reloaded products/batches since the
    # snapshot — the sheet still renders from the line's own stored fields.
    rows = session.execute(
        select(m.StockCountLine, m.Product, m.StockBatch)
        .join(m.Product, m.Product.product_id == m.StockCountLine.product_id, isouter=True)
        .join(m.StockBatch, m.StockBatch.batch_id == m.StockCountLine.batch_id, isouter=True)
        .where(m.StockCountLine.count_id == count_id)
        .order_by(m.StockCountLine.name_ar, m.StockCountLine.line_id)
    ).all()

    lines = []
    total_shortage_qty = total_shortage_value = 0.0
    total_overage_qty = total_overage_value = 0.0
    for line, product, batch in rows:
        buy_price = float(batch.buy_price or 0) if batch is not None else 0.0
        variance = None
        variance_value = None
        if line.counted_qty is not None:
            variance = round(float(line.counted_qty) - float(line.expected_qty), 3)
            variance_value = round(variance * buy_price, 3)
            if variance < 0:
                total_shortage_qty += -variance
                total_shortage_value += -variance_value
            elif variance > 0:
                total_overage_qty += variance
                total_overage_value += variance_value
        lines.append(
            {
                "line_id": line.line_id,
                "batch_id": line.batch_id,
                "product_id": line.product_id,
                "name_ar": product.name_ar if product is not None else line.name_ar,
                "name_en": product.name_en if product is not None else None,
                "shelf_location": product.shelf_location if product is not None else None,
                "exp_date": batch.exp_date.isoformat() if batch is not None and batch.exp_date else None,
                "buy_price": money(buy_price),
                "sell_price": money(batch.sell_price) if batch is not None else 0,
                "expected_qty": money(line.expected_qty),
                "counted_qty": money(line.counted_qty) if line.counted_qty is not None else None,
                "variance": variance,
                "variance_value": variance_value,
                "posted_delta": money(line.posted_delta) if line.posted_delta is not None else None,
                "batch_missing": batch is None,
            }
        )
    return {
        "count_id": c.count_id,
        "branch_id": c.branch_id,
        "count_type": c.count_type,
        "status": c.status,
        "note": c.note,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "posted_at": c.posted_at.isoformat() if c.posted_at else None,
        "lines": lines,
        "summary": {
            "total_lines": len(lines),
            "counted_lines": sum(1 for l in lines if l["counted_qty"] is not None),
            "variance_lines": sum(1 for l in lines if l["variance"] not in (None, 0)),
            "shortage_qty": money(total_shortage_qty),
            "shortage_value": money(total_shortage_value),
            "overage_qty": money(total_overage_qty),
            "overage_value": money(total_overage_value),
        },
    }


def record_lines(session: Session, count_id: int, entries: list[dict]) -> dict:
    """Save physically-counted quantities: ``[{line_id, counted_qty}]``.
    Re-recording a line overwrites it (recount) while the session is open."""
    c = session.get(m.StockCount, count_id)
    if c is None:
        raise POSError("count_not_found", f"جلسة الجرد غير موجودة #{count_id} / count not found")
    if c.status != "open":
        raise POSError("count_closed", "جلسة الجرد مغلقة / count session is closed")
    saved = 0
    for e in entries:
        line = session.get(m.StockCountLine, int(e["line_id"]))
        if line is None or line.count_id != count_id:
            continue
        qty = e.get("counted_qty")
        if qty is None:
            line.counted_qty = None  # un-count (clear a mistake)
            saved += 1
            continue
        qty = float(qty)
        if qty < 0:
            raise POSError("bad_quantity", "الكمية لا يمكن أن تكون سالبة / amount cannot be negative")
        line.counted_qty = qty
        saved += 1
    session.commit()
    return {"count_id": count_id, "saved": saved}


def post_count(session: Session, count_id: int, *, employee_id: int | None = None) -> dict:
    """Close the session and apply every counted difference as an adjustment.

    Atomic: one transaction sets each counted batch to its physical quantity,
    writes the audit movement (reason='adjust', ref_id=count_id), and marks the
    session posted. Uncounted lines are left untouched (their stock is trusted).
    """
    c = session.get(m.StockCount, count_id)
    if c is None:
        raise POSError("count_not_found", f"جلسة الجرد غير موجودة #{count_id} / count not found")
    if c.status != "open":
        raise POSError("count_closed", "جلسة الجرد مغلقة بالفعل / count already closed")

    lines = session.scalars(
        select(m.StockCountLine).where(
            m.StockCountLine.count_id == count_id, m.StockCountLine.counted_qty.is_not(None)
        )
    ).all()
    if not lines:
        raise POSError("nothing_counted", "لم يتم تسجيل أي كمية بعد / nothing counted yet")

    adjusted = 0
    skipped = 0
    for line in lines:
        batch = session.get(m.StockBatch, line.batch_id)
        if batch is None:
            # A sync reload removed this batch since the snapshot — nothing to
            # adjust; the line stays in the report as history.
            skipped += 1
            continue
        delta = round(float(line.counted_qty) - float(batch.amount), 3)
        line.posted_delta = delta
        if delta == 0:
            continue
        batch.amount = float(line.counted_qty)
        session.add(
            m.StockMovement(
                batch_id=batch.batch_id,
                branch_id=batch.branch_id,
                delta=delta,
                reason="adjust",
                ref_id=count_id,
                employee_id=employee_id,
            )
        )
        adjusted += 1

    c.status = "posted"
    c.posted_by = employee_id
    c.posted_at = datetime.now()
    session.commit()
    return {
        "count_id": count_id,
        "status": "posted",
        "adjusted": adjusted,
        "counted": len(lines),
        "skipped_missing_batch": skipped,
    }


def cancel_count(session: Session, count_id: int) -> dict:
    """Abandon an open session — nothing is applied to stock."""
    c = session.get(m.StockCount, count_id)
    if c is None:
        raise POSError("count_not_found", f"جلسة الجرد غير موجودة #{count_id} / count not found")
    if c.status != "open":
        raise POSError("count_closed", "جلسة الجرد مغلقة بالفعل / count already closed")
    c.status = "cancelled"
    session.commit()
    return {"count_id": count_id, "status": "cancelled"}


def top_movers(session: Session, branch_id: int, limit: int = 30) -> list[int]:
    """Product ids of the fastest-selling items at a branch (last 30 days) —
    the default scope of a periodic count (الجرد الدوري)."""
    rows = session.execute(
        select(m.SaleLine.product_id, func.sum(m.SaleLine.amount).label("qty"))
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(
            m.Sale.branch_id == branch_id,
            m.Sale.is_return == False,  # noqa: E712
            m.Sale.sale_date >= datetime.now() - timedelta(days=30),
        )
        .group_by(m.SaleLine.product_id)
        .order_by(func.sum(m.SaleLine.amount).desc())
        .limit(limit)
    ).all()
    return [pid for pid, _ in rows]
