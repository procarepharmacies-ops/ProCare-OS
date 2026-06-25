"""The AI assistant is read-only by construction and answers in Arabic."""
import pytest

from app import ai


@pytest.mark.parametrize("sql", [
    "DROP TABLE sales",
    "DELETE FROM customers",
    "UPDATE customers SET current_balance = 0",
    "INSERT INTO vw_daily_sales VALUES (1)",
    "SELECT 1; DROP TABLE sales",                       # statement stacking
    "SELECT * FROM vw_daily_sales; DELETE FROM sales",  # stacking
    "SELECT * FROM products",                           # base table, not a view
    "SELECT * FROM employees",                          # not whitelisted
    "SELECT * FROM sales",                              # base table
    "SELECT * FROM vw_daily_sales -- ; DROP TABLE x",   # comment smuggling
])
def test_validator_rejects_unsafe(sql):
    ok, reason, _ = ai.validate_sql(sql)
    assert ok is False, f"should have rejected: {sql} ({reason})"


@pytest.mark.parametrize("sql", [
    "SELECT * FROM vw_daily_sales WHERE sale_day = date('now')",
    "select product_name_ar, revenue from vw_top_products order by revenue desc limit 5",
    "SELECT * FROM vw_expiry_risk WHERE days_to_expiry BETWEEN 0 AND 7",
])
def test_validator_allows_whitelisted_selects(sql):
    ok, reason, _ = ai.validate_sql(sql)
    assert ok is True, reason


def test_run_whitelisted_sql_blocks_writes():
    with pytest.raises(ValueError):
        ai.run_whitelisted_sql("DELETE FROM sales")


def test_rules_engine_answers_examples():
    for q in ["مبيعات النهاردة", "مبيعات امبارح",
              "الأصناف اللي هتخلص الأسبوع الجاي", "الأصناف الناقصة",
              "أكثر صنف مبيعاً", "العملاء اللي تجاوزوا الحد", "مستحقات الموردين"]:
        r = ai.chat(q, "ALL")
        assert r["engine"] in ("rules", "rules_fallback")
        assert isinstance(r["answer"], str) and r["answer"]
        # If SQL was produced, it must pass the validator.
        if r.get("sql"):
            ok, _, _ = ai.validate_sql(r["sql"])
            assert ok


def test_top_product_intent_beats_generic_month():
    # "أكثر صنف ... الشهر ده" must hit top-products, not the month-sales intent.
    r = ai.chat("أكثر صنف مبيعاً الشهر ده", "ALL")
    assert "vw_top_products" in (r.get("sql") or "")


def test_unknown_question_offers_suggestions():
    r = ai.chat("ما هي عاصمة فرنسا؟", "ALL")
    assert r["engine"] == "rules"
    assert "suggestions" in r


def test_engine_status_is_read_only():
    st = ai.engine_status()
    assert st["read_only"] is True
    assert "vw_daily_sales" in st["view_whitelist"]
