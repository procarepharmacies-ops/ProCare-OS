"""Read-only dashboard / KPI queries over ProCare's own clean schema.

These are the Phase-1 reporting surface — the 10 KPI patterns seeded in
``sql/dashboard-queries.sql`` (originally written against eStock) re-expressed
against the clean ProCare schema and curated views. Every figure already obeys
the data-quality rules (returns excluded, NON-NULL ``sale_date``, available =
``amount > 0`` and not expired, FEFO).

Every function is branch-aware: ``branch`` may be ``"ALL"``, a branch code
(``"MAIN"`` / ``"ELSANTA"``), or a numeric ``branch_id`` — matching the UI's
Main / Elsanta / All switcher. Nothing here writes.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.db import get_db


# -- branch / date helpers ---------------------------------------------------
def _resolve_branch_id(branch) -> int | None:
    """Map 'ALL'|code|id -> branch_id (or None for all branches)."""
    if branch is None:
        return None
    s = str(branch).strip()
    if s == "" or s.upper() == "ALL":
        return None
    if s.isdigit():
        return int(s)
    row = get_db().query_one(
        "SELECT branch_id FROM branches WHERE UPPER(code) = ?", (s.upper(),)
    )
    return row["branch_id"] if row else None


def _branch_clause(branch, column="branch_id"):
    """Return (sql_fragment, params) for an optional branch filter."""
    bid = _resolve_branch_id(branch)
    if bid is None:
        return "", ()
    return f" AND {column} = ?", (bid,)


def _month_bounds(today: date | None = None):
    today = today or date.today()
    first_this = today.replace(day=1)
    last_prev_end = first_this - timedelta(days=1)
    first_prev = last_prev_end.replace(day=1)
    return first_this.isoformat(), first_prev.isoformat(), last_prev_end.isoformat(), today.isoformat()


# -- headline KPIs -----------------------------------------------------------
def dashboard_summary(branch="ALL") -> dict:
    db = get_db()
    bc, bp = _branch_clause(branch, "branch_id")
    first_this, first_prev, last_prev_end, today = _month_bounds()

    today_row = db.query_one(
        f"""SELECT COUNT(*) AS bills, COALESCE(SUM(total_net),0) AS revenue,
                   COALESCE(SUM(cash_paid),0) AS cash
            FROM sales
            WHERE is_return = 0 AND date(sale_date) = ?{bc}""",
        (today, *bp),
    )
    month_row = db.query_one(
        f"""SELECT COALESCE(SUM(total_net),0) AS revenue, COUNT(*) AS bills
            FROM sales
            WHERE is_return = 0 AND date(sale_date) >= ?{bc}""",
        (first_this, *bp),
    )
    last_month_row = db.query_one(
        f"""SELECT COALESCE(SUM(total_net),0) AS revenue
            FROM sales
            WHERE is_return = 0 AND date(sale_date) BETWEEN ? AND ?{bc}""",
        (first_prev, last_prev_end, *bp),
    )
    profit_row = db.query_one(
        f"""SELECT COALESCE(SUM(total_sell),0) AS revenue,
                   COALESCE(SUM(amount * buy_price),0) AS cost
            FROM sale_lines sl
            JOIN sales s ON s.sale_id = sl.sale_id
            WHERE s.is_return = 0 AND sl.is_return = 0
              AND date(s.sale_date) >= ?{_branch_clause(branch, 's.branch_id')[0]}""",
        (first_this, *_branch_clause(branch, "s.branch_id")[1]),
    )

    low_stock = db.query_one(
        f"SELECT COUNT(*) AS n FROM vw_low_stock WHERE 1=1{bc}", bp
    )["n"]
    exp30 = db.query_one(
        f"SELECT COUNT(*) AS n FROM vw_expiry_risk WHERE days_to_expiry BETWEEN 0 AND 30{bc}", bp
    )["n"]
    exp7 = db.query_one(
        f"SELECT COUNT(*) AS n FROM vw_expiry_risk WHERE days_to_expiry BETWEEN 0 AND 7{bc}", bp
    )["n"]
    expired = db.query_one(
        f"SELECT COUNT(*) AS n FROM vw_expiry_risk WHERE days_to_expiry < 0{bc}", bp
    )["n"]
    # debtors / payables are branch-independent ledgers in this model
    debtors = db.query_one(
        "SELECT COUNT(*) AS n, COALESCE(SUM(balance),0) AS total FROM vw_customer_debtors"
    )
    over_limit = db.query_one(
        "SELECT COUNT(*) AS n FROM vw_customer_debtors WHERE over_limit = 1"
    )["n"]
    payables = db.query_one(
        "SELECT COALESCE(SUM(amount_owed),0) AS total FROM vw_vendor_payables"
    )["total"]

    this_m = round(month_row["revenue"], 2)
    last_m = round(last_month_row["revenue"], 2)
    delta_pct = round((this_m - last_m) / last_m * 100, 1) if last_m else None
    bills_today = today_row["bills"]
    revenue_today = round(today_row["revenue"], 2)

    return {
        "branch": str(branch).upper(),
        "as_of": today,
        "wired_to_db": True,
        "source": get_db().mode,
        "kpis": {
            "sales_today": revenue_today,
            "bills_today": bills_today,
            "avg_basket_today": round(revenue_today / bills_today, 2) if bills_today else 0,
            "cash_today": round(today_row["cash"], 2),
            "sales_month": this_m,
            "sales_last_month": last_m,
            "month_delta_pct": delta_pct,
            "profit_month": round(profit_row["revenue"] - profit_row["cost"], 2),
            "low_stock_items": low_stock,
            "expiring_30_days": exp30,
            "expiring_7_days": exp7,
            "expired_in_stock": expired,
            "debtors_count": debtors["n"],
            "debtors_total": round(debtors["total"], 2),
            "debtors_over_limit": over_limit,
            "vendor_payables": round(payables, 2),
        },
    }


# -- detail reports ----------------------------------------------------------
def daily_sales(branch="ALL", days=30) -> list[dict]:
    db = get_db()
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    bc, bp = _branch_clause(branch, "branch_id")
    rows = db.query(
        f"""SELECT date(sale_date) AS sale_day, COUNT(*) AS bills,
                   ROUND(SUM(total_net),2) AS revenue
            FROM sales
            WHERE is_return = 0 AND date(sale_date) >= ?{bc}
            GROUP BY date(sale_date)
            ORDER BY sale_day ASC""",
        (start, *bp),
    )
    return rows


def top_products(branch="ALL", days=30, limit=10) -> list[dict]:
    db = get_db()
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    bc, bp = _branch_clause(branch, "s.branch_id")
    return db.query(
        f"""SELECT p.name_ar AS product_name_ar, p.name_en AS product_name_en,
                   ROUND(SUM(sl.amount),2) AS units_sold,
                   ROUND(SUM(sl.total_sell),2) AS revenue,
                   ROUND(SUM(sl.total_sell - sl.amount*sl.buy_price),2) AS profit
            FROM sale_lines sl
            JOIN sales s    ON s.sale_id = sl.sale_id
            JOIN products p ON p.product_id = sl.product_id
            WHERE s.is_return = 0 AND sl.is_return = 0 AND date(s.sale_date) >= ?{bc}
            GROUP BY p.product_id, p.name_ar, p.name_en
            ORDER BY revenue DESC
            LIMIT ?""",
        (start, *bp, limit),
    )


def expiry_report(branch="ALL", horizon_days=30, limit=100) -> list[dict]:
    db = get_db()
    bc, bp = _branch_clause(branch, "branch_id")
    return db.query(
        f"""SELECT product_name_ar, product_name_en, exp_date,
                   ROUND(qty_remaining,2) AS qty_remaining,
                   ROUND(expected_loss,2) AS expected_loss, days_to_expiry, branch_id
            FROM vw_expiry_risk
            WHERE days_to_expiry <= ?{bc}
            ORDER BY days_to_expiry ASC, expected_loss DESC
            LIMIT ?""",
        (horizon_days, *bp, limit),
    )


def low_stock(branch="ALL", limit=100) -> list[dict]:
    db = get_db()
    bc, bp = _branch_clause(branch, "branch_id")
    return db.query(
        f"""SELECT product_name_ar, product_name_en,
                   ROUND(qty_on_hand,2) AS qty_on_hand, min_stock, branch_id
            FROM vw_low_stock
            WHERE 1=1{bc}
            ORDER BY qty_on_hand ASC
            LIMIT ?""",
        (*bp, limit),
    )


def debtors(limit=20) -> list[dict]:
    return get_db().query(
        """SELECT customer_name_ar, customer_name_en, mobile,
                  ROUND(balance,2) AS balance, credit_limit,
                  ROUND(over_limit_by,2) AS over_limit_by, over_limit
           FROM vw_customer_debtors
           ORDER BY balance DESC
           LIMIT ?""",
        (limit,),
    )


def vendor_payables(limit=20) -> list[dict]:
    return get_db().query(
        """SELECT vendor_name_ar, vendor_name_en, ROUND(amount_owed,2) AS amount_owed
           FROM vw_vendor_payables
           ORDER BY amount_owed DESC
           LIMIT ?""",
        (limit,),
    )


def hourly_sales(branch="ALL", day=None) -> list[dict]:
    db = get_db()
    day = day or date.today().isoformat()
    bc, bp = _branch_clause(branch, "branch_id")
    # strftime('%H', ...) is SQLite; on SQL Server swap to DATEPART(hour, ...)
    return db.query(
        f"""SELECT CAST(strftime('%H', sale_date) AS INTEGER) AS hour_of_day,
                   COUNT(*) AS bills, ROUND(SUM(total_net),2) AS revenue
            FROM sales
            WHERE is_return = 0 AND date(sale_date) = ?{bc}
            GROUP BY hour_of_day
            ORDER BY hour_of_day ASC""",
        (day, *bp),
    )


def cashier_performance(branch="ALL", day=None) -> list[dict]:
    db = get_db()
    day = day or date.today().isoformat()
    bc, bp = _branch_clause(branch, "branch_id")
    return db.query(
        f"""SELECT cashier_name_ar, cashier_name_en, bills, ROUND(revenue,2) AS revenue
            FROM vw_cashier_performance
            WHERE sale_day = ?{bc}
            ORDER BY revenue DESC""",
        (day, *bp),
    )


def profit(branch="ALL", date_from=None, date_to=None) -> dict:
    db = get_db()
    date_to = date_to or date.today().isoformat()
    date_from = date_from or (date.today() - timedelta(days=29)).isoformat()
    bc, bp = _branch_clause(branch, "s.branch_id")
    row = db.query_one(
        f"""SELECT ROUND(COALESCE(SUM(sl.total_sell),0),2) AS revenue,
                   ROUND(COALESCE(SUM(sl.amount*sl.buy_price),0),2) AS cost
            FROM sale_lines sl
            JOIN sales s ON s.sale_id = sl.sale_id
            WHERE s.is_return = 0 AND sl.is_return = 0
              AND date(s.sale_date) BETWEEN ? AND ?{bc}""",
        (date_from, date_to, *bp),
    )
    revenue = row["revenue"]
    cost = row["cost"]
    return {
        "date_from": date_from,
        "date_to": date_to,
        "revenue": revenue,
        "cost": cost,
        "gross_profit": round(revenue - cost, 2),
        "margin_pct": round((revenue - cost) / revenue * 100, 1) if revenue else None,
    }


def stock_lookup(query: str, branch="ALL", limit=20) -> list[dict]:
    """FEFO batch lookup for a product by name / code / barcode."""
    db = get_db()
    bc, bp = _branch_clause(branch, "sb.branch_id")
    like = f"%{query}%"
    return db.query(
        f"""SELECT p.name_ar AS product_name_ar, p.name_en AS product_name_en,
                   sb.branch_id, sb.exp_date, ROUND(sb.amount,2) AS available_qty,
                   sb.sell_price, sb.buy_price
            FROM stock_batches sb
            JOIN products p ON p.product_id = sb.product_id
            LEFT JOIN product_barcodes pb ON pb.product_id = p.product_id
            WHERE sb.amount > 0
              AND (p.has_expiry = 0 OR sb.exp_date IS NULL OR sb.exp_date > date('now'))
              AND (p.name_ar LIKE ? OR p.name_en LIKE ? OR p.code LIKE ? OR pb.barcode = ?){bc}
            GROUP BY sb.batch_id
            ORDER BY sb.exp_date ASC
            LIMIT ?""",
        (like, like, like, query, *bp, limit),
    )
