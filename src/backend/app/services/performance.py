"""Pharmacy performance over time + data-quality audit + supplier analysis.

This is the owner's "how is the pharmacy doing over the years" layer. Everything
here is derived from data ProCare actually holds (sales, sale lines, purchases,
stock, customers, vendors) after the eStock mirror / SQL Server Express cut-over,
so every figure is reproducible — the same numbers come out of
``sql/performance-analysis.sql`` run directly against SQL Server Express.

Three views:

* ``overview``  — a multi-year (default 5) trend: per-year and per-month revenue,
  gross profit, invoices, active + new customers, cash vs card, purchasing spend,
  plus a current stock / cash-on-hand snapshot and year-over-year growth.
* ``audit``     — a reconciliation / data-quality report: negative stock, expired
  stock still on hand and its value, orphan batches, invoices with no lines,
  products priced below cost, customers over their credit limit, and the overall
  data span. This is the "audit report" run after a fresh sync.
* ``vendor_purchasing`` — purchasing investigation for one supplier (PharmaOverseas
  by default): spend per year, orders, items, top products, the current payable
  balance, and its share of total purchasing, with a full vendor ranking.

Bucketing is done in Python (small row counts) so the exact same code runs on
SQLite (dev/tests) and SQL Server (production) without dialect-specific date SQL.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import TODAY, available_stock_filter, branch_filter, money


def _pct(numerator: float, denominator: float) -> float | None:
    return round(100 * numerator / denominator, 1) if denominator else None


# --- 5-year performance overview -------------------------------------------
def overview(session: Session, years: int = 5, branch_id: int | None = None) -> dict:
    """Per-year and per-month pharmacy performance for the last ``years`` years."""
    years = max(1, min(int(years), 15))
    year_list = list(range(TODAY.year - years + 1, TODAY.year + 1))
    window_start = datetime(year_list[0], 1, 1)

    # Blank per-year accumulator.
    def _blank() -> dict:
        return {
            "revenue": 0.0, "cogs": 0.0, "bills": 0, "returns": 0, "returns_value": 0.0,
            "items_sold": 0.0, "cash_collected": 0.0, "card_collected": 0.0,
            "discount_given": 0.0, "customers": set(), "new_customers": 0,
            "purchases_spend": 0.0, "purchase_orders": 0,
        }

    per_year: dict[int, dict] = {y: _blank() for y in year_list}
    per_month: dict[str, dict] = {}

    def _month(key: str) -> dict:
        return per_month.setdefault(key, {"revenue": 0.0, "bills": 0, "cogs": 0.0})

    # Sale headers (non-return): revenue, bills, cash/card, discount, customers.
    rows = session.execute(
        select(
            m.Sale.sale_date, m.Sale.total_net, m.Sale.cash_paid, m.Sale.card_paid,
            m.Sale.total_discount, m.Sale.customer_id,
        ).where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            m.Sale.sale_date >= window_start,
        )
    ).all()
    for sale_date, net, cash, card, disc, customer_id in rows:
        y = sale_date.year
        yb = per_year.get(y)
        if yb is None:
            continue
        yb["revenue"] += float(net or 0)
        yb["bills"] += 1
        yb["cash_collected"] += float(cash or 0)
        yb["card_collected"] += float(card or 0)
        yb["discount_given"] += float(disc or 0)
        if customer_id:
            yb["customers"].add(customer_id)
        mb = _month(f"{y}-{sale_date.month:02d}")
        mb["revenue"] += float(net or 0)
        mb["bills"] += 1

    # Returns (refunds): count + value.
    for sale_date, net in session.execute(
        select(m.Sale.sale_date, m.Sale.total_net).where(
            m.Sale.is_return == True,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            m.Sale.sale_date >= window_start,
        )
    ).all():
        yb = per_year.get(sale_date.year)
        if yb is not None:
            yb["returns"] += 1
            yb["returns_value"] += float(net or 0)

    # Sale lines (non-return): COGS + units, for gross profit and volume.
    for sale_date, amount, buy_price in session.execute(
        select(m.Sale.sale_date, m.SaleLine.amount, m.SaleLine.buy_price)
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            m.Sale.sale_date >= window_start,
        )
    ).all():
        yb = per_year.get(sale_date.year)
        if yb is None:
            continue
        cost = float(amount or 0) * float(buy_price or 0)
        yb["cogs"] += cost
        yb["items_sold"] += float(amount or 0)
        _month(f"{sale_date.year}-{sale_date.month:02d}")["cogs"] += cost

    # New customers per year (by join date).
    for (created_at,) in session.execute(
        select(m.Customer.created_at).where(m.Customer.is_deleted == False)  # noqa: E712
    ).all():
        if created_at and created_at.year in per_year:
            per_year[created_at.year]["new_customers"] += 1

    # Purchasing spend per year (net of discount).
    for bill_date, gross, disc in session.execute(
        select(m.Purchase.bill_date, m.Purchase.total_gross, m.Purchase.total_discount).where(
            m.Purchase.is_return == False,  # noqa: E712
            branch_filter(m.Purchase, branch_id),
            m.Purchase.bill_date >= window_start.date(),
        )
    ).all():
        yb = per_year.get(bill_date.year)
        if yb is not None:
            yb["purchases_spend"] += float(gross or 0) - float(disc or 0)
            yb["purchase_orders"] += 1

    # Assemble the yearly series with YoY growth.
    yearly = []
    prev_rev = None
    for y in year_list:
        b = per_year[y]
        gross_profit = b["revenue"] - b["cogs"]
        yearly.append({
            "year": y,
            "revenue": money(b["revenue"]),
            "cogs": money(b["cogs"]),
            "gross_profit": money(gross_profit),
            "margin_pct": _pct(gross_profit, b["revenue"]),
            "invoices": b["bills"],
            "returns": b["returns"],
            "returns_value": money(b["returns_value"]),
            "items_sold": money(b["items_sold"]),
            "active_customers": len(b["customers"]),
            "new_customers": b["new_customers"],
            "cash_collected": money(b["cash_collected"]),
            "card_collected": money(b["card_collected"]),
            "discount_given": money(b["discount_given"]),
            "avg_bill": money(b["revenue"] / b["bills"]) if b["bills"] else 0,
            "purchases_spend": money(b["purchases_spend"]),
            "purchase_orders": b["purchase_orders"],
            "revenue_growth_pct": _pct(b["revenue"] - prev_rev, prev_rev) if prev_rev else None,
        })
        prev_rev = b["revenue"]

    monthly = [
        {"month": k, "revenue": money(v["revenue"]), "invoices": v["bills"],
         "gross_profit": money(v["revenue"] - v["cogs"])}
        for k, v in sorted(per_month.items())
    ]

    totals = {
        "revenue": money(sum(y["revenue"] for y in yearly)),
        "gross_profit": money(sum(y["gross_profit"] for y in yearly)),
        "invoices": sum(y["invoices"] for y in yearly),
        "returns": sum(y["returns"] for y in yearly),
        "purchases_spend": money(sum(y["purchases_spend"] for y in yearly)),
    }

    return {
        "as_of": TODAY.isoformat(),
        "branch_id": branch_id or 0,
        "years": years,
        "year_range": [year_list[0], year_list[-1]],
        "yearly": yearly,
        "monthly": monthly,
        "totals": totals,
        "snapshot": _snapshot(session, branch_id),
    }


def _snapshot(session: Session, branch_id: int | None) -> dict:
    """Current stock level, stock valuation and cash-on-hand position."""
    avail = available_stock_filter()
    on_hand_units, value_cost, value_retail = session.execute(
        select(
            func.coalesce(func.sum(m.StockBatch.amount), 0),
            func.coalesce(func.sum(m.StockBatch.amount * m.StockBatch.buy_price), 0),
            func.coalesce(func.sum(m.StockBatch.amount * m.StockBatch.sell_price), 0),
        ).where(avail, branch_filter(m.StockBatch, branch_id))
    ).one()

    expired_units, expired_value = session.execute(
        select(
            func.coalesce(func.sum(m.StockBatch.amount), 0),
            func.coalesce(func.sum(m.StockBatch.amount * m.StockBatch.buy_price), 0),
        ).where(
            m.StockBatch.amount > 0,
            branch_filter(m.StockBatch, branch_id),
            m.StockBatch.exp_date != None,  # noqa: E711
            m.StockBatch.exp_date <= TODAY,
        )
    ).one()

    receivables = session.scalar(
        select(func.coalesce(func.sum(m.Customer.current_balance), 0)).where(m.Customer.current_balance > 0)
    ) or 0
    payables = session.scalar(
        select(func.coalesce(func.sum(m.Vendor.current_balance), 0)).where(m.Vendor.current_balance > 0)
    ) or 0
    registered_customers = session.scalar(
        select(func.count()).select_from(m.Customer).where(m.Customer.is_deleted == False)  # noqa: E712
    ) or 0

    return {
        "stock_on_hand_units": money(on_hand_units),
        "stock_value_at_cost": money(value_cost),
        "stock_value_at_retail": money(value_retail),
        "potential_stock_margin": money(float(value_retail) - float(value_cost)),
        "expired_in_stock_units": money(expired_units),
        "expired_in_stock_value": money(expired_value),
        "low_stock_products": _low_stock_count(session, branch_id),
        "registered_customers": int(registered_customers),
        "receivables_from_customers": money(receivables),
        "payables_to_vendors": money(payables),
    }


def _low_stock_count(session: Session, branch_id: int | None) -> int:
    on_hand = (
        select(m.StockBatch.product_id.label("pid"), func.sum(m.StockBatch.amount).label("qty"))
        .where(available_stock_filter(), branch_filter(m.StockBatch, branch_id))
        .group_by(m.StockBatch.product_id)
        .subquery()
    )
    stmt = (
        select(func.count())
        .select_from(m.Product)
        .join(on_hand, on_hand.c.pid == m.Product.product_id, isouter=True)
        .where(m.Product.is_active == True, func.coalesce(on_hand.c.qty, 0) < m.Product.min_stock)  # noqa: E712
    )
    return int(session.execute(stmt).scalar_one())


# --- Data-quality / reconciliation audit -----------------------------------
def audit(session: Session, branch_id: int | None = None) -> dict:
    """Post-sync data-quality audit: the checks the owner wants signed off."""
    checks: list[dict] = []

    def add(key, label_en, label_ar, status, value, detail=""):
        checks.append({
            "key": key, "label_en": label_en, "label_ar": label_ar,
            "status": status, "value": value, "detail": detail,
        })

    # Negative stock — must never happen (CK_stock_amount enforces it).
    negative = session.scalar(
        select(func.count()).select_from(m.StockBatch).where(
            m.StockBatch.amount < 0, branch_filter(m.StockBatch, branch_id)
        )
    ) or 0
    add("negative_stock", "Negative stock batches", "أرصدة مخزون سالبة",
        "ok" if negative == 0 else "fail", int(negative),
        "Stock can never go negative." if negative == 0 else "Investigate: constraint bypass.")

    # Expired stock still on hand.
    exp_products, exp_units, exp_value = session.execute(
        select(
            func.count(func.distinct(m.StockBatch.product_id)),
            func.coalesce(func.sum(m.StockBatch.amount), 0),
            func.coalesce(func.sum(m.StockBatch.amount * m.StockBatch.buy_price), 0),
        ).where(
            m.StockBatch.amount > 0, branch_filter(m.StockBatch, branch_id),
            m.StockBatch.exp_date != None, m.StockBatch.exp_date <= TODAY,  # noqa: E711
        )
    ).one()
    add("expired_in_stock", "Expired stock still on hand", "مخزون منتهي الصلاحية",
        "ok" if exp_products == 0 else "warn", int(exp_products),
        f"{money(exp_units)} units, {money(exp_value)} EGP at cost — write off / quarantine.")

    # Orphan batches (product deleted or missing).
    orphan = session.scalar(
        select(func.count()).select_from(m.StockBatch)
        .join(m.Product, m.Product.product_id == m.StockBatch.product_id, isouter=True)
        .where(branch_filter(m.StockBatch, branch_id),
               or_(m.Product.product_id == None, m.Product.is_deleted == True))  # noqa: E711,E712
    ) or 0
    add("orphan_batches", "Batches on deleted/missing products", "دفعات لمنتجات محذوفة",
        "ok" if orphan == 0 else "warn", int(orphan))

    # Sale invoices (non-return) with no lines.
    line_counts = (
        select(m.SaleLine.sale_id.label("sid")).group_by(m.SaleLine.sale_id).subquery()
    )
    zero_line = session.scalar(
        select(func.count()).select_from(m.Sale)
        .join(line_counts, line_counts.c.sid == m.Sale.sale_id, isouter=True)
        .where(m.Sale.is_return == False, branch_filter(m.Sale, branch_id),  # noqa: E712
               line_counts.c.sid == None)  # noqa: E711
    ) or 0
    add("zero_line_sales", "Invoices with no line items", "فواتير بلا أصناف",
        "ok" if zero_line == 0 else "warn", int(zero_line))

    # Products priced at or below cost (margin leak).
    below_cost = session.scalar(
        select(func.count()).select_from(m.Product).where(
            m.Product.is_active == True, m.Product.buy_price > 0,  # noqa: E712
            m.Product.sell_price < m.Product.buy_price,
        )
    ) or 0
    add("price_below_cost", "Active products priced below cost", "أصناف سعر بيعها أقل من التكلفة",
        "ok" if below_cost == 0 else "warn", int(below_cost))

    # Customers over their credit limit.
    over_limit = session.scalar(
        select(func.count()).select_from(m.Customer).where(
            m.Customer.credit_limit > 0, m.Customer.current_balance > m.Customer.credit_limit,
        )
    ) or 0
    add("customers_over_limit", "Customers over credit limit", "عملاء تجاوزوا حد الائتمان",
        "ok" if over_limit == 0 else "warn", int(over_limit))

    # Walk-in share (informational — not a defect, but useful for CRM reach).
    total_sales = session.scalar(
        select(func.count()).select_from(m.Sale).where(
            m.Sale.is_return == False, branch_filter(m.Sale, branch_id))  # noqa: E712
    ) or 0
    walk_in = session.scalar(
        select(func.count()).select_from(m.Sale).where(
            m.Sale.is_return == False, branch_filter(m.Sale, branch_id),  # noqa: E712
            m.Sale.customer_id == None)  # noqa: E711
    ) or 0
    add("walk_in_share", "Walk-in invoices (no customer)", "فواتير بدون عميل مسجل",
        "info", _pct(walk_in, total_sales), f"{walk_in} of {total_sales} invoices — CRM reach opportunity.")

    # Data span + volumes.
    first_sale = session.scalar(select(func.min(m.Sale.sale_date)).where(branch_filter(m.Sale, branch_id)))
    last_sale = session.scalar(select(func.max(m.Sale.sale_date)).where(branch_filter(m.Sale, branch_id)))
    total_lines = session.scalar(select(func.count()).select_from(m.SaleLine)) or 0
    total_purchases = session.scalar(
        select(func.count()).select_from(m.Purchase).where(branch_filter(m.Purchase, branch_id))
    ) or 0

    fails = sum(1 for c in checks if c["status"] == "fail")
    warns = sum(1 for c in checks if c["status"] == "warn")
    return {
        "as_of": TODAY.isoformat(),
        "branch_id": branch_id or 0,
        "overall": "fail" if fails else ("warn" if warns else "ok"),
        "fail_count": fails,
        "warn_count": warns,
        "checks": checks,
        "data_span": {
            "first_sale": first_sale.isoformat() if first_sale else None,
            "last_sale": last_sale.isoformat() if last_sale else None,
            "total_invoices": int(total_sales),
            "total_sale_lines": int(total_lines),
            "total_purchases": int(total_purchases),
        },
        "valuation": _snapshot(session, branch_id),
    }


# --- Supplier / purchasing investigation (PharmaOverseas) -------------------
def _resolve_vendor(session: Session, query: str | int) -> m.Vendor | None:
    if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
        return session.get(m.Vendor, int(query))
    q = str(query).strip().lower()
    for v in session.scalars(select(m.Vendor)).all():
        hay = f"{(v.name_en or '').lower()} {(v.name_ar or '')}"
        if q in hay:
            return v
    return None


def vendor_purchasing(session: Session, query: str | int = "pharmaoverseas",
                      years: int = 5, branch_id: int | None = None) -> dict:
    """Purchasing history for one supplier: spend/orders/items per year, top
    products, current payable, and share of total purchasing (+ vendor ranking)."""
    years = max(1, min(int(years), 15))
    year_list = list(range(TODAY.year - years + 1, TODAY.year + 1))
    window_start = date(year_list[0], 1, 1)

    vendor = _resolve_vendor(session, query)

    # Spend across ALL vendors in the window → ranking + share context.
    all_rows = session.execute(
        select(
            m.Purchase.vendor_id,
            func.count(),
            func.coalesce(func.sum(m.Purchase.total_gross - m.Purchase.total_discount), 0),
        ).where(
            m.Purchase.is_return == False,  # noqa: E712
            branch_filter(m.Purchase, branch_id),
            m.Purchase.bill_date >= window_start,
        ).group_by(m.Purchase.vendor_id)
    ).all()
    names = dict(session.execute(select(m.Vendor.vendor_id, m.Vendor.name_ar)).all())
    names_en = dict(session.execute(select(m.Vendor.vendor_id, m.Vendor.name_en)).all())
    total_spend = float(sum(r[2] for r in all_rows)) or 0.0
    ranking = sorted(
        (
            {"vendor_id": vid, "name_ar": names.get(vid), "name_en": names_en.get(vid),
             "orders": int(cnt), "spend": money(spend),
             "share_pct": _pct(float(spend), total_spend)}
            for vid, cnt, spend in all_rows
        ),
        key=lambda r: -r["spend"],
    )

    if vendor is None:
        return {
            "as_of": TODAY.isoformat(), "query": str(query), "found": False,
            "message": "No matching vendor — showing full purchasing ranking instead.",
            "total_purchasing_spend": money(total_spend), "vendor_ranking": ranking,
        }

    # Per-year spend/orders/items for THIS vendor.
    per_year = {y: {"spend": 0.0, "orders": 0, "items": 0.0} for y in year_list}
    for bill_date, gross, disc in session.execute(
        select(m.Purchase.bill_date, m.Purchase.total_gross, m.Purchase.total_discount).where(
            m.Purchase.vendor_id == vendor.vendor_id, m.Purchase.is_return == False,  # noqa: E712
            branch_filter(m.Purchase, branch_id), m.Purchase.bill_date >= window_start,
        )
    ).all():
        yb = per_year.get(bill_date.year)
        if yb is not None:
            yb["spend"] += float(gross or 0) - float(disc or 0)
            yb["orders"] += 1

    for bill_date, amount in session.execute(
        select(m.Purchase.bill_date, m.PurchaseLine.amount)
        .join(m.Purchase, m.Purchase.purchase_id == m.PurchaseLine.purchase_id)
        .where(
            m.Purchase.vendor_id == vendor.vendor_id, m.Purchase.is_return == False,  # noqa: E712
            branch_filter(m.Purchase, branch_id), m.Purchase.bill_date >= window_start,
        )
    ).all():
        yb = per_year.get(bill_date.year)
        if yb is not None:
            yb["items"] += float(amount or 0)

    yearly = [
        {"year": y, "spend": money(per_year[y]["spend"]), "orders": per_year[y]["orders"],
         "items": money(per_year[y]["items"])}
        for y in year_list
    ]

    # Top products bought from this vendor over the window.
    top = session.execute(
        select(
            m.Product.name_ar, m.Product.name_en,
            func.coalesce(func.sum(m.PurchaseLine.amount), 0),
            func.coalesce(func.sum(m.PurchaseLine.amount * m.PurchaseLine.buy_price), 0),
        )
        .join(m.PurchaseLine, m.PurchaseLine.product_id == m.Product.product_id)
        .join(m.Purchase, m.Purchase.purchase_id == m.PurchaseLine.purchase_id)
        .where(
            m.Purchase.vendor_id == vendor.vendor_id, m.Purchase.is_return == False,  # noqa: E712
            branch_filter(m.Purchase, branch_id), m.Purchase.bill_date >= window_start,
        )
        .group_by(m.Product.product_id, m.Product.name_ar, m.Product.name_en)
        .order_by(func.sum(m.PurchaseLine.amount * m.PurchaseLine.buy_price).desc())
        .limit(10)
    ).all()

    vendor_spend = sum(y["spend"] for y in yearly)
    return {
        "as_of": TODAY.isoformat(),
        "query": str(query),
        "found": True,
        "vendor": {
            "vendor_id": vendor.vendor_id, "name_ar": vendor.name_ar, "name_en": vendor.name_en,
            "current_payable": money(vendor.current_balance), "credit_limit": money(vendor.credit_limit),
        },
        "total_spend": money(vendor_spend),
        "total_orders": sum(y["orders"] for y in yearly),
        "share_of_purchasing_pct": _pct(vendor_spend, total_spend),
        "yearly": yearly,
        "top_products": [
            {"name_ar": r[0], "name_en": r[1], "units": money(r[2]), "spend": money(r[3])}
            for r in top
        ],
        "vendor_ranking": ranking,
    }


if __name__ == "__main__":
    import json

    from app.db.base import SessionLocal

    with SessionLocal() as s:
        out = {
            "overview": overview(s),
            "audit": audit(s),
            "vendor_purchasing": vendor_purchasing(s),
        }
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
