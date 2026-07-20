"""CRM endpoints: loyalty points, per-invoice WhatsApp, marketing campaigns.

Delivery is graceful: with WHATSAPP_TOKEN/WHATSAPP_PHONE_ID set the Cloud API
sends directly; otherwise every message is a wa.me click-to-chat link.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.config import settings
from app.db import models as m
from app.db.base import get_session
from app.services import loyalty as loyalty_svc
from app.services import whatsapp as wa

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/status")
def status():
    """What the CRM can do right now (never returns secrets)."""
    return {
        "whatsapp_api_configured": wa.is_configured(),
        "delivery_mode": "cloud_api" if wa.is_configured() else "click_to_chat_links",
        "loyalty": {
            "egp_per_point": settings.loyalty_egp_per_point,
            "point_value_egp": settings.loyalty_point_value,
        },
        "audiences": wa.AUDIENCES,
    }


# --- Loyalty ------------------------------------------------------------------
@router.get("/loyalty/{customer_id}")
def loyalty_summary(customer_id: int, session: Session = Depends(get_session)):
    try:
        return loyalty_svc.summary(session, customer_id)
    except loyalty_svc.LoyaltyError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})


class AdjustIn(BaseModel):
    points_delta: float
    note: str | None = None


@router.post("/loyalty/{customer_id}/adjust")
def loyalty_adjust(customer_id: int, payload: AdjustIn, session: Session = Depends(get_session)):
    """Manual adjustment (e.g. goodwill points, corrections) — audited."""
    customer = session.get(m.Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")
    new_balance = float(customer.loyalty_points or 0) + float(payload.points_delta)
    if new_balance < 0:
        raise HTTPException(status_code=422, detail={"code": "negative_balance", "message": "balance cannot go negative"})
    customer.loyalty_points = new_balance
    session.add(
        m.LoyaltyTransaction(
            customer_id=customer_id,
            points_delta=float(payload.points_delta),
            kind="adjust",
            note=payload.note or "تعديل يدوي / manual adjustment",
        )
    )
    session.commit()
    return {"customer_id": customer_id, "points": new_balance}


# --- Per-invoice WhatsApp -----------------------------------------------------
@router.get("/sales/{sale_id}/whatsapp")
def sale_whatsapp(sale_id: int, session: Session = Depends(get_session)):
    """Invoice message + wa.me link; auto-sent when the Cloud API is configured."""
    sale = session.get(m.Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="sale not found")
    return wa.invoice_whatsapp(session, sale)


# --- Campaigns ------------------------------------------------------------------
class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2000)
    audience: str = "all"
    created_by: int | None = None


def _campaign_out(c: m.Campaign) -> dict:
    return {
        "campaign_id": c.campaign_id,
        "name": c.name,
        "message": c.message,
        "audience": c.audience,
        "status": c.status,
        "recipient_count": c.recipient_count,
        "sent_count": c.sent_count,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "sent_at": c.sent_at.isoformat() if c.sent_at else None,
    }


@router.get("/campaigns")
def list_campaigns(session: Session = Depends(get_session)):
    rows = session.scalars(select(m.Campaign).order_by(desc(m.Campaign.campaign_id)).limit(50)).all()
    return {"campaigns": [_campaign_out(c) for c in rows]}


@router.post("/campaigns")
def create_campaign(payload: CampaignIn, session: Session = Depends(get_session)):
    try:
        c = wa.create_campaign(session, payload.name, payload.message, payload.audience, payload.created_by)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"code": "bad_audience", "message": str(e)})
    return _campaign_out(c)


@router.post("/campaigns/{campaign_id}/send")
def send_campaign(campaign_id: int, session: Session = Depends(get_session)):
    c = session.get(m.Campaign, campaign_id)
    if c is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    if c.status == "sent":
        raise HTTPException(status_code=422, detail={"code": "already_sent", "message": "campaign already sent"})
    return wa.send_campaign(session, c)


@router.get("/campaigns/{campaign_id}/links")
def campaign_links(campaign_id: int, session: Session = Depends(get_session)):
    """Per-customer click-to-chat links — the delivery mode without the API."""
    c = session.get(m.Campaign, campaign_id)
    if c is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    return {"campaign_id": campaign_id, "links": wa.campaign_links(session, c)}


# --- Phase 3: Loyalty Tiers & RFM Segmentation --------------------------------
@router.get("/segments/summary")
def segment_summary(session: Session = Depends(get_session)):
    """RFM segment distribution (vip/regular/at_risk/dormant) with counts."""
    from app.services import crm as crm_svc

    return crm_svc.segment_summary(session)


class CustomerTierUpdate(BaseModel):
    tier: str


@router.patch("/customers/{customer_id}/tier", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def update_customer_tier(customer_id: int, payload: CustomerTierUpdate, session: Session = Depends(get_session)):
    """Manually set a customer's tier (manager+)."""
    customer = session.get(m.Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="customer not found")
    if payload.tier not in ("silver", "gold", "platinum"):
        raise HTTPException(status_code=400, detail="Invalid tier")

    old_tier = customer.tier
    customer.tier = payload.tier
    session.commit()

    return {
        "customer_id": customer_id,
        "old_tier": old_tier,
        "new_tier": customer.tier,
        "message": f"Tier updated to {payload.tier}",
    }


@router.patch("/customers/{customer_id}/wa-opt-out")
def update_customer_wa_opt_out(customer_id: int, opt_out: bool, session: Session = Depends(get_session)):
    """Update WhatsApp opt-out flag."""
    customer = session.get(m.Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="customer not found")

    customer.wa_opt_out = opt_out
    session.commit()

    return {"customer_id": customer_id, "wa_opt_out": customer.wa_opt_out}
