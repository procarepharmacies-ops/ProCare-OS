"""POS / write-path service — the Phase-2 hot-path logic.

eStock had ZERO stored procedures: all business logic was locked in the .exe.
ProCare moves the hot paths into tested, atomic functions here (the Python
equivalents of the ``sp_*`` procedures sketched in ``sql/procare-schema.sql``):

  * ``check_credit``    — sp_check_credit: enforce the customer credit limit.
  * ``deduct_stock_fefo`` — sp_deduct_stock: FEFO, never goes negative.
  * ``create_sale``     — sp_create_sale: atomic invoice (header + lines +
                          stock movements + ledger), credit-checked, expiry-locked.
  * ``transfer_stock``  — sp_transfer_stock: atomic Main <-> Elsanta move.

Guardrails baked in (fixing the eStock issues named in the docs):
  * a sale that would exceed the credit limit needs an explicit override by an
    employee with ``can_sale_credit`` (fixes 61 over-limit customers);
  * expired-only product is blocked from sale (fixes 74 expired-but-sellable);
  * stock can never go negative (CK_stock_amount; fixes 33,249 zero/neg batches);
  * everything in one sale is one transaction — any failure rolls the lot back.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import TODAY, money


class POSError(Exception):
    """Business-rule violation at the POS (credit, stock, expiry...)."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass
class SaleLineInput:
    product_id: int
    amount: float
    sell_price: float | None = None  # None => use product default
    disc_money: float = 0.0


# --- sp_check_credit --------------------------------------------------------
def check_credit(session: Session, customer_id: int, new_charge: float, override_by: int | None = None) -> None:
    """Raise POSError unless the on-account charge fits the credit limit or an
    authorised employee (``can_sale_credit``) explicitly overrides."""
    customer = session.get(m.Customer, customer_id)
    if customer is None:
        raise POSError("customer_not_found", "العميل غير موجود / customer not found")
    limit = float(customer.credit_limit or 0)
    if limit <= 0:
        return  # no limit configured => unlimited account
    projected = float(customer.current_balance or 0) + float(new_charge)
    if projected <= limit:
        return
    # Over the limit — only an authorised override gets through.
    if override_by is not None:
        emp = session.get(m.Employee, override_by)
        if emp and emp.can_sale_credit:
            return
    raise POSError(
        "credit_limit_exceeded",
        f"تجاوز حد الائتمان: الرصيد المتوقع {money(projected)} > الحد {money(limit)} "
        f"/ credit limit exceeded (needs override)",
    )


# --- sp_deduct_stock (FEFO) -------------------------------------------------
def deduct_stock_fefo(
    session: Session,
    product_id: int,
    branch_id: int,
    qty: float,
    *,
    ref_id: int | None,
    employee_id: int | None,
    reason: str = "sale",
) -> list[tuple[int, float]]:
    """Walk live batches first-expire-first and decrement them to cover ``qty``.

    Returns the list of (batch_id, qty_taken). Raises if there isn't enough
    sellable (non-expired) stock — so an expired-only product cannot be sold.
    """
    batches = session.scalars(
        select(m.StockBatch)
        .where(
            m.StockBatch.product_id == product_id,
            m.StockBatch.branch_id == branch_id,
            m.StockBatch.amount > 0,
            (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > TODAY),  # noqa: E711
        )
        .order_by(m.StockBatch.exp_date.asc().nulls_last())
    ).all()

    available = sum(float(b.amount) for b in batches)
    if available < qty:
        raise POSError(
            "insufficient_stock",
            f"مخزون غير كافٍ: متاح {money(available)} مطلوب {money(qty)} "
            f"/ insufficient sellable stock",
        )

    remaining = float(qty)
    taken: list[tuple[int, float]] = []
    for batch in batches:
        if remaining <= 0:
            break
        take = min(float(batch.amount), remaining)
        batch.amount = float(batch.amount) - take
        remaining -= take
        session.add(
            m.StockMovement(
                batch_id=batch.batch_id,
                branch_id=branch_id,
                delta=-take,
                reason=reason,
                ref_id=ref_id,
                employee_id=employee_id,
            )
        )
        taken.append((batch.batch_id, take))
    return taken


# --- sp_create_sale ---------------------------------------------------------
def create_sale(
    session: Session,
    branch_id: int,
    lines: list[SaleLineInput],
    *,
    customer_id: int | None = None,
    cashier_id: int | None = None,
    is_credit: bool = False,
    cash_paid: float | None = None,
    card_paid: float = 0.0,
    override_by: int | None = None,
) -> m.Sale:
    """Create one atomic invoice. Commits on success; rolls back on any failure."""
    if not lines:
        raise POSError("empty_sale", "لا توجد أصناف في الفاتورة / no lines in sale")

    try:
        # Resolve prices and compute totals up front (also validates products).
        resolved = []
        gross = 0.0
        total_disc = 0.0
        for ln in lines:
            product = session.get(m.Product, ln.product_id)
            if product is None or product.is_deleted:
                raise POSError("product_not_found", f"صنف غير موجود #{ln.product_id}")
            if ln.amount <= 0:
                raise POSError("bad_quantity", "الكمية يجب أن تكون أكبر من صفر")
            price = float(ln.sell_price) if ln.sell_price is not None else float(product.sell_price)
            line_total = round(price * float(ln.amount) - float(ln.disc_money), 2)
            if line_total < 0:
                raise POSError("bad_discount", "الخصم أكبر من قيمة الصنف")
            gross += round(price * float(ln.amount), 2)
            total_disc += float(ln.disc_money)
            resolved.append((product, ln, price, line_total))

        net = round(gross - total_disc, 2)

        # Credit check BEFORE touching stock (fail fast, atomic intent).
        if is_credit:
            if customer_id is None:
                raise POSError("credit_needs_customer", "البيع الآجل يتطلب عميلاً / credit sale needs a customer")
            check_credit(session, customer_id, net, override_by=override_by)

        sale = m.Sale(
            branch_id=branch_id,
            customer_id=customer_id,
            cashier_id=cashier_id,
            sale_date=datetime.now(),
            total_gross=round(gross, 2),
            total_discount=round(total_disc, 2),
            total_net=net,
            is_credit=is_credit,
            cash_paid=0.0 if is_credit else (net if cash_paid is None else cash_paid),
            card_paid=card_paid,
        )
        session.add(sale)
        session.flush()  # assign sale_id

        for product, ln, price, line_total in resolved:
            # FEFO deduction (skips expired => expired-only product is blocked).
            taken = deduct_stock_fefo(
                session,
                product.product_id,
                branch_id,
                float(ln.amount),
                ref_id=sale.sale_id,
                employee_id=cashier_id,
            )
            primary_batch = taken[0][0] if taken else None
            session.add(
                m.SaleLine(
                    sale_id=sale.sale_id,
                    product_id=product.product_id,
                    batch_id=primary_batch,
                    amount=float(ln.amount),
                    sell_price=price,
                    buy_price=float(product.buy_price),
                    disc_money=float(ln.disc_money),
                    total_sell=line_total,
                )
            )

        # Ledger + customer balance for on-account sales.
        if is_credit and customer_id is not None:
            customer = session.get(m.Customer, customer_id)
            customer.current_balance = float(customer.current_balance or 0) + net
            session.add(
                m.LedgerEntry(
                    branch_id=branch_id,
                    account_type="customer",
                    account_ref=customer_id,
                    ref_type="sale",
                    ref_id=sale.sale_id,
                    debit=net,
                    note="بيع آجل / credit sale",
                )
            )
        else:
            session.add(
                m.LedgerEntry(
                    branch_id=branch_id,
                    account_type="cash",
                    ref_type="sale",
                    ref_id=sale.sale_id,
                    debit=net,
                    note="بيع نقدي / cash sale",
                )
            )

        session.commit()
        session.refresh(sale)
        return sale
    except Exception:
        session.rollback()
        raise


# --- sp_transfer_stock ------------------------------------------------------
def transfer_stock(
    session: Session,
    from_branch_id: int,
    to_branch_id: int,
    lines: list[SaleLineInput],
    *,
    requested_by: int | None = None,
) -> m.StockTransfer:
    """Atomic inter-branch move: FEFO-decrement source, create matching
    destination batches carrying the SAME expiry + cost, two stock movements
    per line under one transfer_id. All-or-nothing."""
    if from_branch_id == to_branch_id:
        raise POSError("same_branch", "لا يمكن التحويل لنفس الفرع / cannot transfer to the same branch")
    if not lines:
        raise POSError("empty_transfer", "لا توجد أصناف للتحويل / no lines to transfer")

    try:
        transfer = m.StockTransfer(
            from_branch_id=from_branch_id,
            to_branch_id=to_branch_id,
            status="received",
            requested_by=requested_by,
            shipped_at=datetime.now(),
            received_at=datetime.now(),
        )
        session.add(transfer)
        session.flush()

        for ln in lines:
            # Decrement the source FEFO; each hit batch's expiry travels along.
            src_batches = session.scalars(
                select(m.StockBatch)
                .where(
                    m.StockBatch.product_id == ln.product_id,
                    m.StockBatch.branch_id == from_branch_id,
                    m.StockBatch.amount > 0,
                    (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > TODAY),  # noqa: E711
                )
                .order_by(m.StockBatch.exp_date.asc().nulls_last())
            ).all()
            available = sum(float(b.amount) for b in src_batches)
            if available < ln.amount:
                raise POSError(
                    "insufficient_stock",
                    f"مخزون غير كافٍ للتحويل: متاح {money(available)} مطلوب {money(ln.amount)}",
                )
            remaining = float(ln.amount)
            for src in src_batches:
                if remaining <= 0:
                    break
                take = min(float(src.amount), remaining)
                src.amount = float(src.amount) - take
                remaining -= take
                session.add(
                    m.StockMovement(
                        batch_id=src.batch_id, branch_id=from_branch_id, delta=-take,
                        reason="transfer_out", ref_id=transfer.transfer_id, employee_id=requested_by,
                    )
                )
                # Destination batch mirrors expiry + cost so FEFO stays correct.
                dst = m.StockBatch(
                    product_id=ln.product_id, branch_id=to_branch_id, amount=take,
                    buy_price=src.buy_price, sell_price=src.sell_price, exp_date=src.exp_date,
                )
                session.add(dst)
                session.flush()
                session.add(
                    m.StockMovement(
                        batch_id=dst.batch_id, branch_id=to_branch_id, delta=take,
                        reason="transfer_in", ref_id=transfer.transfer_id, employee_id=requested_by,
                    )
                )
                session.add(
                    m.StockTransferLine(
                        transfer_id=transfer.transfer_id, product_id=ln.product_id,
                        from_batch_id=src.batch_id, to_batch_id=dst.batch_id,
                        amount=take, buy_price=src.buy_price, exp_date=src.exp_date,
                    )
                )

        session.commit()
        session.refresh(transfer)
        return transfer
    except Exception:
        session.rollback()
        raise
