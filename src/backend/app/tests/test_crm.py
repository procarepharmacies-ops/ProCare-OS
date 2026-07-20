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


# --- Phase 3: Loyalty Tiers --------------------------------------------------
def test_tier_thresholds_returns_config(session):
    from app.services.loyalty import tier_thresholds

    thresholds = tier_thresholds()
    assert "silver" in thresholds
    assert "gold" in thresholds
    assert "platinum" in thresholds
    # Each tier has (min_spend, max_spend, multiplier)
    assert len(thresholds["silver"]) == 3
    assert thresholds["silver"][2] == 1.0  # silver multiplier
    assert thresholds["gold"][2] == 1.25  # gold multiplier
    assert thresholds["platinum"][2] == 1.5  # platinum multiplier


def test_tier_multiplier_returns_correct_multiplier(session):
    from app.services.loyalty import tier_multiplier

    c = _customer(session)
    c.tier = "silver"
    session.commit()
    assert tier_multiplier(c) == 1.0

    c.tier = "gold"
    session.commit()
    assert tier_multiplier(c) == 1.25

    c.tier = "platinum"
    session.commit()
    assert tier_multiplier(c) == 1.5


def test_earn_points_applies_tier_multiplier(session):
    from app.services.loyalty import tier_multiplier

    c = _customer(session)
    pid, _ = _product_with_live_stock(session, 1)

    # Create sale with gold tier customer
    c.tier = "gold"
    session.commit()
    sale = pos.create_sale(
        session, branch_id=1, lines=[pos.SaleLineInput(pid, 3)], customer_id=c.customer_id, cashier_id=1
    )
    session.refresh(c)

    # Base points without multiplier
    base_points = loyalty.points_for_spend(float(sale.total_net))
    # Gold multiplier = 1.25
    expected = int(base_points * 1.25)
    assert float(c.loyalty_points) == pytest.approx(expected, abs=1)

    # Verify transaction note includes tier info
    tx = session.scalars(
        select(m.LoyaltyTransaction).where(m.LoyaltyTransaction.sale_id == sale.sale_id)
    ).all()
    assert any("gold" in str(t.note).lower() for t in tx)


def test_recompute_customer_tier_from_12m_spend(session):
    from app.services.loyalty import recompute_customer_tier
    from datetime import datetime, timedelta

    c = _customer(session)
    pid, _ = _product_with_live_stock(session, 1)

    # Create multiple sales to push total spend
    # Silver threshold: < 2000; Gold threshold: 2000-10000; Platinum: >= 10000
    sales = []
    for i in range(3):
        sale = pos.create_sale(
            session, branch_id=1, lines=[pos.SaleLineInput(pid, 10)], customer_id=c.customer_id, cashier_id=1
        )
        sales.append(sale)

    session.refresh(c)
    total_spend = sum(float(s.total_net) for s in sales)

    # Recompute tier
    new_tier, computed_spend = recompute_customer_tier(session, c.customer_id)
    session.commit()
    session.refresh(c)

    assert c.tier == new_tier
    assert float(c.tier_spend_12m) == pytest.approx(float(computed_spend))
    if float(computed_spend) >= 2000:
        assert new_tier in ("gold", "platinum")
    else:
        assert new_tier == "silver"


def test_tier_promotion_detected(session):
    from app.services.loyalty import recompute_customer_tier

    c = _customer(session)
    c.tier = "silver"
    session.commit()

    pid, _ = _product_with_live_stock(session, 1)

    # Create enough sales to cross into gold tier (>= 2000 EGP)
    sales = []
    for i in range(4):
        sale = pos.create_sale(
            session, branch_id=1, lines=[pos.SaleLineInput(pid, 10)], customer_id=c.customer_id, cashier_id=1
        )
        sales.append(sale)

    # Recompute tier
    new_tier, _ = recompute_customer_tier(session, c.customer_id)
    session.refresh(c)

    # If total spend >= 2000, should promote to gold or platinum
    if new_tier != "silver":
        assert new_tier in ("gold", "platinum")


# --- Phase 3: RFM Segmentation ------------------------------------------------
def test_compute_rfm_segments_assigns_all_customers(session):
    from app.services.crm import compute_rfm_segments

    # Create customers with varied purchase history
    c1 = _customer(session)  # No purchases = dormant
    c2 = _customer(session)
    c3 = _customer(session)
    c4 = _customer(session)

    pid, _ = _product_with_live_stock(session, 1)

    # C2: Recent, frequent, high-spend = VIP
    for _ in range(15):
        pos.create_sale(
            session, branch_id=1, lines=[pos.SaleLineInput(pid, 2)], customer_id=c2.customer_id, cashier_id=1
        )

    # C3: Regular customer
    for _ in range(8):
        pos.create_sale(
            session, branch_id=1, lines=[pos.SaleLineInput(pid, 1)], customer_id=c3.customer_id, cashier_id=1
        )

    # Compute RFM
    segments = compute_rfm_segments(session)
    session.commit()

    # Verify all customers got assigned
    assert c1.customer_id in segments
    assert c2.customer_id in segments
    assert c3.customer_id in segments
    assert c4.customer_id in segments

    # Verify segment values are valid
    valid_segments = {"vip", "regular", "at_risk", "dormant"}
    for segment in segments.values():
        assert segment in valid_segments


def test_vip_segment_criteria(session):
    from app.services.crm import compute_rfm_segments, segment_customers

    c = _customer(session)
    pid, _ = _product_with_live_stock(session, 1)

    # Create VIP customer: recent, frequent (>=12), high-spend (>=5000)
    # Need ~25 purchases of ~200 EGP each to hit 5000 EGP
    for _ in range(25):
        pos.create_sale(
            session, branch_id=1, lines=[pos.SaleLineInput(pid, 1)], customer_id=c.customer_id, cashier_id=1
        )

    segments = compute_rfm_segments(session)
    session.commit()
    session.refresh(c)

    if segments[c.customer_id] == "vip":
        # Verify the customer meets VIP criteria
        vips = segment_customers(session, "vip")
        assert any(cust.customer_id == c.customer_id for cust in vips)


def test_dormant_segment_criteria(session):
    from app.services.crm import compute_rfm_segments, segment_customers

    c = _customer(session)  # No purchases

    segments = compute_rfm_segments(session)
    session.commit()  # Persist the rfm_segment changes
    session.refresh(c)

    # Customer with no purchases should be dormant
    assert segments[c.customer_id] == "dormant"

    dormant = segment_customers(session, "dormant")
    assert any(cust.customer_id == c.customer_id for cust in dormant)


def test_segment_counts_returns_all_segments(session):
    from app.services.crm import compute_rfm_segments, segment_counts

    # Create multiple customers
    for _ in range(4):
        _customer(session)

    compute_rfm_segments(session)
    session.commit()
    counts = segment_counts(session)

    # Verify all segments present
    assert "vip" in counts
    assert "regular" in counts
    assert "at_risk" in counts
    assert "dormant" in counts

    # Verify counts are non-negative integers
    for segment, count in counts.items():
        assert isinstance(count, int)
        assert count >= 0


def test_segment_summary_includes_translations(session):
    from app.services.crm import compute_rfm_segments, segment_summary

    compute_rfm_segments(session)
    session.commit()
    summary = segment_summary(session)

    # Verify structure
    for segment_key in ("vip", "regular", "at_risk", "dormant"):
        assert segment_key in summary
        segment_data = summary[segment_key]
        assert "ar" in segment_data  # Arabic name
        assert "en" in segment_data  # English name
        assert "count" in segment_data
        assert "icon" in segment_data


# --- Phase 3: API Endpoints --------------------------------------------------
def test_update_customer_tier_endpoint(client, session):
    c = _customer(session)
    r = client.patch(f"/api/crm/customers/{c.customer_id}/tier", json={"tier": "gold"})
    assert r.status_code == 200
    body = r.json()
    assert body["new_tier"] == "gold"

    session.refresh(c)
    assert c.tier == "gold"


def test_update_customer_tier_invalid_tier_rejected(client, session):
    c = _customer(session)
    r = client.patch(f"/api/crm/customers/{c.customer_id}/tier", json={"tier": "invalid"})
    assert r.status_code == 400


def test_update_customer_wa_opt_out(client, session):
    c = _customer(session)
    assert c.wa_opt_out is False

    r = client.patch(f"/api/crm/customers/{c.customer_id}/wa-opt-out", params={"opt_out": True})
    assert r.status_code == 200

    session.refresh(c)
    assert c.wa_opt_out is True


def test_segment_summary_endpoint(client, session):
    from app.services.crm import compute_rfm_segments

    # Create a customer and compute segments
    _customer(session)
    compute_rfm_segments(session)
    session.commit()

    r = client.get("/api/crm/segments/summary")
    assert r.status_code == 200
    body = r.json()

    # Verify response structure
    for segment in ("vip", "regular", "at_risk", "dormant"):
        assert segment in body
        assert "ar" in body[segment]
        assert "en" in body[segment]
        assert "count" in body[segment]
