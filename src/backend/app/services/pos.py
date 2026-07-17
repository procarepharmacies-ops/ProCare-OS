"""POS / write-path service — the Phase-2 hot-path logic.

eStock had ZERO stored procedures: all business logic was locked in the .exe.
ProCare moves the hot paths into tested, atomic functions here (the Python
equivalents of the ``sp_*`` procedures sketched in ``sql/procare-schema.sql``):

  * ``check_credit``    — sp_check_credit: enforce the customer credit limit.
  * ``deduct_stock_fefo`` — sp_deduct_stock: FEFO, never goes negative.
  * ``create_sale``     — sp_create_sale: atomic invoice (header + lines +
                          stock movements + ledger), credit-checked, expiry-locked.
  * ``transfer_stock``  — sp_transfer_stock: atomic Elsanta <-> Mas-hala move.

Guardrails baked in (fixing the eStock issues named in the docs):
  * a sale that would exceed the credit limit needs an explicit override by an
    employee with ``can_sale_credit`` (fixes 61 over-limit customers);
  * expired-only product is blocked from sale (fixes 74 expired-but-sellable);
  * stock can never go negative (CK_stock_amount; fixes 33,249 zero/neg batches);
  * everything in one sale is one transaction — any failure rolls the lot back.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services import loyalty as loyalty_svc
from app.services.common import money, today


def _parse_date(value) -> date | None:
    """Accept an ISO 'YYYY-MM-DD' string (or a date/datetime) and return a date."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


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
            (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > today()),  # noqa: E711
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
    redeem_points: float = 0.0,
) -> m.Sale:
    """Create one atomic invoice. Commits on success; rolls back on any failure.

    ``redeem_points`` spends that many loyalty points as an extra invoice
    discount (requires a customer; capped at the invoice value)."""
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

        # Loyalty redemption = extra discount, validated + deducted atomically
        # with the sale.
        redeem_value = 0.0
        redeem_tx = None
        if redeem_points and redeem_points > 0:
            if customer_id is None:
                raise POSError("redeem_needs_customer", "استبدال النقاط يتطلب عميلاً / redemption needs a customer")
            try:
                redeem_value, redeem_tx = loyalty_svc.redeem_on_sale(session, customer_id, redeem_points)
            except loyalty_svc.LoyaltyError as e:
                raise POSError(e.code, e.message)
            redeem_value = min(redeem_value, net)  # discount can't exceed the invoice
            total_disc = round(total_disc + redeem_value, 2)
            net = round(net - redeem_value, 2)

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
        if redeem_tx is not None:
            redeem_tx.sale_id = sale.sale_id

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

        # Loyalty: earn points on the final net (same transaction).
        loyalty_svc.award_for_sale(session, sale)

        session.commit()
        session.refresh(sale)
        return sale
    except Exception:
        session.rollback()
        raise


# --- sp_return_sale ---------------------------------------------------------
@dataclass
class ReturnLineInput:
    product_id: int
    amount: float


def returnable_quantities(session: Session, sale: m.Sale) -> dict[int, float]:
    """Per product: quantity sold on this invoice minus quantity already
    returned against it (across all prior return invoices)."""
    sold: dict[int, float] = {}
    for ln in sale.lines:
        sold[ln.product_id] = sold.get(ln.product_id, 0.0) + float(ln.amount)
    prior_returns = session.scalars(
        select(m.Sale).where(m.Sale.original_sale_id == sale.sale_id, m.Sale.is_return == True)  # noqa: E712
    ).all()
    for ret in prior_returns:
        for ln in ret.lines:
            sold[ln.product_id] = sold.get(ln.product_id, 0.0) - float(ln.amount)
    return sold


def return_sale(
    session: Session,
    sale_id: int,
    lines: list[ReturnLineInput] | None = None,
    *,
    cashier_id: int | None = None,
) -> m.Sale:
    """Create one atomic return invoice against an existing sale (eStock's
    Back_sales_header/details, which it used 4,359 times).

    * quantities are capped at (sold - already returned) per product;
    * refund per unit is the NET price actually paid (after line discount);
    * stock goes back to the original batch when it still exists, else a new
      batch at the line's cost/sell price;
    * cash refund is a ledger credit; a credit-sale return also reduces the
      customer's outstanding balance.

    ``lines=None`` returns everything still returnable on the invoice.
    """
    original = session.get(m.Sale, sale_id)
    if original is None:
        raise POSError("sale_not_found", f"الفاتورة غير موجودة #{sale_id} / sale not found")
    if original.is_return:
        raise POSError("cannot_return_return", "لا يمكن استرجاع فاتورة استرجاع / cannot return a return invoice")

    remaining = returnable_quantities(session, original)
    # Net unit price + costs come from the original lines (first line per product).
    line_by_product: dict[int, m.SaleLine] = {}
    for ln in original.lines:
        line_by_product.setdefault(ln.product_id, ln)

    if lines is None:
        lines = [ReturnLineInput(pid, qty) for pid, qty in remaining.items() if qty > 0]
    if not lines:
        raise POSError("nothing_to_return", "لا يوجد ما يمكن استرجاعه / nothing left to return")

    try:
        total_refund = 0.0
        resolved: list[tuple[m.SaleLine, float, float]] = []  # (orig line, qty, refund)
        for rl in lines:
            if rl.amount <= 0:
                raise POSError("bad_quantity", "الكمية يجب أن تكون أكبر من صفر")
            orig_line = line_by_product.get(rl.product_id)
            if orig_line is None:
                raise POSError("product_not_on_sale", f"الصنف #{rl.product_id} ليس على الفاتورة / not on this invoice")
            if rl.amount > remaining.get(rl.product_id, 0.0) + 1e-9:
                raise POSError(
                    "return_exceeds_sold",
                    f"كمية الاسترجاع أكبر من المتبقي ({money(remaining.get(rl.product_id, 0.0))}) "
                    f"/ return exceeds returnable quantity",
                )
            unit_net = float(orig_line.total_sell) / float(orig_line.amount)
            refund = round(unit_net * float(rl.amount), 2)
            total_refund += refund
            resolved.append((orig_line, float(rl.amount), refund))

        total_refund = round(total_refund, 2)
        ret = m.Sale(
            branch_id=original.branch_id,
            customer_id=original.customer_id,
            cashier_id=cashier_id,
            sale_date=datetime.now(),
            total_gross=total_refund,
            total_discount=0.0,
            total_net=total_refund,
            is_return=True,
            is_credit=original.is_credit,
            original_sale_id=original.sale_id,
        )
        session.add(ret)
        session.flush()

        for orig_line, qty, refund in resolved:
            # Restock: back into the original batch if it still exists,
            # otherwise a new batch carrying the line's cost/sell price.
            batch = session.get(m.StockBatch, orig_line.batch_id) if orig_line.batch_id else None
            if batch is None or batch.branch_id != original.branch_id:
                batch = m.StockBatch(
                    product_id=orig_line.product_id,
                    branch_id=original.branch_id,
                    amount=0,
                    buy_price=orig_line.buy_price,
                    sell_price=orig_line.sell_price,
                )
                session.add(batch)
                session.flush()
            batch.amount = float(batch.amount) + qty
            session.add(
                m.StockMovement(
                    batch_id=batch.batch_id,
                    branch_id=original.branch_id,
                    delta=qty,
                    reason="return",
                    ref_id=ret.sale_id,
                    employee_id=cashier_id,
                )
            )
            session.add(
                m.SaleLine(
                    sale_id=ret.sale_id,
                    product_id=orig_line.product_id,
                    batch_id=batch.batch_id,
                    amount=qty,
                    sell_price=orig_line.sell_price,
                    buy_price=orig_line.buy_price,
                    total_sell=refund,
                    is_return=True,
                )
            )

        if original.is_credit and original.customer_id is not None:
            customer = session.get(m.Customer, original.customer_id)
            customer.current_balance = float(customer.current_balance or 0) - total_refund
            session.add(
                m.LedgerEntry(
                    branch_id=original.branch_id,
                    account_type="customer",
                    account_ref=original.customer_id,
                    ref_type="sale_return",
                    ref_id=ret.sale_id,
                    credit=total_refund,
                    note="مرتجع بيع آجل / credit sale return",
                )
            )
        else:
            session.add(
                m.LedgerEntry(
                    branch_id=original.branch_id,
                    account_type="cash",
                    ref_type="sale_return",
                    ref_id=ret.sale_id,
                    credit=total_refund,
                    note="مرتجع بيع نقدي / cash sale return (refund)",
                )
            )

        # Loyalty: claw back the points the refunded amount had earned.
        loyalty_svc.clawback_for_return(session, ret)

        session.commit()
        session.refresh(ret)
        return ret
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
        _move_transfer_lines(session, transfer, lines, actor=requested_by)
        session.commit()
        session.refresh(transfer)
        return transfer
    except Exception:
        session.rollback()
        raise


def _move_transfer_lines(session: Session, transfer: m.StockTransfer, lines, actor: int | None) -> None:
    """FEFO-move each (product_id, amount) line from the transfer's source branch
    to its destination, recording two stock movements + a detailed transfer line
    per hit batch. Shared by the immediate transfer and the approve-request path."""
    from_branch_id = transfer.from_branch_id
    to_branch_id = transfer.to_branch_id
    for ln in lines:
        # Decrement the source FEFO; each hit batch's expiry travels along.
        src_batches = session.scalars(
            select(m.StockBatch)
            .where(
                m.StockBatch.product_id == ln.product_id,
                m.StockBatch.branch_id == from_branch_id,
                m.StockBatch.amount > 0,
                (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > today()),  # noqa: E711
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
                    reason="transfer_out", ref_id=transfer.transfer_id, employee_id=actor,
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
                    reason="transfer_in", ref_id=transfer.transfer_id, employee_id=actor,
                )
            )
            session.add(
                m.StockTransferLine(
                    transfer_id=transfer.transfer_id, product_id=ln.product_id,
                    from_batch_id=src.batch_id, to_batch_id=dst.batch_id,
                    amount=take, buy_price=src.buy_price, exp_date=src.exp_date,
                )
            )


def request_transfer(
    session: Session,
    from_branch_id: int,
    to_branch_id: int,
    lines: list[SaleLineInput],
    *,
    requested_by: int | None = None,
) -> m.StockTransfer:
    """Record a transfer REQUEST (status='requested') without moving any stock —
    a manager approves it later. Lines store product_id + amount only (batches
    are picked at approval time). Validates source availability up front so an
    impossible request is rejected immediately."""
    if from_branch_id == to_branch_id:
        raise POSError("same_branch", "لا يمكن التحويل لنفس الفرع / cannot transfer to the same branch")
    if not lines:
        raise POSError("empty_transfer", "لا توجد أصناف للتحويل / no lines to transfer")
    try:
        transfer = m.StockTransfer(
            from_branch_id=from_branch_id,
            to_branch_id=to_branch_id,
            status="requested",
            requested_by=requested_by,
        )
        session.add(transfer)
        session.flush()
        for ln in lines:
            if ln.amount <= 0:
                continue
            session.add(
                m.StockTransferLine(
                    transfer_id=transfer.transfer_id,
                    product_id=ln.product_id,
                    amount=float(ln.amount),
                )
            )
        session.commit()
        session.refresh(transfer)
        return transfer
    except Exception:
        session.rollback()
        raise


def approve_transfer(session: Session, transfer_id: int, *, approved_by: int | None = None) -> m.StockTransfer:
    """Approve a requested transfer: execute the FEFO stock move now and mark it
    received. Idempotency-guarded — only a 'requested' transfer can be approved."""
    transfer = session.get(m.StockTransfer, transfer_id)
    if transfer is None:
        raise POSError("not_found", "طلب التحويل غير موجود / transfer request not found")
    if transfer.status != "requested":
        raise POSError("bad_status", f"لا يمكن اعتماد تحويل حالته {transfer.status}")
    # The requested lines carry (product_id, amount); replace them with the
    # detailed, batch-linked lines the move produces.
    requested = [SaleLineInput(product_id=l.product_id, amount=float(l.amount)) for l in transfer.lines]
    try:
        for l in list(transfer.lines):
            session.delete(l)
        session.flush()
        transfer.status = "received"
        transfer.shipped_at = datetime.now()
        transfer.received_at = datetime.now()
        _move_transfer_lines(session, transfer, requested, actor=approved_by)
        session.commit()
        session.refresh(transfer)
        return transfer
    except Exception:
        session.rollback()
        raise


def reject_transfer(session: Session, transfer_id: int) -> m.StockTransfer:
    """Reject a requested transfer (status -> cancelled). No stock moves."""
    transfer = session.get(m.StockTransfer, transfer_id)
    if transfer is None:
        raise POSError("not_found", "طلب التحويل غير موجود / transfer request not found")
    if transfer.status != "requested":
        raise POSError("bad_status", f"لا يمكن رفض تحويل حالته {transfer.status}")
    transfer.status = "cancelled"
    session.commit()
    session.refresh(transfer)
    return transfer


def _ship_transfer_lines(session: Session, transfer: m.StockTransfer, lines, actor: int | None) -> None:
    """OUT side only: FEFO-decrement the source and record transfer_out. Each hit
    batch becomes a transfer line carrying its expiry + cost (to_batch_id stays
    NULL — the goods are in transit, not yet in destination stock)."""
    from_branch_id = transfer.from_branch_id
    for ln in lines:
        src_batches = session.scalars(
            select(m.StockBatch)
            .where(
                m.StockBatch.product_id == ln.product_id,
                m.StockBatch.branch_id == from_branch_id,
                m.StockBatch.amount > 0,
                (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > today()),  # noqa: E711
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
                    reason="transfer_out", ref_id=transfer.transfer_id, employee_id=actor,
                )
            )
            session.add(
                m.StockTransferLine(
                    transfer_id=transfer.transfer_id, product_id=ln.product_id,
                    from_batch_id=src.batch_id, to_batch_id=None,
                    amount=take, buy_price=src.buy_price, exp_date=src.exp_date,
                )
            )


def ship_transfer(session: Session, transfer_id: int, *, shipped_by: int | None = None) -> m.StockTransfer:
    """Two-phase step 1 (صرف/شحن): the source releases the goods. Stock leaves
    the source now (transfer_out); it is NOT yet in destination stock — the
    destination must confirm receipt (expiry + quantity) to complete it."""
    transfer = session.get(m.StockTransfer, transfer_id)
    if transfer is None:
        raise POSError("not_found", "طلب التحويل غير موجود / transfer request not found")
    if transfer.status != "requested":
        raise POSError("bad_status", f"لا يمكن شحن تحويل حالته {transfer.status}")
    requested = [SaleLineInput(product_id=l.product_id, amount=float(l.amount)) for l in transfer.lines]
    try:
        for l in list(transfer.lines):
            session.delete(l)
        session.flush()
        transfer.status = "in_transit"
        transfer.shipped_at = datetime.now()
        _ship_transfer_lines(session, transfer, requested, actor=shipped_by)
        session.commit()
        session.refresh(transfer)
        return transfer
    except Exception:
        session.rollback()
        raise


def receive_transfer(
    session: Session,
    transfer_id: int,
    confirmations: dict | None = None,
    *,
    received_by: int | None = None,
) -> m.StockTransfer:
    """Two-phase step 2 (استلام الإذن): the destination reviews the in-transit
    lines, confirms/corrects each line's received quantity and expiry date, and
    only then does the stock enter destination inventory (transfer_in). A short
    receipt (breakage in transit) simply adds less than was shipped — the
    difference is visible in the movement ledger as shrinkage.

    ``confirmations``: ``{line_id: {"amount": float, "exp_date": "YYYY-MM-DD"}}``.
    Missing lines default to the shipped amount + expiry (accept as sent).
    """
    transfer = session.get(m.StockTransfer, transfer_id)
    if transfer is None:
        raise POSError("not_found", "طلب التحويل غير موجود / transfer request not found")
    if transfer.status != "in_transit":
        raise POSError("bad_status", f"لا يمكن استلام تحويل حالته {transfer.status}")
    confirmations = confirmations or {}
    # Product sell prices for the new destination batches (destination sells at
    # its own catalogue price).
    prod_ids = {l.product_id for l in transfer.lines}
    sell_prices = dict(
        session.execute(
            select(m.Product.product_id, m.Product.sell_price).where(m.Product.product_id.in_(prod_ids))
        ).all()
    ) if prod_ids else {}
    try:
        for line in transfer.lines:
            conf = confirmations.get(line.line_id) or confirmations.get(str(line.line_id)) or {}
            recv_amount = float(conf.get("amount", line.amount))
            if recv_amount < 0:
                raise POSError("bad_quantity", "الكمية لا يمكن أن تكون سالبة / amount cannot be negative")
            exp = conf.get("exp_date", None)
            exp_date = _parse_date(exp) if exp else line.exp_date
            if recv_amount <= 0:
                # Nothing arrived for this line (fully lost in transit) — leave
                # the shipped record, create no destination batch.
                continue
            dst = m.StockBatch(
                product_id=line.product_id, branch_id=transfer.to_branch_id,
                amount=recv_amount, buy_price=line.buy_price,
                sell_price=float(sell_prices.get(line.product_id, 0) or 0),
                exp_date=exp_date,
            )
            session.add(dst)
            session.flush()
            line.to_batch_id = dst.batch_id
            line.amount = recv_amount  # what was actually received
            line.exp_date = exp_date
            session.add(
                m.StockMovement(
                    batch_id=dst.batch_id, branch_id=transfer.to_branch_id, delta=recv_amount,
                    reason="transfer_in", ref_id=transfer.transfer_id, employee_id=received_by,
                )
            )
        transfer.status = "received"
        transfer.received_at = datetime.now()
        session.commit()
        session.refresh(transfer)
        return transfer
    except Exception:
        session.rollback()
        raise
