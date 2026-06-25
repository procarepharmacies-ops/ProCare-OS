"""Alerts and the advisory clinical lookup behave per spec."""
from app import alerts, drugs
from app.db import get_db


def test_expiry_alert_buckets_nested():
    a = alerts.expiry_alerts("ALL")
    c = a["counts"]
    # 7-day horizon is a subset of 30, which is a subset of 90.
    assert c["within_7"] <= c["within_30"] <= c["within_90"]
    assert "expected_loss_at_risk" in a


def test_reorder_drafts_are_draft_only():
    d = alerts.reorder_drafts("ALL")
    assert "draft" in d["note"].lower()
    for draft in d["drafts"]:
        assert draft["suggested_order_qty"] > 0


def test_debtor_alerts_only_over_limit():
    d = alerts.debtor_alerts()
    for c in d["customers"]:
        assert c["over_limit_by"] > 0


def test_drug_basket_is_advisory_and_finds_interaction():
    ids = [r["product_id"] for r in get_db().query(
        "SELECT product_id FROM products WHERE scientific_name IN ('warfarin','aspirin')")]
    res = drugs.check_basket(ids)
    assert res["advisory"] is True
    assert res["max_severity"] == "severe"
    assert len(res["warnings"]) >= 1
    # The guardrail text must make clear it never blocks a sale.
    assert "لا يمنع" in res["disclaimer_ar"]


def test_drug_status_reports_titan_tbd():
    s = drugs.status()
    assert s["titan_configured"] is False
    assert s["source"] == "local_demo"
