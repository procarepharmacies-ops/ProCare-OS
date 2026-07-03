"""WhatsApp CRM — invoice messages after every sale + marketing campaigns.

Two delivery modes, chosen automatically:

* **Cloud API** (zero-friction for staff): when ``WHATSAPP_TOKEN`` and
  ``WHATSAPP_PHONE_ID`` are set in the environment (Meta WhatsApp Business
  Cloud API credentials), messages are sent directly from the pharmacy's
  WhatsApp Business number.
* **Click-to-chat fallback** (zero setup): with no credentials, every message
  becomes a ``wa.me`` link that opens WhatsApp (web/desktop/phone) with the
  text pre-filled — the cashier just presses send. Works from day one.

Credentials never live in git — environment only, like the AI keys.
"""
from __future__ import annotations

import os
import urllib.parse
from datetime import datetime, timedelta

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import money

GRAPH_URL = "https://graph.facebook.com/v20.0"


def _token() -> str | None:
    return os.environ.get("WHATSAPP_TOKEN") or None


def _phone_id() -> str | None:
    return os.environ.get("WHATSAPP_PHONE_ID") or None


def is_configured() -> bool:
    """True when the Cloud API can send directly (token + phone id set)."""
    return bool(_token() and _phone_id())


def normalize_phone(mobile: str | None) -> str | None:
    """Digits-only international form. Egyptian local numbers (01xxxxxxxxx)
    get the +20 country code; anything already international passes through."""
    if not mobile:
        return None
    digits = "".join(ch for ch in mobile if ch.isdigit())
    if not digits:
        return None
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("01") and len(digits) == 11:  # Egyptian mobile
        digits = "2" + digits
    return digits


def wa_link(mobile: str | None, text: str) -> str | None:
    """Click-to-chat URL that opens WhatsApp with the message pre-filled."""
    phone = normalize_phone(mobile)
    if not phone:
        return None
    return f"https://wa.me/{phone}?text={urllib.parse.quote(text)}"


def send_text(mobile: str | None, text: str) -> bool:
    """Send via the Cloud API. Returns True on success, False otherwise
    (no exception — CRM sending must never break a sale)."""
    phone = normalize_phone(mobile)
    if not phone or not is_configured():
        return False
    try:
        resp = httpx.post(
            f"{GRAPH_URL}/{_phone_id()}/messages",
            headers={"Authorization": f"Bearer {_token()}"},
            json={
                "messaging_product": "whatsapp",
                "to": phone,
                "type": "text",
                "text": {"body": text},
            },
            timeout=15,
        )
        return resp.status_code < 300
    except Exception:  # noqa: BLE001 — network failure must not break the caller
        return False


# --- Invoice message ---------------------------------------------------------
def invoice_message(session: Session, sale: m.Sale) -> str:
    """The Arabic thank-you + invoice summary sent after every sale."""
    lines = []
    for ln in sale.lines:
        name = ln.product.name_ar or ln.product.name_en or f"#{ln.product_id}"
        lines.append(f"• {name} ×{money(ln.amount)} = {money(ln.total_sell)} ج")
    body = "\n".join(lines)
    kind = "فاتورة مرتجع" if sale.is_return else "فاتورة"
    msg = (
        f"صيدليات بروكير 💚\n"
        f"{kind} #{sale.sale_id} — {sale.sale_date.strftime('%Y-%m-%d %H:%M')}\n"
        f"{body}\n"
        f"الإجمالي: {money(sale.total_net)} جنيه"
    )
    if sale.total_discount and float(sale.total_discount) > 0:
        msg += f" (خصم {money(sale.total_discount)} ج)"
    if sale.customer_id:
        customer = sale.customer
        if customer is not None:
            msg += f"\nرصيد نقاطك: {money(customer.loyalty_points or 0)} نقطة ⭐"
    msg += "\nشكراً لثقتكم — مش مجرد صيدلية… عيلة لكل احتياجاتك 🙏"
    return msg


def invoice_whatsapp(session: Session, sale: m.Sale) -> dict:
    """Message + wa.me link for a sale; auto-sends when the API is configured."""
    text = invoice_message(session, sale)
    mobile = sale.customer.mobile if sale.customer else None
    link = wa_link(mobile, text)
    sent = send_text(mobile, text) if is_configured() else False
    return {
        "sale_id": sale.sale_id,
        "customer": sale.customer.name_ar if sale.customer else None,
        "mobile": mobile,
        "message": text,
        "link": link,          # None when the customer has no phone number
        "sent": sent,          # True only via Cloud API
        "api_configured": is_configured(),
    }


# --- Campaigns ----------------------------------------------------------------
AUDIENCES = {
    "all": "كل العملاء / all active customers with a phone",
    "debtors": "عملاء عليهم رصيد / customers with an outstanding balance",
    "top": "أفضل العملاء (٩٠ يوم) / top spenders of the last 90 days",
    "inactive": "عملاء غير نشطين (٦٠ يوم) / no purchase in 60 days",
}


def audience_customers(session: Session, audience: str, limit: int = 500) -> list[m.Customer]:
    """Resolve a campaign audience to actual customers (must have a mobile)."""
    base = select(m.Customer).where(
        m.Customer.is_active == True,  # noqa: E712
        m.Customer.is_deleted == False,  # noqa: E712
        m.Customer.mobile != None,  # noqa: E711
        m.Customer.mobile != "",
    )
    if audience == "debtors":
        return list(session.scalars(base.where(m.Customer.current_balance > 0).limit(limit)))
    if audience == "top":
        since = datetime.now() - timedelta(days=90)
        top_ids = [
            row[0]
            for row in session.execute(
                select(m.Sale.customer_id, func.sum(m.Sale.total_net).label("rev"))
                .where(m.Sale.customer_id != None, m.Sale.is_return == False, m.Sale.sale_date >= since)  # noqa: E711,E712
                .group_by(m.Sale.customer_id)
                .order_by(desc("rev"))
                .limit(limit)
            )
        ]
        if not top_ids:
            return []
        customers = {c.customer_id: c for c in session.scalars(base.where(m.Customer.customer_id.in_(top_ids)))}
        return [customers[i] for i in top_ids if i in customers]
    if audience == "inactive":
        since = datetime.now() - timedelta(days=60)
        recent_ids = select(m.Sale.customer_id).where(
            m.Sale.customer_id != None, m.Sale.sale_date >= since  # noqa: E711
        )
        return list(session.scalars(base.where(m.Customer.customer_id.not_in(recent_ids)).limit(limit)))
    return list(session.scalars(base.limit(limit)))  # "all"


def create_campaign(
    session: Session, name: str, message: str, audience: str, created_by: int | None = None
) -> m.Campaign:
    if audience not in AUDIENCES:
        raise ValueError(f"unknown audience '{audience}'")
    recipients = audience_customers(session, audience)
    campaign = m.Campaign(
        name=name.strip(),
        message=message.strip(),
        audience=audience,
        recipient_count=len(recipients),
        created_by=created_by,
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


def campaign_links(session: Session, campaign: m.Campaign) -> list[dict]:
    """Per-customer click-to-chat links (the no-API delivery mode)."""
    out = []
    for c in audience_customers(session, campaign.audience):
        link = wa_link(c.mobile, campaign.message)
        if link:
            out.append({"customer_id": c.customer_id, "name": c.name_ar, "mobile": c.mobile, "link": link})
    return out


def send_campaign(session: Session, campaign: m.Campaign) -> dict:
    """Send to the whole audience via the Cloud API (when configured) and mark
    the campaign sent. Without the API the campaign is still marked sent —
    delivery happens through the links list the UI shows."""
    recipients = audience_customers(session, campaign.audience)
    sent = 0
    if is_configured():
        for c in recipients:
            if send_text(c.mobile, campaign.message):
                sent += 1
    campaign.status = "sent"
    campaign.recipient_count = len(recipients)
    campaign.sent_count = sent
    campaign.sent_at = datetime.now()
    session.commit()
    return {
        "campaign_id": campaign.campaign_id,
        "recipients": len(recipients),
        "sent_via_api": sent,
        "api_configured": is_configured(),
    }
