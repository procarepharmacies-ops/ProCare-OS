"""Performance-over-time, audit and supplier-purchasing tests.

Exercises the service directly against the seeded 5-year dataset and the HTTP
endpoints through the app. The same code runs on SQL Server in production.
"""
from __future__ import annotations

from app.services import deep_analysis as da
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
    # A branch-scoped overview carries no by_branch comparison; consolidated does.
    assert "by_branch" not in perf.overview(session, branch_id=1)


def test_overview_by_branch_reconciles(session):
    ov = perf.overview(session)
    assert len(ov["by_branch"]) == 2  # Elsanta + Mas-hala
    # Per-branch invoices sum to the consolidated total.
    assert sum(b["totals"]["invoices"] for b in ov["by_branch"]) == ov["totals"]["invoices"]
    for b in ov["by_branch"]:
        assert b["code"] in ("ELSANTA", "MASHALA")
        assert b["totals"]["revenue"] > 0
        assert len(b["yearly"]) == 5


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
    # Spend is broken down by branch and reconciles to the total.
    assert len(vp["by_branch"]) >= 1
    assert abs(sum(b["spend"] for b in vp["by_branch"]) - vp["total_spend"]) < 1.0
    # Shares across all vendors sum to ~100%.
    assert abs(sum(r["share_pct"] for r in vp["vendor_ranking"]) - 100) < 1.0


def test_vendor_purchasing_unknown_falls_back_to_ranking(session):
    vp = perf.vendor_purchasing(session, "no-such-vendor-xyz")
    assert vp["found"] is False
    assert vp["vendor_ranking"]  # still useful: the full ranking


# --- deep analysis ----------------------------------------------------------
def test_deep_analysis_covers_all_aspects(session):
    d = da.deep_analysis(session, years=5, lang="en")
    # Every aspect present.
    for key in ("sales", "inventory", "customers", "suppliers", "by_branch", "audit",
                "findings", "recommendations", "scorecard", "narrative"):
        assert key in d, f"missing {key}"
    # Inventory turnover computed.
    assert d["inventory"]["turnover"]["days_of_stock_cover"] is not None
    assert d["inventory"]["turnover"]["annual_inventory_turns"] > 0
    # Findings are severity-scored and ordered (high risks first).
    assert d["findings"]
    sev_rank = {"high": 0, "medium": 1, "low": 2, "positive": 3}
    ranks = [sev_rank[f["severity"]] for f in d["findings"]]
    assert ranks == sorted(ranks)
    # Supplier concentration is measured; PharmaOverseas dominates the seed.
    assert d["suppliers"]["top_vendor"] == "PharmaOverseas"
    assert 0 <= d["suppliers"]["herfindahl_index"] <= 1
    # Offline, the narrative is the deterministic engine (no API key in tests).
    assert d["narrative_engine"] == "rule-based"
    assert len(d["narrative"]) > 40


def test_deep_analysis_endpoint(client):
    r = client.get("/api/performance/deep?years=5&lang=en")
    assert r.status_code == 200
    body = r.json()
    assert body["scorecard"]["high_risks"] >= 0
    assert body["findings"]


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
