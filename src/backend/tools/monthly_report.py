"""Monthly performance report + separate credit-sales (بيع آجل) invoice report.

Usage (from src/backend, against the DB ProCare is configured for):
    python tools/monthly_report.py --year 2026 --month 9 [--branch-id N] [--out DIR]

Writes, per run (READ-ONLY on the DB, SELECT only):
    performance_YYYY-MM.html   monthly performance (KPIs, daily trend, branches,
                               cashiers, top products, vs previous month)
    credit_sales_YYYY-MM.html  every credit invoice in the month, by customer
    credit_sales_YYYY-MM.csv   same rows, for Excel

Credit definition: eStock-mirrored sales do NOT carry ``is_credit`` (ETL does
not set it), so an invoice counts as credit when ``is_credit`` is true OR it
is a non-return invoice for a registered customer whose cash+card paid is below
its net by more than ``TOLERANCE`` (the unpaid part went on the customer
account). Walk-in (no customer) invoices are never credit.

SQL Server 2008 safe: no OFFSET, no date-part functions — day grouping is done
in Python over a month-bounded SELECT.
"""
from __future__ import annotations

import argparse
import csv
import html
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import models as m  # noqa: E402
from app.db.base import SessionLocal  # noqa: E402

TOLERANCE = 0.5  # currency units; ignores rounding dust on "fully paid" bills


def _bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    end = datetime(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return start, end


def _f(v) -> float:
    return float(v or 0)


def _fmt(v: float) -> str:
    return f"{v:,.2f}"


def _is_credit(s) -> bool:
    if s.is_return or s.customer_id is None:
        return False
    if s.is_credit:
        return True
    paid = _f(s.cash_paid) - _f(s.change_given) + _f(s.card_paid)
    return _f(s.total_net) - paid > TOLERANCE


def collect(session, year: int, month: int, branch_id: int | None) -> dict:
    start, end = _bounds(year, month)
    pstart, _ = _bounds(year - (month == 1), 12 if month == 1 else month - 1)

    def sales(a: datetime, b: datetime):
        q = select(m.Sale).where(m.Sale.sale_date >= a, m.Sale.sale_date < b)
        if branch_id:
            q = q.where(m.Sale.branch_id == branch_id)
        return list(session.scalars(q.order_by(m.Sale.sale_date, m.Sale.sale_id)))

    cur, prev = sales(start, end), sales(pstart, start)
    names = {b.branch_id: (b.name_ar or b.name_en) for b in session.scalars(select(m.Branch))}
    emps = {e.employee_id: (e.name_ar or e.name_en) for e in session.scalars(select(m.Employee))}
    custs = {c.customer_id: c for c in session.scalars(select(m.Customer))}

    def kpis(rows: list) -> dict:
        ok = [s for s in rows if not s.is_return]
        rets = [s for s in rows if s.is_return]
        rev = sum(_f(s.total_net) for s in ok)
        ret = sum(_f(s.total_net) for s in rets)
        credit = [s for s in ok if _is_credit(s)]
        return {
            "revenue": rev, "returns": ret, "net_revenue": rev - ret,
            "bills": len(ok), "returns_count": len(rets),
            "avg_bill": rev / len(ok) if ok else 0.0,
            "discount": sum(_f(s.total_discount) for s in ok),
            "cash": sum(_f(s.cash_paid) - _f(s.change_given) for s in ok),
            "card": sum(_f(s.card_paid) for s in ok),
            "credit_value": sum(_f(s.total_net) for s in credit),
            "credit_bills": len(credit),
        }

    # COGS / gross profit from sale lines (same basis as services/performance).
    ids = [s.sale_id for s in cur if not s.is_return]
    cogs = units = 0.0
    prod: dict[int, dict] = defaultdict(lambda: {"units": 0.0, "revenue": 0.0})
    for i in range(0, len(ids), 500):  # chunked IN() — no OFFSET, 2008-safe
        for ln in session.scalars(select(m.SaleLine).where(m.SaleLine.sale_id.in_(ids[i:i + 500]))):
            a = _f(ln.amount)
            cogs += a * _f(ln.buy_price)
            units += a
            prod[ln.product_id]["units"] += a
            prod[ln.product_id]["revenue"] += a * _f(ln.sell_price)
    pnames = {p.product_id: (p.name_ar or p.name_en) for p in session.scalars(
        select(m.Product).where(m.Product.product_id.in_(list(prod) or [0])))}

    k, pk = kpis(cur), kpis(prev)
    k["cogs"], k["units"] = cogs, units
    k["gross_profit"] = k["revenue"] - cogs
    k["margin_pct"] = k["gross_profit"] / k["revenue"] * 100 if k["revenue"] else 0.0

    daily: dict[int, float] = defaultdict(float)
    by_branch: dict[str, dict] = defaultdict(lambda: {"revenue": 0.0, "bills": 0})
    by_cashier: dict[str, dict] = defaultdict(lambda: {"revenue": 0.0, "bills": 0})
    for s in cur:
        if s.is_return:
            continue
        daily[s.sale_date.day] += _f(s.total_net)
        b = by_branch[names.get(s.branch_id, str(s.branch_id))]
        b["revenue"] += _f(s.total_net); b["bills"] += 1
        c = by_cashier[emps.get(s.cashier_id, "—")]
        c["revenue"] += _f(s.total_net); c["bills"] += 1

    credit_rows = []
    for s in cur:
        if not _is_credit(s):
            continue
        paid = _f(s.cash_paid) - _f(s.change_given) + _f(s.card_paid)
        c = custs.get(s.customer_id)
        credit_rows.append({
            "sale_id": s.sale_id, "date": s.sale_date.strftime("%Y-%m-%d %H:%M"),
            "branch": names.get(s.branch_id, ""),
            "customer": (c.name_ar or c.name_en) if c else str(s.customer_id),
            "cashier": emps.get(s.cashier_id, "—"),
            "net": _f(s.total_net), "paid": paid, "credit": _f(s.total_net) - paid,
        })
    return {
        "year": year, "month": month, "kpis": k, "prev": pk, "daily": dict(daily),
        "branches": dict(by_branch), "cashiers": dict(by_cashier),
        "top_products": sorted(
            ({"name": pnames.get(p, str(p)), **v} for p, v in prod.items()),
            key=lambda r: r["revenue"], reverse=True)[:15],
        "credit": credit_rows,
    }


_CSS = ("body{font-family:Cairo,Tahoma,Arial,sans-serif;margin:24px;color:#222}"
        "h1{color:#3d4f1f}h2{border-bottom:2px solid #b8860b;padding-bottom:4px}"
        "table{border-collapse:collapse;width:100%;margin:8px 0 20px}"
        "th,td{border:1px solid #ccc;padding:6px 8px;text-align:right}"
        "th{background:#eef1e4}.n{direction:ltr;text-align:left}"
        ".kpi{display:inline-block;margin:4px;padding:10px 16px;background:#f6f4ea;border-radius:8px}"
        ".kpi b{display:block;font-size:1.3em}")


def _page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
            f"<title>{html.escape(title)}</title><style>{_CSS}</style></head>"
            f"<body><h1>{html.escape(title)}</h1>{body}</body></html>")


def _table(heads: list[str], rows: list[list], num_from: int = 1) -> str:
    th = "".join(f"<th>{html.escape(h)}</th>" for h in heads)
    tr = "".join(
        "<tr>" + "".join(
            f'<td class="{"n" if i >= num_from else ""}">{html.escape(str(c))}</td>'
            for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table><tr>{th}</tr>{tr}</table>"


def _delta(cur: float, prev: float) -> str:
    return "—" if not prev else f"{(cur - prev) / prev * 100:+.1f}%"


def render_performance(d: dict) -> str:
    k, p = d["kpis"], d["prev"]
    tiles = [("صافي المبيعات", k["net_revenue"], p["net_revenue"]),
             ("إجمالي المبيعات", k["revenue"], p["revenue"]),
             ("عدد الفواتير", k["bills"], p["bills"]),
             ("متوسط الفاتورة", k["avg_bill"], p["avg_bill"])]
    kp = "".join(f'<div class="kpi">{n}<b>{_fmt(float(v))}</b>مقارنة بالشهر السابق: {_delta(v, pv)}</div>'
                 for n, v, pv in tiles)
    kp += "".join(f'<div class="kpi">{n}<b>{v}</b></div>' for n, v in [
        ("إجمالي الربح", _fmt(k["gross_profit"])), ("هامش الربح %", f'{k["margin_pct"]:.1f}'),
        ("المرتجعات", f'{_fmt(k["returns"])} ({k["returns_count"]})'),
        ("الخصومات", _fmt(k["discount"])),
        ("نقدي / فيزا", f'{_fmt(k["cash"])} / {_fmt(k["card"])}'),
        ("بيع آجل", f'{_fmt(k["credit_value"])} ({k["credit_bills"]} فاتورة)')])
    body = f"<div>{kp}</div><h2>المبيعات اليومية</h2>" + _table(
        ["اليوم", "المبيعات"], [[day, _fmt(v)] for day, v in sorted(d["daily"].items())])
    body += "<h2>حسب الفرع</h2>" + _table(["الفرع", "المبيعات", "الفواتير"], [
        [n, _fmt(v["revenue"]), v["bills"]] for n, v in d["branches"].items()])
    body += "<h2>حسب الكاشير</h2>" + _table(["الكاشير", "المبيعات", "الفواتير"], [
        [n, _fmt(v["revenue"]), v["bills"]]
        for n, v in sorted(d["cashiers"].items(), key=lambda x: -x[1]["revenue"])])
    body += "<h2>أعلى ١٥ صنف</h2>" + _table(["الصنف", "الكمية", "القيمة"], [
        [r["name"], _fmt(r["units"]), _fmt(r["revenue"])] for r in d["top_products"]])
    return _page(f'تقرير الأداء — {d["month"]:02d}/{d["year"]}', body)


def render_credit(d: dict) -> str:
    rows = d["credit"]
    by_cust: dict[str, dict] = defaultdict(lambda: {"n": 0, "net": 0.0, "credit": 0.0})
    for r in rows:
        c = by_cust[r["customer"]]
        c["n"] += 1; c["net"] += r["net"]; c["credit"] += r["credit"]
    body = (f'<div class="kpi">عدد الفواتير الآجلة<b>{len(rows)}</b></div>'
            f'<div class="kpi">إجمالي الآجل<b>{_fmt(sum(r["credit"] for r in rows))}</b></div>'
            "<h2>ملخص حسب العميل</h2>" + _table(["العميل", "الفواتير", "إجمالي الفواتير", "المبلغ الآجل"], [
                [n, v["n"], _fmt(v["net"]), _fmt(v["credit"])]
                for n, v in sorted(by_cust.items(), key=lambda x: -x[1]["credit"])])
            + "<h2>تفاصيل الفواتير</h2>" + _table(
                ["رقم الفاتورة", "التاريخ", "الفرع", "العميل", "الكاشير", "الصافي", "المدفوع", "الآجل"],
                [[r["sale_id"], r["date"], r["branch"], r["customer"], r["cashier"],
                  _fmt(r["net"]), _fmt(r["paid"]), _fmt(r["credit"])] for r in rows], num_from=5))
    return _page(f'تقرير فواتير البيع الآجل — {d["month"]:02d}/{d["year"]}', body)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--branch-id", type=int, default=None)
    ap.add_argument("--out", default=".tmp/reports")
    a = ap.parse_args()
    if not 1 <= a.month <= 12:
        print("ERROR: --month must be 1..12", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as session:
        d = collect(session, a.year, a.month, a.branch_id)
    tag = f"{a.year}-{a.month:02d}"
    (out / f"performance_{tag}.html").write_text(render_performance(d), encoding="utf-8")
    (out / f"credit_sales_{tag}.html").write_text(render_credit(d), encoding="utf-8")
    with (out / f"credit_sales_{tag}.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["sale_id", "date", "branch", "customer", "cashier", "net", "paid", "credit"])
        w.writeheader()
        w.writerows(d["credit"])
    print(f"OK {tag}: {d['kpis']['bills']} bills, {len(d['credit'])} credit -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
