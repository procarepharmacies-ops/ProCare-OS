"""Owner intelligence: daily report, staff productivity, footfall conversion.

All analysis here is computed from data ProCare actually has — POS sale
timestamps and door-counter events pushed by the NVR (``footfall_events``).
No video is processed by ProCare itself: the NVR (or any camera people-counter)
POSTs one event per person crossing the door line, and everything else
(conversion rate, peak hours, staffing hints) is derived arithmetic. That keeps
the "AI analysis" honest: every number below is reproducible from the tables.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services import tasks as tasks_svc
from app.services.common import money


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min)
    return start, start + timedelta(days=1)


def record_footfall(session: Session, branch_id: int, direction: str = "in", count: int = 1, source: str | None = None, ts: datetime | None = None) -> dict:
    """Insert ``count`` door events (NVR line-crossing counters often batch)."""
    if direction not in ("in", "out"):
        raise ValueError("direction must be 'in' or 'out'")
    count = max(1, min(int(count), 500))  # sanity clamp against a runaway NVR
    for _ in range(count):
        session.add(m.FootfallEvent(branch_id=branch_id, direction=direction, source=source, ts=ts or datetime.now()))
    session.commit()
    return {"recorded": count, "branch_id": branch_id, "direction": direction}


def footfall_summary(session: Session, branch_id: int | None = None, days: int = 14) -> dict:
    """Daily visitors-in / bills / conversion for the last ``days`` days."""
    since = datetime.combine(datetime.now().date() - timedelta(days=days - 1), time.min)

    ff = select(m.FootfallEvent).where(m.FootfallEvent.ts >= since, m.FootfallEvent.direction == "in")
    sales_q = select(m.Sale).where(m.Sale.sale_date >= since, m.Sale.is_return == False)  # noqa: E712
    if branch_id:
        ff = ff.where(m.FootfallEvent.branch_id == branch_id)
        sales_q = sales_q.where(m.Sale.branch_id == branch_id)

    visitors_by_day: dict[str, int] = {}
    for ev in session.scalars(ff):
        key = ev.ts.date().isoformat()
        visitors_by_day[key] = visitors_by_day.get(key, 0) + 1

    bills_by_day: dict[str, int] = {}
    for s in session.scalars(sales_q):
        key = s.sale_date.date().isoformat()
        bills_by_day[key] = bills_by_day.get(key, 0) + 1

    series = []
    for i in range(days):
        d = (datetime.now().date() - timedelta(days=days - 1 - i)).isoformat()
        v, b = visitors_by_day.get(d, 0), bills_by_day.get(d, 0)
        series.append(
            {
                "date": d,
                "visitors": v,
                "bills": b,
                # Conversion only means something once the counter is feeding us.
                "conversion_pct": round(100 * b / v, 1) if v else None,
            }
        )

    total_v = sum(r["visitors"] for r in series)
    total_b = sum(r["bills"] for r in series)
    # Period conversion only counts days the counter actually reported —
    # otherwise bills from pre-counter days inflate the rate absurdly.
    counted = [r for r in series if r["visitors"] > 0]
    cv = sum(r["visitors"] for r in counted)
    cb = sum(r["bills"] for r in counted)
    return {
        "days": days,
        "series": series,
        "total_visitors": total_v,
        "total_bills": total_b,
        "conversion_pct": round(100 * cb / cv, 1) if cv else None,
        "counter_connected": total_v > 0,
    }


def productivity(session: Session, branch_id: int | None = None, days: int = 30) -> dict:
    """Per-employee activity profile from POS timestamps.

    For each cashier: bills, revenue, average bill, the hour-by-hour histogram
    of when they actually ring sales (their real working rhythm), their peak
    hour, and idle-hour hints. This is the honest, data-backed version of
    "employee movement and time analysis" — it measures output at the till,
    not camera tracking.
    """
    since = datetime.combine(datetime.now().date() - timedelta(days=days - 1), time.min)
    q = select(m.Sale).where(m.Sale.sale_date >= since, m.Sale.is_return == False)  # noqa: E712
    if branch_id:
        q = q.where(m.Sale.branch_id == branch_id)

    names = dict(session.execute(select(m.Employee.employee_id, m.Employee.name_ar)).all())

    per: dict[int, dict] = {}
    hourly_all = [0] * 24
    for s in session.scalars(q):
        cid = s.cashier_id or 0
        rec = per.setdefault(cid, {"bills": 0, "revenue": 0.0, "hours": [0] * 24, "days": set()})
        rec["bills"] += 1
        rec["revenue"] += float(s.total_net or 0)
        h = s.sale_date.hour
        rec["hours"][h] += 1
        hourly_all[h] += 1
        rec["days"].add(s.sale_date.date())

    employees = []
    for cid, rec in sorted(per.items(), key=lambda kv: -kv[1]["revenue"]):
        peak_hour = max(range(24), key=lambda h: rec["hours"][h]) if rec["bills"] else None
        active_days = len(rec["days"]) or 1
        employees.append(
            {
                "employee_id": cid,
                "name": names.get(cid, "—"),
                "bills": rec["bills"],
                "revenue": money(rec["revenue"]),
                "avg_bill": money(rec["revenue"] / rec["bills"]) if rec["bills"] else 0,
                "bills_per_active_day": round(rec["bills"] / active_days, 1),
                "active_days": active_days,
                "peak_hour": peak_hour,
                "hourly": rec["hours"],
            }
        )

    busiest = max(range(24), key=lambda h: hourly_all[h]) if any(hourly_all) else None
    quietest_open = None
    open_hours = [h for h in range(24) if hourly_all[h] > 0]
    if open_hours:
        quietest_open = min(open_hours, key=lambda h: hourly_all[h])

    return {
        "days": days,
        "employees": employees,
        "hourly_total": hourly_all,
        "busiest_hour": busiest,
        "quietest_open_hour": quietest_open,
    }


def daily_report(session: Session, branch_id: int | None = None, on: date | None = None) -> dict:
    """The owner's end-of-day sheet: sales, returns, tasks, footfall, alerts."""
    on = on or datetime.now().date()
    start, end = _day_bounds(on)

    sales_q = select(m.Sale).where(m.Sale.sale_date >= start, m.Sale.sale_date < end)
    if branch_id:
        sales_q = sales_q.where(m.Sale.branch_id == branch_id)

    bills = returns = 0
    revenue = returns_value = 0.0
    for s in session.scalars(sales_q):
        if s.is_return:
            returns += 1
            returns_value += float(s.total_net or 0)
        else:
            bills += 1
            revenue += float(s.total_net or 0)

    ff_q = select(func.count()).select_from(m.FootfallEvent).where(
        m.FootfallEvent.ts >= start, m.FootfallEvent.ts < end, m.FootfallEvent.direction == "in"
    )
    if branch_id:
        ff_q = ff_q.where(m.FootfallEvent.branch_id == branch_id)
    visitors = int(session.scalar(ff_q) or 0)

    from app.services import alerts as alerts_svc

    low_stock = len(alerts_svc.low_stock(session, branch_id, limit=500))
    expiry = alerts_svc.expiry_risk(session, branch_id, horizon_days=30)["counts"]

    return {
        "date": on.isoformat(),
        "branch_id": branch_id or 0,
        "sales": {"bills": bills, "revenue": money(revenue), "returns": returns, "returns_value": money(returns_value)},
        "visitors": visitors,
        "conversion_pct": round(100 * bills / visitors, 1) if visitors else None,
        "tasks": tasks_svc.summary(session, branch_id=branch_id),
        "alerts": {"low_stock": low_stock, "expiring_7d": expiry["d7"], "expiring_30d": expiry["d30"], "expired": expiry["expired"]},
    }
