"""Purchase order management."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import models as m


def list_purchases(session: Session, branch_id: int | None = None, limit: int = 200) -> list[dict]:
    """Fetch recent purchases, optionally filtered by branch."""
    q = select(m.Purchase).order_by(m.Purchase.created_at.desc())
    if branch_id:
        q = q.where(m.Purchase.branch_id == branch_id)
    rows = session.scalars(q.limit(limit)).all()
    return [
        {
            "purchase_id": p.purchase_id,
            "branch_id": p.branch_id,
            "vendor_id": p.vendor_id,
            "vendor_name": (
                session.scalar(select(m.Vendor.name_ar).where(m.Vendor.vendor_id == p.vendor_id))
                or "Unknown"
            ),
            "bill_date": p.bill_date.isoformat() if p.bill_date else None,
            "bill_number": p.bill_number,
            "total_gross": float(p.total_gross or 0),
            "total_discount": float(p.total_discount or 0),
            "total_tax": float(p.total_tax or 0),
            "is_return": p.is_return,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in rows
    ]


def purchase_detail(session: Session, purchase_id: int) -> dict | None:
    """Fetch a single purchase with its lines."""
    p = session.scalar(select(m.Purchase).where(m.Purchase.purchase_id == purchase_id))
    if not p:
        return None

    lines = session.scalars(
        select(m.PurchaseLine).where(m.PurchaseLine.purchase_id == purchase_id)
    ).all()

    return {
        "purchase_id": p.purchase_id,
        "branch_id": p.branch_id,
        "vendor_id": p.vendor_id,
        "vendor_name": (
            session.scalar(select(m.Vendor.name_ar).where(m.Vendor.vendor_id == p.vendor_id))
            or "Unknown"
        ),
        "bill_date": p.bill_date.isoformat() if p.bill_date else None,
        "bill_number": p.bill_number,
        "total_gross": float(p.total_gross or 0),
        "total_discount": float(p.total_discount or 0),
        "total_net": round(float(p.total_gross or 0) - float(p.total_discount or 0) + float(p.total_tax or 0), 2),
        "total_tax": float(p.total_tax or 0),
        "is_return": p.is_return,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "lines": [
            {
                "line_id": pl.line_id,
                "product_id": pl.product_id,
                "product_name": (
                    session.scalar(select(m.Product.name_ar).where(m.Product.product_id == pl.product_id))
                    or "Unknown"
                ),
                "amount": float(pl.amount or 0),
                "bonus": float(pl.bonus or 0),
                "buy_price": float(pl.buy_price or 0),
                "sell_price": float(pl.sell_price or 0),
                "disc_money": float(pl.disc_money or 0),
                "exp_date": pl.exp_date.isoformat() if pl.exp_date else None,
            }
            for pl in lines
        ],
    }


def list_purchase_drafts(session: Session, branch_id: int | None = None, limit: int = 200) -> list[dict]:
    """Fetch purchase order drafts (auto-reorder suggestions)."""
    q = select(m.PurchaseOrderDraft).order_by(m.PurchaseOrderDraft.created_at.desc())
    if branch_id:
        q = q.where(m.PurchaseOrderDraft.branch_id == branch_id)
    rows = session.scalars(q.limit(limit)).all()
    return [
        {
            "draft_id": d.draft_id,
            "branch_id": d.branch_id,
            "product_id": d.product_id,
            "product_name": (
                session.scalar(select(m.Product.name_ar).where(m.Product.product_id == d.product_id))
                or "Unknown"
            ),
            "vendor_id": d.vendor_id,
            "vendor_name": (
                session.scalar(select(m.Vendor.name_ar).where(m.Vendor.vendor_id == d.vendor_id))
                if d.vendor_id
                else None
            ),
            "on_hand": float(d.on_hand or 0),
            "suggested_qty": float(d.suggested_qty or 0),
            "reason": d.reason,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in rows
    ]


def set_draft_status(session: Session, draft_id: int, status: str) -> dict | None:
    """Approve or reject a purchase-order draft. Approved drafts stay as the
    record of what the manager cleared to order (a human still places it with
    the vendor); rejected drafts are dismissed so reruns don't resurface them."""
    if status not in ("approved", "rejected"):
        raise ValueError("status must be 'approved' or 'rejected'")
    d = session.get(m.PurchaseOrderDraft, draft_id)
    if d is None:
        return None
    d.status = status
    session.commit()
    return {"draft_id": d.draft_id, "status": d.status}


def purchase_summary(session: Session, branch_id: int | None = None) -> dict:
    """Summary: total spent, pending POs, etc."""
    q_purchase = select(m.Purchase).where(m.Purchase.is_return == False)
    if branch_id:
        q_purchase = q_purchase.where(m.Purchase.branch_id == branch_id)

    total_spent = session.scalar(
        select(func.sum(m.Purchase.total_gross)).where(m.Purchase.is_return == False)
        if not branch_id
        else select(func.sum(m.Purchase.total_gross))
        .where(m.Purchase.branch_id == branch_id)
        .where(m.Purchase.is_return == False)
    ) or 0

    pending_drafts = session.scalar(
        select(func.count()).select_from(m.PurchaseOrderDraft)
        .where(m.PurchaseOrderDraft.status == "draft")
        if not branch_id
        else select(func.count()).select_from(m.PurchaseOrderDraft)
        .where(m.PurchaseOrderDraft.branch_id == branch_id)
        .where(m.PurchaseOrderDraft.status == "draft")
    ) or 0

    recent_count = session.scalar(
        select(func.count()).select_from(m.Purchase)
        if not branch_id
        else select(func.count()).select_from(m.Purchase).where(m.Purchase.branch_id == branch_id)
    ) or 0

    return {
        "total_spent": float(total_spent),
        "pending_drafts": int(pending_drafts),
        "total_purchases": int(recent_count),
    }


def create_purchase(
    session: Session,
    branch_id: int,
    vendor_id: int,
    lines: list[dict],
    *,
    bill_number: str | None = None,
    total_discount: float = 0.0,
    total_tax: float = 0.0,
    is_credit: bool = True,
) -> m.Purchase:
    """Receive goods — eStock's New Purchase Invoice (685 used), atomically:
    header + lines + a NEW stock batch per line (batch-level expiry/cost, so
    FEFO keeps working) + vendor balance/ledger for on-account purchases.

    Each line: {product_id, amount, buy_price, sell_price?, bonus?, exp_date?}.
    Bonus (eStock's 'bouns') adds free units to the received batch quantity.
    """
    from app.services.pos import POSError  # shared business-error type

    if not lines:
        raise POSError("empty_purchase", "لا توجد أصناف في الفاتورة / no lines")
    vendor = session.get(m.Vendor, vendor_id)
    if vendor is None or not vendor.is_active:
        raise POSError("vendor_not_found", "المورد غير موجود / vendor not found")

    try:
        gross = 0.0
        line_disc_total = 0.0
        resolved = []
        for ln in lines:
            product = session.get(m.Product, int(ln["product_id"]))
            if product is None or product.is_deleted:
                raise POSError("product_not_found", f"صنف غير موجود #{ln['product_id']}")
            amount = float(ln["amount"])
            if amount <= 0:
                raise POSError("bad_quantity", "الكمية يجب أن تكون أكبر من صفر")
            buy_price = float(ln["buy_price"])
            if buy_price < 0:
                raise POSError("bad_price", "سعر شراء غير صالح / invalid buy price")
            sell_price = float(ln.get("sell_price") or product.sell_price)
            bonus = float(ln.get("bonus") or 0)
            disc_money = float(ln.get("disc_money") or 0)
            line_gross = round(amount * buy_price, 2)
            if disc_money < 0 or disc_money > line_gross:
                raise POSError("bad_discount", "خصم السطر أكبر من قيمته / line discount exceeds its value")
            exp_date = ln.get("exp_date")  # date | None (parsed by the API layer)
            gross += line_gross
            line_disc_total += disc_money
            resolved.append((product, amount, bonus, buy_price, sell_price, disc_money, exp_date))

        net = round(gross - line_disc_total - float(total_discount) + float(total_tax), 2)
        purchase = m.Purchase(
            branch_id=branch_id,
            vendor_id=vendor_id,
            bill_date=datetime.now().date(),
            bill_number=bill_number,
            total_gross=round(gross, 2),
            # Invoice total discount = header discount + all per-line discounts,
            # so total_gross − total_discount + total_tax == net.
            total_discount=round(float(total_discount) + line_disc_total, 2),
            total_tax=float(total_tax),
        )
        session.add(purchase)
        session.flush()

        for product, amount, bonus, buy_price, sell_price, disc_money, exp_date in resolved:
            batch = m.StockBatch(
                product_id=product.product_id,
                branch_id=branch_id,
                amount=amount + bonus,  # bonus units are free stock
                buy_price=buy_price,
                sell_price=sell_price,
                exp_date=exp_date,
            )
            session.add(batch)
            session.flush()
            session.add(
                m.StockMovement(
                    batch_id=batch.batch_id,
                    branch_id=branch_id,
                    delta=amount + bonus,
                    reason="purchase",
                    ref_id=purchase.purchase_id,
                )
            )
            session.add(
                m.PurchaseLine(
                    purchase_id=purchase.purchase_id,
                    product_id=product.product_id,
                    batch_id=batch.batch_id,
                    amount=amount,
                    bonus=bonus,
                    buy_price=buy_price,
                    sell_price=sell_price,
                    disc_money=disc_money,
                    exp_date=exp_date,
                )
            )
            # Keep the product's last cost current (eStock behaviour).
            product.buy_price = buy_price

        if is_credit:
            vendor.current_balance = float(vendor.current_balance or 0) + net
        session.add(
            m.LedgerEntry(
                branch_id=branch_id,
                account_type="vendor" if is_credit else "cash",
                account_ref=vendor_id if is_credit else None,
                ref_type="purchase",
                ref_id=purchase.purchase_id,
                credit=net,
                note="فاتورة شراء / purchase invoice",
            )
        )

        session.commit()
        session.refresh(purchase)
        return purchase
    except Exception:
        session.rollback()
        raise


def create_purchase_return(
    session: Session,
    purchase_id: int,
    lines: list[dict] | None = None,
    *,
    is_credit: bool = True,
) -> m.Purchase:
    """Return goods to the vendor against a purchase invoice (eStock's
    Back_purchase_header/details), atomically:

    * quantities capped at (received − already returned) per product;
    * stock leaves the batch the purchase created (never below zero);
    * vendor balance/ledger reversed at the line's buy price.

    Each line: {product_id, amount}. ``lines=None`` returns everything still
    returnable.
    """
    from app.services.pos import POSError

    original = session.scalar(select(m.Purchase).where(m.Purchase.purchase_id == purchase_id))
    if original is None:
        raise POSError("purchase_not_found", f"فاتورة الشراء غير موجودة #{purchase_id} / purchase not found")
    if original.is_return:
        raise POSError("cannot_return_return", "لا يمكن استرجاع فاتورة مرتجع / cannot return a return invoice")

    # Received minus already returned, per product.
    received: dict[int, float] = {}
    line_by_product: dict[int, m.PurchaseLine] = {}
    for ln in original.lines:
        received[ln.product_id] = received.get(ln.product_id, 0.0) + float(ln.amount)
        line_by_product.setdefault(ln.product_id, ln)
    prior = session.scalars(
        select(m.Purchase).where(
            m.Purchase.bill_number == f"RET-{purchase_id}", m.Purchase.is_return == True  # noqa: E712
        )
    ).all()
    for ret in prior:
        for ln in ret.lines:
            received[ln.product_id] = received.get(ln.product_id, 0.0) - float(ln.amount)

    if lines is None:
        lines = [{"product_id": pid, "amount": qty} for pid, qty in received.items() if qty > 0]
    if not lines:
        raise POSError("nothing_to_return", "لا يوجد ما يمكن إرجاعه / nothing left to return")

    try:
        vendor = session.get(m.Vendor, original.vendor_id)
        total = 0.0
        resolved: list[tuple[m.PurchaseLine, float, float]] = []
        for rl in lines:
            pid = int(rl["product_id"])
            qty = float(rl["amount"])
            if qty <= 0:
                raise POSError("bad_quantity", "الكمية يجب أن تكون أكبر من صفر")
            orig_line = line_by_product.get(pid)
            if orig_line is None:
                raise POSError("product_not_on_purchase", f"الصنف #{pid} ليس على الفاتورة / not on this invoice")
            if qty > received.get(pid, 0.0) + 1e-9:
                raise POSError(
                    "return_exceeds_received",
                    f"كمية الإرجاع أكبر من المتبقي ({received.get(pid, 0.0)}) / return exceeds received quantity",
                )
            # Stock must still be there to give back.
            batch = session.get(m.StockBatch, orig_line.batch_id) if orig_line.batch_id else None
            available = float(batch.amount) if batch else 0.0
            if available + 1e-9 < qty:
                raise POSError(
                    "insufficient_stock",
                    f"المخزون الحالي ({available}) أقل من كمية الإرجاع / stock already sold — cannot return to vendor",
                )
            value = round(qty * float(orig_line.buy_price), 2)
            total += value
            resolved.append((orig_line, qty, value))

        total = round(total, 2)
        ret = m.Purchase(
            branch_id=original.branch_id,
            vendor_id=original.vendor_id,
            bill_date=datetime.now().date(),
            bill_number=f"RET-{purchase_id}",
            total_gross=total,
            is_return=True,
        )
        session.add(ret)
        session.flush()

        for orig_line, qty, value in resolved:
            batch = session.get(m.StockBatch, orig_line.batch_id)
            batch.amount = float(batch.amount) - qty
            session.add(
                m.StockMovement(
                    batch_id=batch.batch_id,
                    branch_id=original.branch_id,
                    delta=-qty,
                    reason="return",
                    ref_id=ret.purchase_id,
                )
            )
            session.add(
                m.PurchaseLine(
                    purchase_id=ret.purchase_id,
                    product_id=orig_line.product_id,
                    batch_id=batch.batch_id,
                    amount=qty,
                    buy_price=orig_line.buy_price,
                    sell_price=orig_line.sell_price,
                    exp_date=orig_line.exp_date,
                )
            )

        if is_credit and vendor is not None:
            vendor.current_balance = float(vendor.current_balance or 0) - total
        session.add(
            m.LedgerEntry(
                branch_id=original.branch_id,
                account_type="vendor" if is_credit else "cash",
                account_ref=original.vendor_id if is_credit else None,
                ref_type="purchase_return",
                ref_id=ret.purchase_id,
                debit=total,
                note="مرتجع شراء / purchase return",
            )
        )

        session.commit()
        session.refresh(ret)
        return ret
    except Exception:
        session.rollback()
        raise
