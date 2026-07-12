"""Inventory / catalogue read service.

Product list with on-hand stock, and per-product FEFO batch lookup. "Available"
stock follows the data-quality rule (positive and not expired).
"""
from __future__ import annotations

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import TODAY, available_stock_filter, branch_filter, money


def list_products(
    session: Session,
    branch_id: int | None = None,
    search: str | None = None,
    limit: int = 100,
    *,
    dosage_form: str | None = None,
    otc: bool | None = None,
    scientific: str | None = None,
    location: str | None = None,
    sort: str | None = None,  # name (default) | price_asc | price_desc
) -> list[dict]:
    on_hand = (
        select(
            m.StockBatch.product_id.label("pid"),
            func.sum(m.StockBatch.amount).label("qty"),
        )
        .where(available_stock_filter(), branch_filter(m.StockBatch, branch_id))
        .group_by(m.StockBatch.product_id)
        .subquery()
    )
    stmt = (
        select(m.Product, func.coalesce(on_hand.c.qty, 0).label("on_hand"))
        .join(on_hand, on_hand.c.pid == m.Product.product_id, isouter=True)
        .where(m.Product.is_deleted == False)  # noqa: E712
    )
    # Classification filters (الفلترة): every axis the pharmacist thinks in.
    if dosage_form:
        stmt = stmt.where(m.Product.dosage_form == dosage_form)
    if otc is not None:
        stmt = stmt.where(m.Product.is_otc == otc)
    if scientific:
        stmt = stmt.where(m.Product.scientific_name.like(f"{scientific}%"))
    if location:
        stmt = stmt.where(m.Product.shelf_location.like(f"{location}%"))
    if search:
        # Search-as-you-type: one typed letter matches every product that
        # STARTS with it (prefix), ranked before contains-anywhere matches —
        # so "ب" lists بانادول، بروفين… first, like eStock's item lookup.
        term = search.strip()
        prefix = f"{term}%"
        anywhere = f"%{term}%"
        stmt = stmt.where(
            or_(
                m.Product.name_ar.like(anywhere),
                m.Product.name_en.like(anywhere),
                m.Product.scientific_name.like(anywhere),
                m.Product.code.like(anywhere),
            )
        )
        rank = case(
            (
                or_(
                    m.Product.name_ar.like(prefix),
                    m.Product.name_en.like(prefix),
                    m.Product.code.like(prefix),
                ),
                0,
            ),
            (m.Product.scientific_name.like(prefix), 1),
            else_=2,
        )
        stmt = stmt.order_by(rank, m.Product.name_ar)
    elif sort == "price_asc":
        stmt = stmt.order_by(m.Product.sell_price.asc(), m.Product.name_ar)
    elif sort == "price_desc":
        stmt = stmt.order_by(m.Product.sell_price.desc(), m.Product.name_ar)
    else:
        stmt = stmt.order_by(m.Product.name_ar)
    stmt = stmt.limit(limit)
    rows = session.execute(stmt).all()

    # Cross-branch availability (أثناء البيع): when the caller is scoped to one
    # branch, also report each product's live stock at the OTHER branches so the
    # cashier instantly sees "متوفر في السنتا: ٩١" for an item that's out here.
    others: dict[int, list[dict]] = {}
    if branch_id and rows:
        ids = [p.product_id for p, _ in rows]
        other_rows = session.execute(
            select(
                m.StockBatch.product_id,
                m.Branch.branch_id,
                m.Branch.name_ar,
                func.sum(m.StockBatch.amount),
            )
            .join(m.Branch, m.Branch.branch_id == m.StockBatch.branch_id)
            .where(
                m.StockBatch.product_id.in_(ids),
                m.StockBatch.branch_id != branch_id,
                available_stock_filter(),
            )
            .group_by(m.StockBatch.product_id, m.Branch.branch_id, m.Branch.name_ar)
        ).all()
        for pid, bid, bname, qty in other_rows:
            if qty and float(qty) > 0:
                others.setdefault(pid, []).append(
                    {"branch_id": bid, "branch": bname, "on_hand": money(qty)}
                )

    out = []
    for p, qty in rows:
        on_hand_qty = money(qty)
        out.append(
            {
                "product_id": p.product_id,
                "code": p.code,
                "name_ar": p.name_ar,
                "name_en": p.name_en,
                "scientific_name": p.scientific_name,
                "sell_price": money(p.sell_price),
                "buy_price": money(p.buy_price),
                "min_stock": money(p.min_stock),
                "on_hand": on_hand_qty,
                "is_controlled": p.is_controlled,
                "shelf_location": p.shelf_location,
                "unit_big": p.unit_big,
                "unit_small": p.unit_small,
                "unit_factor": money(p.unit_factor or 1) or 1,
                "dosage_form": p.dosage_form,
                "is_otc": p.is_otc,
                "uses": p.uses,
                "other_branches": others.get(p.product_id, []),
                "low": on_hand_qty < float(p.min_stock or 0),
            }
        )
    return out


def create_product(session: Session, data: dict) -> dict:
    """إضافة صنف جديد — a locally-added product (eStock never mirrors it away:
    the catalogue loaders match by code/name and keep unmatched local rows)."""
    from app.services.pos import POSError

    name_ar = (data.get("name_ar") or "").strip()
    if not name_ar:
        raise POSError("name_required", "اسم الصنف مطلوب / product name required")
    dup = session.scalars(
        select(m.Product).where(m.Product.name_ar == name_ar, m.Product.is_deleted == False)  # noqa: E712
    ).first()
    if dup is not None:
        raise POSError("duplicate_name", f"الصنف موجود بالفعل #{dup.product_id} / already exists")
    factor = float(data.get("unit_factor") or 1)
    p = m.Product(
        name_ar=name_ar,
        name_en=(data.get("name_en") or "").strip() or None,
        scientific_name=(data.get("scientific_name") or "").strip() or None,
        code=(data.get("code") or "").strip() or None,
        sell_price=float(data.get("sell_price") or 0),
        buy_price=float(data.get("buy_price") or 0),
        min_stock=float(data.get("min_stock") or 0),
        unit_big=(data.get("unit_big") or "").strip() or None,
        unit_small=(data.get("unit_small") or "").strip() or None,
        unit_factor=factor if factor >= 1 else 1,
        dosage_form=(data.get("dosage_form") or "").strip() or None,
        is_otc=bool(data.get("is_otc") or False),
        uses=(data.get("uses") or "").strip() or None,
        shelf_location=(data.get("shelf_location") or "").strip() or None,
        is_controlled=bool(data.get("is_controlled") or False),
    )
    session.add(p)
    session.commit()
    return {"product_id": p.product_id, "name_ar": p.name_ar}


def filter_values(session: Session) -> dict:
    """Distinct classification values that actually exist — feeds the filter
    dropdowns (الشكل الصيدلاني، الأماكن) on the items screen."""
    forms = [
        f for (f,) in session.execute(
            select(m.Product.dosage_form).where(m.Product.dosage_form.is_not(None)).distinct()
        ) if f
    ]
    locations = [
        l for (l,) in session.execute(
            select(m.Product.shelf_location).where(m.Product.shelf_location.is_not(None)).distinct()
        ) if l
    ]
    return {"dosage_forms": sorted(forms), "locations": sorted(locations)}


def stagnant_products(
    session: Session,
    branch_id: int | None = None,
    days: int = 90,
    limit: int = 300,
) -> dict:
    """الأصناف الراكدة — stocked items with no sale in the last ``days`` days.

    Returns each item's on-hand, tied-up value (at buy price), last sale date
    and idle days, plus totals — eStock's stagnant-items report. Also used to
    scope a stagnant-items count session (جرد الراكد)."""
    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(days=days)

    on_hand = (
        select(
            m.StockBatch.product_id.label("pid"),
            func.sum(m.StockBatch.amount).label("qty"),
        )
        .where(available_stock_filter(), branch_filter(m.StockBatch, branch_id))
        .group_by(m.StockBatch.product_id)
        .subquery()
    )
    last_sale_q = (
        select(
            m.SaleLine.product_id.label("pid"),
            func.max(m.Sale.sale_date).label("last_sale"),
        )
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(m.Sale.is_return == False, branch_filter(m.Sale, branch_id))  # noqa: E712
        .group_by(m.SaleLine.product_id)
        .subquery()
    )
    stmt = (
        select(m.Product, on_hand.c.qty, last_sale_q.c.last_sale)
        .join(on_hand, on_hand.c.pid == m.Product.product_id)
        .join(last_sale_q, last_sale_q.c.pid == m.Product.product_id, isouter=True)
        .where(
            m.Product.is_deleted == False,  # noqa: E712
            (last_sale_q.c.last_sale.is_(None)) | (last_sale_q.c.last_sale < cutoff),
        )
        .order_by((on_hand.c.qty * m.Product.buy_price).desc())
        .limit(limit)
    )
    today = datetime.now()
    items = []
    total_qty = total_value = 0.0
    for p, qty, last_sale in session.execute(stmt):
        qty_f = money(qty)
        value = round(qty_f * float(p.buy_price or 0), 3)
        total_qty += qty_f
        total_value += value
        items.append(
            {
                "product_id": p.product_id,
                "code": p.code,
                "name_ar": p.name_ar,
                "name_en": p.name_en,
                "on_hand": qty_f,
                "buy_price": money(p.buy_price),
                "value": value,
                "last_sale": last_sale.isoformat() if last_sale else None,
                "idle_days": (today - last_sale).days if last_sale else None,
                "unit_big": p.unit_big,
            }
        )
    return {
        "days": days,
        "items": items,
        "total_items": len(items),
        "total_qty": money(total_qty),
        "total_value": money(total_value),
    }


def product_batches(session: Session, product_id: int, branch_id: int | None = None) -> list[dict]:
    """All live batches for a product, FEFO-ordered (first to expire first)."""
    stmt = (
        select(m.StockBatch, m.Branch.name_ar)
        .join(m.Branch, m.Branch.branch_id == m.StockBatch.branch_id)
        .where(
            m.StockBatch.product_id == product_id,
            m.StockBatch.amount > 0,
            branch_filter(m.StockBatch, branch_id),
        )
        .order_by(m.StockBatch.exp_date.asc().nulls_last())
    )
    out = []
    for batch, branch_name in session.execute(stmt):
        expired = batch.exp_date is not None and batch.exp_date <= TODAY
        out.append(
            {
                "batch_id": batch.batch_id,
                "branch": branch_name,
                "amount": money(batch.amount),
                "exp_date": batch.exp_date.isoformat() if batch.exp_date else None,
                "sell_price": money(batch.sell_price),
                "buy_price": money(batch.buy_price),
                "expired": expired,
            }
        )
    return out


def product_insight(session: Session, product_id: int, branch_id: int | None = None) -> dict | None:
    """Drill-down for a product: identity, on-hand per branch, a 30-day demand
    forecast, and recent sales — composed from existing services so a dashboard
    'second click' shows the detail behind a number."""
    from app.services import alerts

    p = session.get(m.Product, product_id)
    if p is None:
        return None

    # On-hand per branch (available = amount>0, non-expired).
    rows = session.execute(
        select(m.Branch.branch_id, m.Branch.name_ar, func.coalesce(func.sum(m.StockBatch.amount), 0))
        .select_from(m.Branch)
        .join(
            m.StockBatch,
            (m.StockBatch.branch_id == m.Branch.branch_id)
            & (m.StockBatch.product_id == product_id)
            & available_stock_filter(),
            isouter=True,
        )
        .group_by(m.Branch.branch_id, m.Branch.name_ar)
    ).all()
    per_branch = [{"branch_id": bid, "branch": name, "on_hand": money(qty)} for bid, name, qty in rows]

    # Recent sales of this product (last 20 lines).
    recent = session.execute(
        select(m.Sale.sale_id, m.Sale.sale_date, m.SaleLine.amount, m.SaleLine.total_sell)
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(m.SaleLine.product_id == product_id, m.Sale.is_return == False)  # noqa: E712
        .order_by(m.Sale.sale_date.desc())
        .limit(20)
    ).all()
    recent_sales = [
        {"sale_id": sid, "date": d.isoformat() if d else None, "qty": money(amt), "total": money(tot)}
        for sid, d, amt, tot in recent
    ]

    forecast = alerts.forecast(session, product_id, branch_id, days=30)

    return {
        "product_id": p.product_id,
        "name_ar": p.name_ar,
        "name_en": p.name_en,
        "scientific_name": p.scientific_name,
        "sell_price": money(p.sell_price),
        "buy_price": money(p.buy_price),
        "on_hand_by_branch": per_branch,
        "total_on_hand": money(sum(b["on_hand"] for b in per_branch)),
        "forecast_30d": forecast,
        "recent_sales": recent_sales,
    }


def adjust_stock(
    session: Session,
    batch_id: int,
    new_amount: float,
    *,
    reason: str = "adjust",
    employee_id: int | None = None,
) -> dict:
    """Manual stock adjustment / stock-count correction (eStock's
    Product_amount_update + Product_amount_reg_update): set a batch to the
    physically-counted quantity and record the delta in the audit trail."""
    from app.services.pos import POSError

    batch = session.get(m.StockBatch, batch_id)
    if batch is None:
        raise POSError("batch_not_found", f"التشغيلة غير موجودة #{batch_id} / batch not found")
    if new_amount < 0:
        raise POSError("bad_quantity", "الكمية لا يمكن أن تكون سالبة / amount cannot be negative")
    delta = round(float(new_amount) - float(batch.amount), 3)
    if delta == 0:
        return {"batch_id": batch_id, "amount": money(batch.amount), "delta": 0}
    batch.amount = float(new_amount)
    session.add(
        m.StockMovement(
            batch_id=batch.batch_id,
            branch_id=batch.branch_id,
            delta=delta,
            reason="adjust" if reason not in ("adjust", "writeoff") else reason,
            employee_id=employee_id,
        )
    )
    session.commit()
    return {"batch_id": batch_id, "amount": money(new_amount), "delta": money(delta)}


def set_shelf_location(session: Session, product_id: int, shelf_location: str | None) -> dict:
    """Merchandising: set/clear a product's physical shelf/place code."""
    from app.services.pos import POSError

    product = session.get(m.Product, product_id)
    if product is None or product.is_deleted:
        raise POSError("product_not_found", f"صنف غير موجود #{product_id} / product not found")
    product.shelf_location = (shelf_location or "").strip() or None
    session.commit()
    return {"product_id": product_id, "shelf_location": product.shelf_location}
