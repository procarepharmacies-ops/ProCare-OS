"""Dashboard KPI queries return consistent, branch-aware figures."""
from app import queries


def test_summary_has_all_kpis():
    s = queries.dashboard_summary("ALL")
    k = s["kpis"]
    for key in ["sales_today", "sales_month", "profit_month", "low_stock_items",
                "expiring_30_days", "expiring_7_days", "debtors_over_limit",
                "vendor_payables", "bills_today"]:
        assert key in k
    assert s["wired_to_db"] is True


def test_branch_filter_partitions_sales():
    total = queries.dashboard_summary("ALL")["kpis"]["sales_month"]
    main = queries.dashboard_summary("MAIN")["kpis"]["sales_month"]
    els = queries.dashboard_summary("ELSANTA")["kpis"]["sales_month"]
    # Per-branch months should sum to the consolidated month (within rounding).
    assert abs((main + els) - total) < 1.0
    assert main > 0 and els > 0


def test_daily_sales_length_and_order():
    series = queries.daily_sales("ALL", days=30)
    assert 1 <= len(series) <= 30
    days = [r["sale_day"] for r in series]
    assert days == sorted(days)  # ascending


def test_top_products_sorted_desc():
    rows = queries.top_products("ALL", days=30, limit=5)
    revs = [r["revenue"] for r in rows]
    assert revs == sorted(revs, reverse=True)
    assert len(rows) <= 5


def test_profit_is_revenue_minus_cost():
    p = queries.profit("ALL")
    assert round(p["revenue"] - p["cost"], 2) == p["gross_profit"]


def test_stock_lookup_is_fefo_and_available():
    rows = queries.stock_lookup("Panadol", "ALL")
    assert len(rows) > 0
    exps = [r["exp_date"] for r in rows]
    assert exps == sorted(exps)            # FEFO
    assert all(r["available_qty"] > 0 for r in rows)
