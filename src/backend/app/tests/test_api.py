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
    assert {"ELSANTA", "MASHALA"} <= codes


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


# --- Sale returns (eStock Back_sales_header/details parity) ------------------
def _make_sale(client, qty=2):
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    target = next(p for p in products if p["on_hand"] >= qty + 1)
    r = client.post(
        "/api/sales",
        json={"branch_id": 1, "cashier_id": 1, "lines": [{"product_id": target["product_id"], "amount": qty}]},
    )
    assert r.status_code == 200, r.text
    return r.json()["sale_id"], target["product_id"]


def test_returnable_shows_sold_quantities(client):
    sale_id, product_id = _make_sale(client, qty=2)
    r = client.get(f"/api/sales/{sale_id}/returnable")
    assert r.status_code == 200, r.text
    body = r.json()
    line = next(l for l in body["lines"] if l["product_id"] == product_id)
    assert line["sold"] == 2 and line["returnable"] == 2


def test_partial_then_full_return_restocks_and_caps(client):
    sale_id, product_id = _make_sale(client, qty=2)
    before = next(
        p for p in client.get("/api/inventory/products?branch_id=1").json()["products"]
        if p["product_id"] == product_id
    )["on_hand"]

    # Partial return of 1 unit.
    r = client.post(f"/api/sales/{sale_id}/return",
                    json={"lines": [{"product_id": product_id, "amount": 1}], "cashier_id": 1})
    assert r.status_code == 200, r.text
    assert r.json()["original_sale_id"] == sale_id

    after = next(
        p for p in client.get("/api/inventory/products?branch_id=1").json()["products"]
        if p["product_id"] == product_id
    )["on_hand"]
    assert after == before + 1  # stock came back

    # Returnable drops to 1; returning 2 more must fail.
    line = next(l for l in client.get(f"/api/sales/{sale_id}/returnable").json()["lines"]
                if l["product_id"] == product_id)
    assert line["returnable"] == 1
    r = client.post(f"/api/sales/{sale_id}/return",
                    json={"lines": [{"product_id": product_id, "amount": 2}]})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "return_exceeds_sold"

    # Full return of the remainder (lines omitted => everything left).
    r = client.post(f"/api/sales/{sale_id}/return", json={})
    assert r.status_code == 200, r.text
    # Nothing left now.
    r = client.post(f"/api/sales/{sale_id}/return", json={})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "nothing_to_return"


def test_cannot_return_a_return(client):
    sale_id, product_id = _make_sale(client, qty=1)
    r = client.post(f"/api/sales/{sale_id}/return", json={})
    return_id = r.json()["return_id"]
    r = client.post(f"/api/sales/{return_id}/return", json={})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "cannot_return_return"


# --- Customer statement (Gedo_customers parity) -------------------------------
def test_customer_statement(client):
    customers = client.get("/api/customers").json()["customers"]
    target = next(c for c in customers if c["current_balance"] > 0)
    r = client.get(f"/api/customers/{target['customer_id']}/statement")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["customer_id"] == target["customer_id"]
    assert body["current_balance"] == target["current_balance"]
    assert isinstance(body["entries"], list)
    r = client.get("/api/customers/999999/statement")
    assert r.status_code == 404


# --- Profit & Loss (eStock profit rule) ---------------------------------------
def test_profit_loss_report(client):
    r = client.get("/api/accounting/profit-loss?days=30")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("revenue", "returns_refund", "net_revenue", "cogs", "gross_profit", "margin_pct"):
        assert key in body
    assert abs(body["net_revenue"] - body["cogs"] - body["gross_profit"]) < 0.01


# --- Purchase invoice creation (eStock New Purchase Invoice) -------------------
def test_create_purchase_receives_stock_and_updates_vendor(client):
    vendors = client.get("/api/vendors").json()["vendors"]
    vendor = vendors[0]
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    target = products[0]
    before_stock = target["on_hand"]
    before_owed = vendor["amount_owed"]

    r = client.post(
        "/api/purchasing/purchases",
        json={
            "branch_id": 1,
            "vendor_id": vendor["vendor_id"],
            "bill_number": "TEST-001",
            "lines": [
                {"product_id": target["product_id"], "amount": 10, "bonus": 2, "buy_price": 5.0, "exp_date": "2027-12-31"}
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_gross"] == 50.0  # 10 * 5.0 (bonus is free)

    after = next(
        p for p in client.get("/api/inventory/products?branch_id=1").json()["products"]
        if p["product_id"] == target["product_id"]
    )
    assert after["on_hand"] == before_stock + 12  # 10 bought + 2 bonus

    vendor_after = next(
        v for v in client.get("/api/vendors").json()["vendors"] if v["vendor_id"] == vendor["vendor_id"]
    )
    assert vendor_after["amount_owed"] == before_owed + 50.0


def test_create_purchase_rejects_unknown_vendor(client):
    r = client.post(
        "/api/purchasing/purchases",
        json={"branch_id": 1, "vendor_id": 999999, "lines": [{"product_id": 1, "amount": 1, "buy_price": 1}]},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "vendor_not_found"


# --- Cash desk shifts (eStock Cash_disk_close) ---------------------------------
def test_cash_shift_open_close_cycle(client):
    # No shift open initially (branch 2 keeps this test independent).
    assert client.get("/api/cashdesk/current?branch_id=2").json()["shift"] is None

    r = client.post("/api/cashdesk/open", json={"branch_id": 2, "cashier_id": 1, "opening_float": 500})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "open"

    # Double-open is refused.
    r = client.post("/api/cashdesk/open", json={"branch_id": 2, "opening_float": 0})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "shift_already_open"

    # A cash sale during the shift raises expected cash.
    products = client.get("/api/inventory/products?branch_id=2").json()["products"]
    target = next(p for p in products if p["on_hand"] >= 1)
    sale = client.post(
        "/api/sales",
        json={"branch_id": 2, "cashier_id": 1, "lines": [{"product_id": target["product_id"], "amount": 1}]},
    ).json()

    r = client.post("/api/cashdesk/close", json={"branch_id": 2, "counted_cash": 500 + sale["total_net"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "closed"
    assert body["expected_cash"] == 500 + sale["total_net"]
    assert body["variance"] == 0

    # Closing again fails; history has the shift.
    r = client.post("/api/cashdesk/close", json={"branch_id": 2, "counted_cash": 0})
    assert r.status_code == 422
    assert client.get("/api/cashdesk/history?branch_id=2").json()["shifts"][0]["status"] == "closed"


# --- Stock adjustment (eStock Stock Adjustments) --------------------------------
def test_stock_adjustment(client):
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    target = next(p for p in products if p["on_hand"] > 0)
    batches = client.get(f"/api/inventory/products/{target['product_id']}/batches?branch_id=1").json()["batches"]
    batch = next(b for b in batches if b["amount"] > 0)

    r = client.post("/api/inventory/adjust", json={"batch_id": batch["batch_id"], "new_amount": batch["amount"] + 5})
    assert r.status_code == 200, r.text
    assert r.json()["delta"] == 5

    r = client.post("/api/inventory/adjust", json={"batch_id": 999999, "new_amount": 1})
    assert r.status_code == 422


# --- Manual journal entry (eStock Tuning_accounts) ------------------------------
def test_manual_journal_entry(client):
    r = client.post(
        "/api/accounting/journal",
        json={"branch_id": 1, "account_type": "general", "debit": 100, "note": "قيد اختبار"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["entry_id"] > 0

    # Both debit AND credit is invalid; unknown account type is invalid.
    r = client.post("/api/accounting/journal",
                    json={"branch_id": 1, "account_type": "general", "debit": 10, "credit": 10})
    assert r.status_code == 422
    r = client.post("/api/accounting/journal",
                    json={"branch_id": 1, "account_type": "weird", "debit": 10})
    assert r.status_code == 422


# --- Sales-by-customer report ----------------------------------------------------
def test_sales_by_customer_report(client):
    r = client.get("/api/accounting/sales-by-customer?days=90")
    assert r.status_code == 200, r.text
    rows = r.json()["customers"]
    assert isinstance(rows, list)
    if rows:
        assert rows[0]["revenue"] >= rows[-1]["revenue"]  # sorted desc


# --- Weekly operations tasks (stocktake, merchandising, expiry, reorder) --------
def test_weekly_ops_tasks_created_once(client, session):
    from app.services import tasks as tasks_svc

    created_first = tasks_svc.ensure_weekly_ops_tasks(session)
    created_again = tasks_svc.ensure_weekly_ops_tasks(session)
    assert created_again == 0  # idempotent within the same ISO week

    r = client.get("/api/tasks")
    titles = [t["title"] for t in r.json()["tasks"]]
    assert any("جرد أسبوعي للمخزون" in t for t in titles)
    assert any("ميرشندايزينج" in t for t in titles)


# --- Merchandising shelf location -----------------------------------------------
def test_set_and_list_shelf_location(client):
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    pid = products[0]["product_id"]
    r = client.post(f"/api/inventory/products/{pid}/location", json={"shelf_location": "A3 — رف الأطفال"})
    assert r.status_code == 200, r.text
    assert r.json()["shelf_location"] == "A3 — رف الأطفال"

    listed = next(
        p for p in client.get("/api/inventory/products?branch_id=1").json()["products"] if p["product_id"] == pid
    )
    assert listed["shelf_location"] == "A3 — رف الأطفال"

    # Clearing works; unknown product 422s.
    r = client.post(f"/api/inventory/products/{pid}/location", json={"shelf_location": "  "})
    assert r.json()["shelf_location"] is None
    assert client.post("/api/inventory/products/999999/location", json={"shelf_location": "X"}).status_code == 422


# --- Employee PMP / development plan ----------------------------------------------
def test_employee_goals_lifecycle(client):
    emp = client.get("/api/employees/list").json()["employees"][0]
    eid = emp["employee_id"]

    r = client.post(
        f"/api/employees/{eid}/goals",
        json={"title": "رفع متوسط الفاتورة 10%", "category": "performance", "target_date": "2026-09-30"},
    )
    assert r.status_code == 200, r.text
    goal_id = r.json()["goal_id"]

    r = client.post(f"/api/employees/{eid}/goals", json={"title": "دورة خدمة عملاء", "category": "training"})
    assert r.status_code == 200

    goals = client.get(f"/api/employees/{eid}/goals").json()["goals"]
    assert len(goals) >= 2

    r = client.post(f"/api/employees/goals/{goal_id}/status", json={"status": "achieved"})
    assert r.status_code == 200
    achieved = next(g for g in client.get(f"/api/employees/{eid}/goals").json()["goals"] if g["goal_id"] == goal_id)
    assert achieved["status"] == "achieved" and achieved["completed_at"]

    # Bad category / status / employee are refused.
    assert client.post(f"/api/employees/{eid}/goals", json={"title": "x y", "category": "weird"}).status_code == 422
    assert client.post(f"/api/employees/goals/{goal_id}/status", json={"status": "weird"}).status_code == 422
    assert client.post("/api/employees/999999/goals", json={"title": "x y"}).status_code == 422
