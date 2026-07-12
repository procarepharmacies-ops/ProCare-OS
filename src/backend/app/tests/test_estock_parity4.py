"""Round-4 parity: customer 360, chart of accounts."""
from __future__ import annotations

from sqlalchemy import select

from app.db import models as m


def test_customer_profile(client, session):
    cust = session.scalars(select(m.Customer).where(m.Customer.is_deleted == False)).first()  # noqa: E712
    r = client.get(f"/api/customers/{cust.customer_id}/profile")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["customer_id"] == cust.customer_id
    for key in ("address", "loyalty_points", "history", "medicines", "total_spent"):
        assert key in body
    assert isinstance(body["medicines"], list)
    assert client.get("/api/customers/999999/profile").status_code == 404


def test_update_customer_address(client, session):
    cust = session.scalars(select(m.Customer).where(m.Customer.is_deleted == False)).first()  # noqa: E712
    r = client.post(f"/api/customers/{cust.customer_id}", json={"address": "عنوان جديد للاختبار"})
    assert r.status_code == 200 and r.json()["address"] == "عنوان جديد للاختبار"
    # Reflected in the profile.
    prof = client.get(f"/api/customers/{cust.customer_id}/profile").json()
    assert prof["address"] == "عنوان جديد للاختبار"


def test_chart_of_accounts(client):
    r = client.get("/api/accounting/chart")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "groups" in body and "balanced" in body
    for g in body["groups"]:
        assert "label" in g and "accounts" in g
        assert g["balance"] == sum(a["balance"] for a in g["accounts"])
