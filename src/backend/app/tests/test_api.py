"""API smoke tests + AI assistant routing."""
from __future__ import annotations


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["seeded_products"] > 0


def test_branches(client):
    r = client.get("/api/branches")
    codes = {b["code"] for b in r.json()["branches"]}
    assert {"MAIN", "ELSANTA"} <= codes


def test_dashboard_summary(client):
    r = client.get("/api/dashboard/summary")
    kpis = r.json()["kpis"]
    assert "sales_month" in kpis and kpis["sales_month"] >= 0
    assert kpis["debtors"] >= 1  # seed deliberately makes some over-limit


def test_daily_sales_continuous(client):
    r = client.get("/api/dashboard/daily-sales?days=14")
    series = r.json()["series"]
    assert len(series) == 14


def test_inventory_search(client):
    r = client.get("/api/inventory/products?search=Panadol")
    products = r.json()["products"]
    assert any("بانادول" in p["name_ar"] for p in products)


def test_expiry_alerts(client):
    r = client.get("/api/alerts/expiry?horizon_days=90")
    body = r.json()
    assert "counts" in body and "buckets" in body


def test_reorder_drafts(client):
    r = client.get("/api/alerts/reorder")
    assert isinstance(r.json()["drafts"], list)


def test_ai_chat_sales_today(client):
    r = client.post("/api/ai/chat", json={"query": "كام باعت الصيدلية النهارده؟", "lang": "ar"})
    body = r.json()
    assert body["intent"] == "sales_today"
    assert "engine" in body


def test_ai_chat_expiry(client):
    r = client.post("/api/ai/chat", json={"query": "إيه الأدوية اللي هتخلص قريب؟"})
    assert r.json()["intent"] == "expiring_soon"


def test_ai_chat_reorder(client):
    r = client.post("/api/ai/chat", json={"query": "اعملي طلب شراء للأصناف الناقصة"})
    assert r.json()["intent"] == "reorder_draft"


def test_create_sale_via_api(client):
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    target = next(p for p in products if p["on_hand"] >= 2)
    r = client.post(
        "/api/sales",
        json={"branch_id": 1, "cashier_id": 1, "lines": [{"product_id": target["product_id"], "amount": 1}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sale_id"] > 0
