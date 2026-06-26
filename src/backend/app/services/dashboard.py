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
from app.services.common import TODAY, available_stock_filter, branch_filter, money


def _sales_base(branch_id):
    return select(m.Sale).where(m.Sale.is_return == False, branch_filter(m.Sale, branch_id))  # noqa: E712


def summary(session: Session, branch_id: int | None = None) -> dict:
    """Headline KPIs for the dashboard cards."""
    month_start = TODAY.replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    def revenue_between(start, end):
        stmt = (
            select(func.coalesce(func.sum(m.Sale.total_net), 0), func.count())
            .where(
                m.Sale.is_return == False,  # noqa: E712
                branch_filter(m.Sale, branch_id),
                func.date(m.Sale.sale_date) >= start,
                func.date(m.Sale.sale_date) <= end,
            )
        )
        rev, cnt = session.execute(stmt).one()
        return money(rev), cnt

    sales_today, bills_today = revenue_between(TODAY, TODAY)
    sales_month, bills_month = revenue_between(month_start, TODAY)
    sales_prev_month, _ = revenue_between(prev_month_start, prev_month_end)

    # Low-stock: products whose total available qty is below their min_stock.
    low_stock = _low_stock_count(session, branch_id)

    # Expiring within 30 days (still in stock).
    expiring = session.execute(
        select(func.count(func.distinct(m.StockBatch.product_id))).where(
            m.StockBatch.amount > 0,
            branch_filter(m.StockBatch, branch_id),
            m.StockBatch.exp_date != None,  # noqa: E711
            m.StockBatch.exp_date > TODAY,
            m.StockBatch.exp_date <= TODAY + timedelta(days=30),
        )
    ).scalar_one()

    debtors = session.execute(
        select(func.count()).where(
            m.Customer.credit_limit > 0,
            m.Customer.current_balance > m.Customer.credit_limit,
        )
    ).scalar_one()

    # Profit this month: revenue - cost on non-return lines.
    profit_month = _profit(session, branch_id, month_start, TODAY)

    return {
        "as_of": TODAY.isoformat(),
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
            func.date(m.Sale.sale_date) >= start,
            func.date(m.Sale.sale_date) <= end,
        )
    )
    revenue, cost = session.execute(stmt).one()
    return money(float(revenue) - float(cost))


def daily_sales(session: Session, branch_id: int | None = None, days: int = 30) -> list[dict]:
    """Revenue + bill count per day for the last ``days`` (for the trend chart)."""
    start = TODAY - timedelta(days=days - 1)
    stmt = (
        select(
            func.date(m.Sale.sale_date).label("d"),
            func.count().label("bills"),
            func.coalesce(func.sum(m.Sale.total_net), 0).label("revenue"),
        )
        .where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            func.date(m.Sale.sale_date) >= start,
        )
        .group_by(func.date(m.Sale.sale_date))
        .order_by(func.date(m.Sale.sale_date))
    )
    rows = {str(r.d): (r.bills, money(r.revenue)) for r in session.execute(stmt)}
    # Fill gaps so the chart has a continuous axis.
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        bills, revenue = rows.get(d, (0, 0.0))
        out.append({"date": d, "bills": bills, "revenue": revenue})
    return out


def top_products(session: Session, branch_id: int | None = None, days: int = 30, limit: int = 10) -> list[dict]:
    start = TODAY - timedelta(days=days - 1)
    stmt = (
        select(
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
            func.date(m.Sale.sale_date) >= start,
        )
        .group_by(m.Product.product_id, m.Product.name_ar, m.Product.name_en)
        .order_by(func.sum(m.SaleLine.total_sell).desc())
        .limit(limit)
    )
    return [
        {"name_ar": r.name_ar, "name_en": r.name_en, "units": money(r.units), "revenue": money(r.revenue)}
        for r in session.execute(stmt)
    ]


def hourly_sales(session: Session, branch_id: int | None = None) -> list[dict]:
    """Peak-hours for the most recent active day. Bucketed in Python so it is
    dialect-agnostic (SQLite dev + SQL Server prod behave identically)."""
    target = session.execute(
        select(func.max(func.date(m.Sale.sale_date))).where(branch_filter(m.Sale, branch_id))
    ).scalar_one()
    if target is None:
        return []
    rows = session.execute(
        select(m.Sale.sale_date, m.Sale.total_net).where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            func.date(m.Sale.sale_date) == target,
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


def cashier_performance(session: Session, branch_id: int | None = None, days: int = 30) -> list[dict]:
    start = TODAY - timedelta(days=days - 1)
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
            func.date(m.Sale.sale_date) >= start,
        )
        .group_by(m.Employee.employee_id, m.Employee.name_ar)
        .order_by(func.sum(m.Sale.total_net).desc())
    )
    return [{"cashier": r.name_ar, "bills": r.bills, "revenue": money(r.revenue)} for r in session.execute(stmt)]
