"""The eStock read-time data-quality rules (docs/05) are correctly implemented."""
from datetime import date

from app import etl


def test_coalesce_sale_date_uses_insert_when_bill_null():
    assert etl.coalesce_sale_date(None, "2026-01-02") == "2026-01-02"
    assert etl.coalesce_sale_date("2026-01-01", "2026-01-02") == "2026-01-01"


def test_returns_are_detected():
    assert etl.is_excluded_return("Y") is True
    assert etl.is_excluded_return("y") is True
    assert etl.is_excluded_return("N") is False
    assert etl.is_excluded_return(None) is False


def test_available_stock_rule():
    today = date(2026, 6, 25)
    assert etl.is_available(10, "2027-01-01", "Y", today) is True   # in date
    assert etl.is_available(10, "2026-01-01", "Y", today) is False  # expired
    assert etl.is_available(0, "2027-01-01", "Y", today) is False   # zero qty
    assert etl.is_available(5, None, "N", today) is True            # no expiry
    assert etl.is_available(-3, "2027-01-01", "Y", today) is False  # negative


def test_fefo_orders_earliest_first():
    items = [{"exp": "2026-12-01"}, {"exp": "2026-06-01"}, {"exp": "2026-09-01"}]
    items.sort(key=lambda b: etl.fefo_key(b["exp"]))
    assert [i["exp"] for i in items] == ["2026-06-01", "2026-09-01", "2026-12-01"]


def test_reconcile_shape_in_shadow_mode():
    r = etl.reconcile(7)
    assert r["mode"] == "procare_only"
    assert r["has_estock_source"] is False
    assert "profit" in r["checks"]
    assert r["checks"]["profit"]["gross_profit"] is not None
