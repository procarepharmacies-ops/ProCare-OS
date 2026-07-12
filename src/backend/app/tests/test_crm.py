"""CRM tests: loyalty earn/redeem/clawback, WhatsApp links, campaigns."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.db import models as m
from app.services import loyalty, pos, whatsapp as wa
from app.services.common import today


def _product_with_live_stock(session, branch_id):
    row = session.execute(
        select(m.StockBatch.product_id, func.sum(m.StockBatch.amount))
        .where(
            m.StockBatch.branch_id == branch_id,
            m.StockBatch.amount > 0,
            (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > today()),  # noqa: E711
        )
        .group_by(m.StockBatch.product_id)
        .order_by(func.sum(m.StockBatch.amount).desc())
    ).first()
    return row[0], float(row[1])


def _customer(session, points=0.0, mobile="01012345678"):
    c = m.Customer(name_ar="عميل ولاء", mobile=mobile, loyalty_points=points)
    session.add(c)
    session.commit()
    return c


# --- Loyalty ------------------------------------------------------------------
def test_sale_earns_points_and_writes_audit_row(session):
    c = _customer(session)
    pid, _ = _product_with_live_stock(session, 1)
    sale = pos.create_sale(
        session, branch_id=1, lines=[pos.SaleLineInput(pid, 3)], customer_id=c.customer_id, cashier_id=1
    )
    session.refresh(c)
    expected = loyalty.points_for_spend(float(sale.total_net))
    assert float(c.loyalty_points) == pytest.approx(expected)
    tx = session.scalars(
        select(m.LoyaltyTransaction).where(m.LoyaltyTransaction.sale_id == sale.sale_id)
    ).all()
    assert len(tx) == 1 and tx[0].kind == "earn" and float(tx[0].points_delta) == pytest.approx(expected)


def test_redeem_reduces_net_and_points_balance(session):
    c = _customer(session, points=100)
    pid, _ = _product_with_live_stock(session, 1)
    # Baseline: identical cart without redemption.
    base = pos.create_sale(session, branch_id=1, lines=[pos.SaleLineInput(pid, 2)], cashier_id=1)
    sale = pos.create_sale(
        session,
        branch_id=1,
        lines=[pos.SaleLineInput(pid, 2)],
        customer_id=c.customer_id,
        cashier_id=1,
        redeem_points=40,
    )
    value = min(loyalty.redemption_value(40), float(base.total_net))
    assert float(sale.total_net) == pytest.approx(float(base.total_net) - value)
    session.refresh(c)
    # Spent 40, then earned on the (reduced) net.
    earned = loyalty.points_for_spend(float(sale.total_net))
    assert float(c.loyalty_points) == pytest.approx(100 - 40 + earned)
    kinds = {
        t.kind
        for t in session.scalars(select(m.LoyaltyTransaction).where(m.LoyaltyTransaction.sale_id == sale.sale_id))
    }
    assert kinds == {"redeem", "earn"} or kinds == {"redeem"}  # earn may be 0 on tiny nets


def test_redeem_more_than_balance_is_rejected_atomically(session):
    c = _customer(session, points=5)
    pid, _ = _product_with_live_stock(session, 1)
    with pytest.raises(pos.POSError) as e:
        pos.create_sale(
            session,
            branch_id=1,
            lines=[pos.SaleLineInput(pid, 1)],
            customer_id=c.customer_id,
            redeem_points=500,
        )
    assert e.value.code == "insufficient_points"
    session.refresh(c)
    assert float(c.loyalty_points) == pytest.approx(5)  # untouched after rollback


def test_return_claws_back_earned_points(session):
    c = _customer(session)
    pid, _ = _product_with_live_stock(session, 1)
    sale = pos.create_sale(
        session, branch_id=1, lines=[pos.SaleLineInput(pid, 3)], customer_id=c.customer_id, cashier_id=1
    )
    session.refresh(c)
    earned = float(c.loyalty_points)
    ret = pos.return_sale(session, sale.sale_id)  # full return
    session.refresh(c)
    clawed = loyalty.points_for_spend(float(ret.total_net))
    assert float(c.loyalty_points) == pytest.approx(max(earned - clawed, 0))


def test_loyalty_summary_api(client, session):
    c = _customer(session, points=12)
    r = client.get(f"/api/crm/loyalty/{c.customer_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == 12
    assert body["value_egp"] == pytest.approx(12 * settings.loyalty_point_value)


# --- WhatsApp -----------------------------------------------------------------
def test_normalize_egyptian_mobile():
    assert wa.normalize_phone("01012345678") == "201012345678"
    assert wa.normalize_phone("+20 101 234 5678") == "201012345678"
    assert wa.normalize_phone("0020101234567") == "20101234567"
    assert wa.normalize_phone(None) is None
    assert wa.normalize_phone("") is None


def test_sale_response_includes_whatsapp_link(client, session):
    c = _customer(session)
    pid, _ = _product_with_live_stock(session, 1)
    r = client.post(
        "/api/sales",
        json={"branch_id": 1, "customer_id": c.customer_id, "lines": [{"product_id": pid, "amount": 1}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["whatsapp_link"].startswith("https://wa.me/201012345678?text=")
    assert body["whatsapp_sent"] is False  # no Cloud API creds in tests
    assert "loyalty_points" in body


def test_invoice_whatsapp_endpoint(client, session):
    c = _customer(session)
    pid, _ = _product_with_live_stock(session, 1)
    sale = pos.create_sale(
        session, branch_id=1, lines=[pos.SaleLineInput(pid, 1)], customer_id=c.customer_id
    )
    r = client.get(f"/api/crm/sales/{sale.sale_id}/whatsapp")
    assert r.status_code == 200
    body = r.json()
    assert "بروكير" in body["message"] and f"#{sale.sale_id}" in body["message"]
    assert body["link"] and body["sent"] is False


# --- Campaigns ------------------------------------------------------------------
def test_campaign_create_send_and_links(client, session):
    _customer(session, mobile="01098765432")
    r = client.post(
        "/api/crm/campaigns",
        json={"name": "عرض الصيف", "message": "خصم ١٠٪ هذا الأسبوع في بروكير!", "audience": "all"},
    )
    assert r.status_code == 200
    camp = r.json()
    assert camp["status"] == "draft" and camp["recipient_count"] >= 1

    r = client.get(f"/api/crm/campaigns/{camp['campaign_id']}/links")
    links = r.json()["links"]
    assert links and all(l["link"].startswith("https://wa.me/") for l in links)

    r = client.post(f"/api/crm/campaigns/{camp['campaign_id']}/send")
    assert r.status_code == 200
    sent = r.json()
    assert sent["api_configured"] is False and sent["sent_via_api"] == 0

    # Sent campaigns can't be re-sent.
    r = client.post(f"/api/crm/campaigns/{camp['campaign_id']}/send")
    assert r.status_code == 422


def test_campaign_bad_audience_rejected(client):
    r = client.post("/api/crm/campaigns", json={"name": "x", "message": "y", "audience": "nope"})
    assert r.status_code == 422


def test_crm_status(client):
    r = client.get("/api/crm/status")
    assert r.status_code == 200
    body = r.json()
    assert body["delivery_mode"] == "click_to_chat_links"
    assert body["loyalty"]["egp_per_point"] == settings.loyalty_egp_per_point
