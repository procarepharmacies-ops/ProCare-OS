"""Dashboard / KPI service — the read-only queries from ``sql/dashboard-queries.sql``
expressed over ProCare's own clean schema.

Every metric obeys the data-quality rules in ``common``: returns excluded,
available stock only, FEFO. All accept an optional ``branch_id`` (None =
consolidated across Main + Elsanta).
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import available_stock_filter, branch_filter, money, sql_day, today


def _sales_base(branch_id):
    return select(m.Sale).where(m.Sale.is_return == False, branch_filter(m.Sale, branch_id))  # noqa: E712


def summary(session: Session, branch_id: int | None = None) -> dict:
    """Headline KPIs for the dashboard cards."""
    month_start = today().replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    def revenue_between(start, end):
        stmt = (
            select(func.coalesce(func.sum(m.Sale.total_net), 0), func.count())
            .where(
                m.Sale.is_return == False,  # noqa: E712
                branch_filter(m.Sale, branch_id),
                sql_day(m.Sale.sale_date) >= start,
                sql_day(m.Sale.sale_date) <= end,
            )
        )
        rev, cnt = session.execute(stmt).one()
        return money(rev), cnt

    sales_today, bills_today = revenue_between(today(), today())
    sales_month, bills_month = revenue_between(month_start, today())
    sales_prev_month, _ = revenue_between(prev_month_start, prev_month_end)

    # Low-stock: products whose total available qty is below their min_stock.
    low_stock = _low_stock_count(session, branch_id)

    # Expiring within 30 days (still in stock).
    expiring = session.execute(
        select(func.count(func.distinct(m.StockBatch.product_id))).where(
            m.StockBatch.amount > 0,
            branch_filter(m.StockBatch, branch_id),
            m.StockBatch.exp_date != None,  # noqa: E711
            m.StockBatch.exp_date > today(),
            m.StockBatch.exp_date <= today() + timedelta(days=30),
        )
    ).scalar_one()

    debtors = session.execute(
        select(func.count()).where(
            m.Customer.credit_limit > 0,
            m.Customer.current_balance > m.Customer.credit_limit,
        )
    ).scalar_one()

    # Profit this month: revenue - cost on non-return lines.
    profit_month = _profit(session, branch_id, month_start, today())

    return {
        "as_of": today().isoformat(),
        "branch_id": branch_id or 0,
        "kpis": {
            "sales_today": sales_today,
            "bills_today": bills_today,
            "sales_month": sales_month,
            "sales_prev_month": sales_prev_month,
            "profit_month": profit_month,
            "low_stock": low_stock,
            "expiring_30": expiring,
            "debtors": debtors,
        },
    }


def _low_stock_count(session: Session, branch_id) -> int:
    on_hand = (
        select(
            m.StockBatch.product_id.label("pid"),
            func.sum(m.StockBatch.amount).label("qty"),
        )
        .where(available_stock_filter(), branch_filter(m.StockBatch, branch_id))
        .group_by(m.StockBatch.product_id)
        .subquery()
    )
    stmt = select(func.count()).select_from(m.Product).join(
        on_hand, on_hand.c.pid == m.Product.product_id, isouter=True
    ).where(
        m.Product.is_active == True,  # noqa: E712
        func.coalesce(on_hand.c.qty, 0) < m.Product.min_stock,
    )
    return session.execute(stmt).scalar_one()


def _profit(session: Session, branch_id, start, end) -> float:
    stmt = (
        select(
            func.coalesce(func.sum(m.SaleLine.total_sell), 0),
            func.coalesce(func.sum(m.SaleLine.amount * m.SaleLine.buy_price), 0),
        )
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            sql_day(m.Sale.sale_date) >= start,
            sql_day(m.Sale.sale_date) <= end,
        )
    )
    revenue, cost = session.execute(stmt).one()
    return money(float(revenue) - float(cost))


def daily_sales(session: Session, branch_id: int | None = None, days: int = 30) -> list[dict]:
    """Per-day sales, matching eStock's daily-sales report (sales_daily_rpt):
    bills, items, gross, discount, net, cash, non-cash. ``revenue`` is kept as an
    alias of ``net`` so the existing trend chart keeps working."""
    start = today() - timedelta(days=days - 1)
    # Header aggregates per day.
    hdr = session.execute(
        select(
            sql_day(m.Sale.sale_date).label("d"),
            func.count().label("bills"),
            func.coalesce(func.sum(m.Sale.total_gross), 0).label("gross"),
            func.coalesce(func.sum(m.Sale.total_discount), 0).label("discount"),
            func.coalesce(func.sum(m.Sale.total_net), 0).label("net"),
            func.coalesce(func.sum(m.Sale.cash_paid), 0).label("cash"),
            func.coalesce(func.sum(m.Sale.card_paid), 0).label("card"),
        )
        .where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            sql_day(m.Sale.sale_date) >= start,
        )
        .group_by(sql_day(m.Sale.sale_date))
    ).all()
    # Item counts per day (join sale_lines once, grouped).
    items = dict(session.execute(
        select(sql_day(m.Sale.sale_date).label("d"), func.coalesce(func.sum(m.SaleLine.amount), 0))
        .select_from(m.Sale).join(m.SaleLine, m.SaleLine.sale_id == m.Sale.sale_id)
        .where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            sql_day(m.Sale.sale_date) >= start,
        )
        .group_by(sql_day(m.Sale.sale_date))
    ).all())
    by_day = {str(r.d): r for r in hdr}
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        r = by_day.get(d)
        net = money(r.net) if r else 0.0
        cash = money(r.cash) if r else 0.0
        out.append({
            "date": d,
            "bills": r.bills if r else 0,
            "items": money(items.get(d, 0)),
            "gross": money(r.gross) if r else 0.0,
            "discount": money(r.discount) if r else 0.0,
            "net": net,
            "revenue": net,  # alias — keeps the existing trend chart working
            "cash": cash,
            "card": money(r.card) if r else 0.0,
            "non_cash": money(net - cash),
        })
    return out


def top_products(session: Session, branch_id: int | None = None, days: int = 30, limit: int = 10) -> list[dict]:
    start = today() - timedelta(days=days - 1)
    stmt = (
        select(
            m.Product.product_id,
            m.Product.name_ar,
            m.Product.name_en,
            func.sum(m.SaleLine.amount).label("units"),
            func.sum(m.SaleLine.total_sell).label("revenue"),
        )
        .join(m.SaleLine, m.SaleLine.product_id == m.Product.product_id)
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            sql_day(m.Sale.sale_date) >= start,
        )
        .group_by(m.Product.product_id, m.Product.name_ar, m.Product.name_en)
        .order_by(func.sum(m.SaleLine.total_sell).desc())
        .limit(limit)
    )
    return [
        {"product_id": r.product_id, "name_ar": r.name_ar, "name_en": r.name_en, "units": money(r.units), "revenue": money(r.revenue)}
        for r in session.execute(stmt)
    ]


def hourly_sales(session: Session, branch_id: int | None = None) -> list[dict]:
    """Peak-hours for the most recent active day. Bucketed in Python so it is
    dialect-agnostic (SQLite dev + SQL Server prod behave identically)."""
    target = session.execute(
        select(func.max(sql_day(m.Sale.sale_date))).where(branch_filter(m.Sale, branch_id))
    ).scalar_one()
    if target is None:
        return []
    rows = session.execute(
        select(m.Sale.sale_date, m.Sale.total_net).where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            sql_day(m.Sale.sale_date) == target,
        )
    ).all()
    buckets: dict[int, list] = {}
    for ts, net in rows:
        h = ts.hour
        b = buckets.setdefault(h, [0, 0.0])
        b[0] += 1
        b[1] += float(net or 0)
    return [
        {"hour": h, "bills": buckets[h][0], "revenue": money(buckets[h][1])}
        for h in sorted(buckets)
    ]


def monthly_sales(session: Session, branch_id: int | None = None, months: int = 12) -> list[dict]:
    """Revenue + bills + profit per calendar month — the dashboard month view.
    Bucketed in Python so SQLite dev and SQL Server prod behave identically."""
    start = (today().replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)
    rows = session.execute(
        select(
            m.Sale.sale_date,
            m.Sale.total_net,
            m.Sale.total_discount,
            m.Sale.sale_id,
        ).where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            sql_day(m.Sale.sale_date) >= start,
        )
    ).all()
    profit_rows = session.execute(
        select(
            m.Sale.sale_date,
            func.coalesce(func.sum(m.SaleLine.total_sell - m.SaleLine.amount * m.SaleLine.buy_price), 0),
        )
        .join(m.SaleLine, m.SaleLine.sale_id == m.Sale.sale_id)
        .where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            sql_day(m.Sale.sale_date) >= start,
        )
        .group_by(m.Sale.sale_id, m.Sale.sale_date)
    ).all()

    buckets: dict[str, dict] = {}
    for ts, net, disc, _sid in rows:
        key = f"{ts.year:04d}-{ts.month:02d}"
        b = buckets.setdefault(key, {"month": key, "bills": 0, "revenue": 0.0, "discount": 0.0, "profit": 0.0})
        b["bills"] += 1
        b["revenue"] += float(net or 0)
        b["discount"] += float(disc or 0)
    for ts, profit in profit_rows:
        key = f"{ts.year:04d}-{ts.month:02d}"
        if key in buckets:
            buckets[key]["profit"] += float(profit or 0)
    out = [
        {**b, "revenue": money(b["revenue"]), "discount": money(b["discount"]), "profit": money(b["profit"])}
        for b in buckets.values()
    ]
    out.sort(key=lambda r: r["month"])
    return out[-months:]


def by_branch(session: Session, date_from=None, date_to=None) -> list[dict]:
    """Side-by-side branch comparison over a date range (defaults: this month).
    Revenue, bills, discount, profit per branch — the all-branches dashboard."""
    start = date_from or today().replace(day=1)
    end = date_to or today()
    branches = session.scalars(select(m.Branch).order_by(m.Branch.branch_id)).all()

    sales_rows = session.execute(
        select(
            m.Sale.branch_id,
            func.count(),
            func.coalesce(func.sum(m.Sale.total_net), 0),
            func.coalesce(func.sum(m.Sale.total_discount), 0),
        )
        .where(
            m.Sale.is_return == False,  # noqa: E712
            sql_day(m.Sale.sale_date) >= start,
            sql_day(m.Sale.sale_date) <= end,
        )
        .group_by(m.Sale.branch_id)
    ).all()
    by_id = {bid: (bills, float(rev), float(disc)) for bid, bills, rev, disc in sales_rows}

    profit_rows = session.execute(
        select(
            m.Sale.branch_id,
            func.coalesce(func.sum(m.SaleLine.total_sell - m.SaleLine.amount * m.SaleLine.buy_price), 0),
        )
        .join(m.SaleLine, m.SaleLine.sale_id == m.Sale.sale_id)
        .where(
            m.Sale.is_return == False,  # noqa: E712
            sql_day(m.Sale.sale_date) >= start,
            sql_day(m.Sale.sale_date) <= end,
        )
        .group_by(m.Sale.branch_id)
    ).all()
    profit_by_id = {bid: float(p) for bid, p in profit_rows}

    out = []
    for b in branches:
        bills, revenue, discount = by_id.get(b.branch_id, (0, 0.0, 0.0))
        out.append(
            {
                "branch_id": b.branch_id,
                "name_ar": b.name_ar,
                "name_en": b.name_en,
                "bills": bills,
                "revenue": money(revenue),
                "discount": money(discount),
                "profit": money(profit_by_id.get(b.branch_id, 0.0)),
            }
        )
    return out


def range_summary(session: Session, branch_id: int | None, date_from, date_to) -> dict:
    """KPIs for an arbitrary [date_from, date_to] window — powers the
    choose-your-dates dashboard view."""
    rev, cnt, disc = session.execute(
        select(
            func.coalesce(func.sum(m.Sale.total_net), 0),
            func.count(),
            func.coalesce(func.sum(m.Sale.total_discount), 0),
        ).where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            sql_day(m.Sale.sale_date) >= date_from,
            sql_day(m.Sale.sale_date) <= date_to,
        )
    ).one()
    return {
        "date_from": str(date_from),
        "date_to": str(date_to),
        "branch_id": branch_id or 0,
        "revenue": money(rev),
        "bills": cnt,
        "discount": money(disc),
        "profit": _profit(session, branch_id, date_from, date_to),
    }


def cashier_performance(session: Session, branch_id: int | None = None, days: int = 30) -> list[dict]:
    start = today() - timedelta(days=days - 1)
    stmt = (
        select(
            m.Employee.name_ar,
            func.count().label("bills"),
            func.coalesce(func.sum(m.Sale.total_net), 0).label("revenue"),
        )
        .join(m.Sale, m.Sale.cashier_id == m.Employee.employee_id)
        .where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            sql_day(m.Sale.sale_date) >= start,
        )
        .group_by(m.Employee.employee_id, m.Employee.name_ar)
        .order_by(func.sum(m.Sale.total_net).desc())
    )
    return [{"cashier": r.name_ar, "bills": r.bills, "revenue": money(r.revenue)} for r in session.execute(stmt)]
