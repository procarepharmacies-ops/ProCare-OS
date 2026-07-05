"""POS write-path endpoints: create a sale, list recent sales, transfer stock.

These exercise the Phase-2 hot-path services (``app.services.pos``) with their
guardrails: FEFO deduction, credit-limit enforcement, expired-stock lock, atomic
all-or-nothing transactions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.db.base import get_session
from app.services import pos
from app.services.common import money

router = APIRouter(prefix="/sales", tags=["sales"])


class LineIn(BaseModel):
    product_id: int
    amount: float = Field(gt=0)
    sell_price: float | None = None
    disc_money: float = 0.0


class SaleIn(BaseModel):
    branch_id: int
    lines: list[LineIn]
    customer_id: int | None = None
    cashier_id: int | None = None
    is_credit: bool = False
    cash_paid: float | None = None
    card_paid: float = 0.0
    override_by: int | None = None
    # Loyalty: spend this many points as an extra invoice discount.
    redeem_points: float = 0.0


class TransferIn(BaseModel):
    from_branch_id: int
    to_branch_id: int
    lines: list[LineIn]
    requested_by: int | None = None


@router.post("")
def create_sale(payload: SaleIn, session: Session = Depends(get_session)):
    try:
        sale = pos.create_sale(
            session,
            branch_id=payload.branch_id,
            lines=[pos.SaleLineInput(l.product_id, l.amount, l.sell_price, l.disc_money) for l in payload.lines],
            customer_id=payload.customer_id,
            cashier_id=payload.cashier_id,
            is_credit=payload.is_credit,
            cash_paid=payload.cash_paid,
            card_paid=payload.card_paid,
            override_by=payload.override_by,
            redeem_points=payload.redeem_points,
        )
    except pos.POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
    out = {
        "sale_id": sale.sale_id,
        "branch_id": sale.branch_id,
        "total_net": money(sale.total_net),
        "is_credit": sale.is_credit,
        "sale_date": sale.sale_date.isoformat(),
    }
    # CRM extras for the POS receipt screen: points balance + WhatsApp invoice.
    if sale.customer_id:
        from app.services import whatsapp as wa

        customer = session.get(m.Customer, sale.customer_id)
        out["loyalty_points"] = money(customer.loyalty_points or 0)
        text = wa.invoice_message(session, sale)
        out["whatsapp_link"] = wa.wa_link(customer.mobile, text)
        out["whatsapp_sent"] = wa.send_text(customer.mobile, text) if wa.is_configured() else False
    return out


@router.post("/transfer")
def transfer(payload: TransferIn, session: Session = Depends(get_session)):
    try:
        t = pos.transfer_stock(
            session,
            payload.from_branch_id,
            payload.to_branch_id,
            [pos.SaleLineInput(l.product_id, l.amount) for l in payload.lines],
            requested_by=payload.requested_by,
        )
    except pos.POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
    return {"transfer_id": t.transfer_id, "status": t.status, "lines": len(t.lines)}


class ReturnLineIn(BaseModel):
    product_id: int
    amount: float = Field(gt=0)


class ReturnIn(BaseModel):
    lines: list[ReturnLineIn] | None = None  # None => full return of what remains
    cashier_id: int | None = None


@router.get("/{sale_id}/returnable")
def returnable(sale_id: int, session: Session = Depends(get_session)):
    """The invoice with, per product, how much can still be returned — feeds
    the POS return picker (eStock flow: open old invoice -> mark return lines)."""
    sale = session.get(m.Sale, sale_id)
    if sale is None or sale.is_return:
        raise HTTPException(status_code=404, detail="sale not found")
    remaining = pos.returnable_quantities(session, sale)
    lines = []
    for ln in sale.lines:
        lines.append(
            {
                "product_id": ln.product_id,
                "name_ar": ln.product.name_ar,
                "name_en": ln.product.name_en,
                "sold": money(ln.amount),
                "returnable": money(max(remaining.get(ln.product_id, 0.0), 0.0)),
                "unit_net_price": money(float(ln.total_sell) / float(ln.amount)),
            }
        )
    return {
        "sale_id": sale.sale_id,
        "branch_id": sale.branch_id,
        "sale_date": sale.sale_date.isoformat(),
        "total_net": money(sale.total_net),
        "is_credit": sale.is_credit,
        "customer": sale.customer.name_ar if sale.customer else None,
        "lines": lines,
    }


@router.post("/{sale_id}/return")
def return_sale(sale_id: int, payload: ReturnIn, session: Session = Depends(get_session)):
    try:
        ret = pos.return_sale(
            session,
            sale_id,
            [pos.ReturnLineInput(l.product_id, l.amount) for l in payload.lines] if payload.lines else None,
            cashier_id=payload.cashier_id,
        )
    except pos.POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})
    return {
        "return_id": ret.sale_id,
        "original_sale_id": ret.original_sale_id,
        "total_refund": money(ret.total_net),
        "lines": len(ret.lines),
    }


@router.get("/recent")
def recent(branch_id: int | None = None, limit: int = 20, session: Session = Depends(get_session)):
    stmt = select(m.Sale).order_by(desc(m.Sale.sale_date)).limit(limit)
    if branch_id:
        stmt = stmt.where(m.Sale.branch_id == branch_id)
    out = []
    for s in session.scalars(stmt):
        # Owner rule: every invoice carries its discount AND its profit, so
        # management can see what there is room to change.
        profit = sum(float(l.total_sell) - float(l.amount) * float(l.buy_price) for l in s.lines)
        out.append(
            {
                "sale_id": s.sale_id,
                "branch_id": s.branch_id,
                "sale_date": s.sale_date.isoformat(),
                "total_net": money(s.total_net),
                "total_discount": money(s.total_discount),
                "profit": money(-profit if s.is_return else profit),
                "is_credit": s.is_credit,
                "is_return": s.is_return,
                "customer": s.customer.name_ar if s.customer else None,
                "lines": len(s.lines),
            }
        )
    return {"sales": out}


@router.get("/{sale_id}")
def sale_detail(sale_id: int, session: Session = Depends(get_session)):
    """Full invoice — header, lines, discount and profit per line and overall.
    Feeds the invoice drill-down and the printable receipt."""
    s = session.get(m.Sale, sale_id)
    if s is None:
        raise HTTPException(status_code=404, detail="sale not found")
    branch = session.get(m.Branch, s.branch_id)
    cashier = session.get(m.Employee, s.cashier_id) if s.cashier_id else None
    lines = []
    total_profit = 0.0
    for ln in s.lines:
        line_profit = float(ln.total_sell) - float(ln.amount) * float(ln.buy_price)
        total_profit += line_profit
        lines.append(
            {
                "product_id": ln.product_id,
                "name_ar": ln.product.name_ar,
                "name_en": ln.product.name_en,
                "code": ln.product.code,
                "amount": money(ln.amount),
                "sell_price": money(ln.sell_price),
                "disc_money": money(ln.disc_money),
                "total_sell": money(ln.total_sell),
                "profit": money(line_profit),
            }
        )
    return {
        "sale_id": s.sale_id,
        "branch_id": s.branch_id,
        "branch_name_ar": branch.name_ar if branch else None,
        "branch_name_en": branch.name_en if branch else None,
        "sale_date": s.sale_date.isoformat(),
        "customer": s.customer.name_ar if s.customer else None,
        "customer_id": s.customer_id,
        "cashier": cashier.name_ar if cashier else None,
        "is_credit": s.is_credit,
        "is_return": s.is_return,
        "original_sale_id": s.original_sale_id,
        "total_gross": money(s.total_gross),
        "total_discount": money(s.total_discount),
        "total_net": money(s.total_net),
        "cash_paid": money(s.cash_paid),
        "card_paid": money(s.card_paid),
        "profit": money(-total_profit if s.is_return else total_profit),
        "lines": lines,
    }
