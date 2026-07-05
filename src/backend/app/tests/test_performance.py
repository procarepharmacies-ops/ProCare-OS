"""Performance-over-time, audit and supplier-purchasing tests.

Exercises the service directly against the seeded 5-year dataset and the HTTP
endpoints through the app. The same code runs on SQL Server in production.
"""
from __future__ import annotations

from app.services import performance as perf


# --- service: 5-year overview ----------------------------------------------
def test_overview_has_five_years_and_growth(session):
    ov = perf.overview(session, years=5)
    assert ov["years"] == 5
    assert len(ov["yearly"]) == 5
    # Years are contiguous and end at the "today" anchor year.
    yrs = [y["year"] for y in ov["yearly"]]
    assert yrs == list(range(yrs[0], yrs[0] + 5))
    # Every year has real activity, revenue and invoices.
    assert all(y["invoices"] > 0 and y["revenue"] > 0 for y in ov["yearly"])
    # Gross profit reconciles: revenue - cogs.
    for y in ov["yearly"]:
        assert abs(y["gross_profit"] - (y["revenue"] - y["cogs"])) < 0.01
    # Growth is reported from the second year on (None for the first).
    assert ov["yearly"][0]["revenue_growth_pct"] is None
    assert any(y["revenue_growth_pct"] is not None for y in ov["yearly"][1:])
    # Monthly series present for charting.
    assert len(ov["monthly"]) >= 12


def test_overview_snapshot_valuation(session):
    snap = perf.overview(session)["snapshot"]
    assert snap["stock_on_hand_units"] > 0
    assert snap["stock_value_at_retail"] >= snap["stock_value_at_cost"] > 0
    assert snap["registered_customers"] > 0
    assert snap["payables_to_vendors"] >= 0


def test_overview_branch_scoped_is_subset(session):
    total = perf.overview(session)["totals"]["invoices"]
    b1 = perf.overview(session, branch_id=1)["totals"]["invoices"]
    b2 = perf.overview(session, branch_id=2)["totals"]["invoices"]
    assert b1 > 0 and b2 > 0
    assert b1 + b2 == total  # every sale belongs to exactly one branch


# --- service: audit ---------------------------------------------------------
def test_audit_reports_clean_stock_and_span(session):
    au = perf.audit(session)
    assert au["overall"] in ("ok", "warn")  # seeded data has no hard failures
    checks = {c["key"]: c for c in au["checks"]}
    # The clean-schema guarantees hold: no negative stock, no orphan/zero-line.
    assert checks["negative_stock"]["status"] == "ok"
    assert checks["orphan_batches"]["status"] == "ok"
    assert checks["zero_line_sales"]["status"] == "ok"
    # Data span covers multiple years.
    span = au["data_span"]
    assert span["total_invoices"] > 0 and span["total_purchases"] > 0
    assert span["first_sale"][:4] != span["last_sale"][:4]


# --- service: supplier purchasing ------------------------------------------
def test_vendor_purchasing_pharmaoverseas(session):
    vp = perf.vendor_purchasing(session, "pharmaoverseas")
    assert vp["found"] is True
    assert "PharmaOverseas" in (vp["vendor"]["name_en"] or "")
    assert vp["total_spend"] > 0 and vp["total_orders"] > 0
    assert 0 < vp["share_of_purchasing_pct"] <= 100
    # Yearly breakdown + a non-empty vendor ranking led by the queried supplier.
    assert len(vp["yearly"]) == 5
    assert vp["vendor_ranking"][0]["name_en"] == "PharmaOverseas"
    # Shares across all vendors sum to ~100%.
    assert abs(sum(r["share_pct"] for r in vp["vendor_ranking"]) - 100) < 1.0


def test_vendor_purchasing_unknown_falls_back_to_ranking(session):
    vp = perf.vendor_purchasing(session, "no-such-vendor-xyz")
    assert vp["found"] is False
    assert vp["vendor_ranking"]  # still useful: the full ranking


# --- HTTP endpoints ---------------------------------------------------------
def test_performance_endpoints(client):
    r = client.get("/api/performance/overview?years=5")
    assert r.status_code == 200
    assert len(r.json()["yearly"]) == 5

    r = client.get("/api/performance/audit")
    assert r.status_code == 200
    assert r.json()["overall"] in ("ok", "warn", "fail")

    r = client.get("/api/performance/vendor?query=pharmaoverseas")
    assert r.status_code == 200
    assert r.json()["found"] is True
