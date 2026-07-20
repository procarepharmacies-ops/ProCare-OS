"""Social media content calendar, AI copywriting, and promo code management.

Endpoints for creating, approving, and publishing social media posts with
linked promo codes for campaign tracking. AI-powered copywriting with
fallback templates when API keys unavailable.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db import models as m
from app.db.base import get_session
from app.services import promo as promo_svc
from app.services import social as social_svc

router = APIRouter(prefix="/marketing", tags=["marketing"])


# --- Pydantic Models ---


class GenerateCopyIn(BaseModel):
    context: dict
    brand_name: str = "بروكير / ProCare"


class GenerateCopyOut(BaseModel):
    body_ar: str
    body_en: str


class CreatePostIn(BaseModel):
    channel: str
    body_ar: str
    body_en: str | None = None
    title: str | None = None
    image_ref: str | None = None
    scheduled_at: datetime | None = None
    promo_code: str | None = None


class PostOut(BaseModel):
    post_id: int
    channel: str
    title: str | None
    body_ar: str
    body_en: str
    image_ref: str | None
    status: str
    scheduled_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    promo_code: str | None
    promo_details: dict | None = None


class PostWithPromoOut(BaseModel):
    post_id: int
    channel: str
    title: str | None
    body_ar: str
    body_en: str
    image_ref: str | None
    status: str
    scheduled_at: datetime | None
    published_at: datetime | None
    promo_code: str | None
    promo_details: dict | None = None


class CreatePromoCodeIn(BaseModel):
    code: str
    discount_type: str
    discount_value: float
    valid_from: datetime
    valid_until: datetime
    description_ar: str | None = None
    description_en: str | None = None
    max_uses: int | None = None


class PromoCodeOut(BaseModel):
    code: str
    discount_type: str
    discount_value: float
    valid_from: datetime
    valid_until: datetime
    description_ar: str | None
    description_en: str | None
    max_uses: int | None
    current_uses: int
    is_active: bool
    remaining_uses: str


# --- Social Post Endpoints ---


@router.post("/posts/generate-copy", dependencies=[Depends(auth_guard())])
def generate_social_copy(
    data: GenerateCopyIn,
    session: Session = Depends(get_session),
) -> GenerateCopyOut:
    """Generate bilingual social media copy using AI or fallback templates.

    Args:
        context: Dict with keys like 'offer_name', 'discount', 'product_type', 'urgency'
        brand_name: Brand name to include in the copy

    Returns:
        Bilingual copy (Arabic + English) with emoji and CTAs
    """
    body_ar, body_en = social_svc.generate_social_copy(session, data.context, data.brand_name)
    return GenerateCopyOut(body_ar=body_ar, body_en=body_en)


@router.post("/posts", dependencies=[Depends(auth_guard())])
def create_social_post(
    data: CreatePostIn,
    session: Session = Depends(get_session),
    user_id: int = Depends(auth_guard()),
) -> PostOut:
    """Create a draft social media post (no commit; caller must commit session).

    Args:
        channel: 'fb' / 'ig' / 'wa-status' / 'tiktok' / 'linkedin'
        body_ar: Arabic content (required)
        body_en: English content (optional; defaults to body_ar)
        title: Post title (optional)
        image_ref: Image URL or base64 reference (optional)
        scheduled_at: Publication datetime (optional)
        promo_code: Linked promo code (optional)

    Returns:
        New SocialPost object
    """
    if data.channel not in ("fb", "ig", "wa-status", "tiktok", "linkedin"):
        raise HTTPException(status_code=400, detail=f"Invalid channel: {data.channel}")

    if data.promo_code:
        try:
            promo_svc.validate_promo_code(session, data.promo_code)
        except promo_svc.PromoError as e:
            raise HTTPException(status_code=400, detail=e.message)

    post = social_svc.create_social_post(
        session,
        channel=data.channel,
        body_ar=data.body_ar,
        body_en=data.body_en,
        title=data.title,
        image_ref=data.image_ref,
        scheduled_at=data.scheduled_at,
        created_by=user_id,
        promo_code=data.promo_code,
    )
    session.commit()

    promo_details = None
    if post.promo_code:
        promo_report = promo_svc.get_promo_usage_report(session, post.promo_code)
        if promo_report:
            promo_details = promo_report[0]

    return PostOut(
        post_id=post.post_id,
        channel=post.channel,
        title=post.title,
        body_ar=post.body_ar,
        body_en=post.body_en,
        image_ref=post.image_ref,
        status=post.status,
        scheduled_at=post.scheduled_at,
        published_at=post.published_at,
        created_at=post.created_at,
        promo_code=post.promo_code,
        promo_details=promo_details,
    )


@router.get("/posts/{post_id}", dependencies=[Depends(auth_guard())])
def get_post_with_promo(
    post_id: int,
    session: Session = Depends(get_session),
) -> PostWithPromoOut:
    """Get a post with its linked promo code details (if any).

    Returns:
        Post with promo details nested
    """
    try:
        post_dict = social_svc.get_post_with_promo(session, post_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return PostWithPromoOut(
        post_id=post_dict["post_id"],
        channel=post_dict["channel"],
        title=post_dict["title"],
        body_ar=post_dict["body_ar"],
        body_en=post_dict["body_en"],
        image_ref=post_dict["image_ref"],
        status=post_dict["status"],
        scheduled_at=post_dict["scheduled_at"],
        published_at=post_dict["published_at"],
        promo_code=post_dict["promo_code"],
        promo_details=post_dict["promo_details"],
    )


@router.get("/calendar", dependencies=[Depends(auth_guard())])
def get_month_posts(
    channel: str | None = None,
    month: int | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """Get all posts scheduled for a month (calendar view).

    Args:
        channel: Filter by channel (optional)
        month: Month number (1-12); defaults to current month

    Returns:
        List of posts grouped by date
    """
    posts = social_svc.get_month_posts(session, channel, month)

    grouped = {}
    for post in posts:
        key = post.scheduled_at.date().isoformat() if post.scheduled_at else "unscheduled"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({
            "post_id": post.post_id,
            "channel": post.channel,
            "title": post.title,
            "body_ar": post.body_ar[:100] + "..." if len(post.body_ar) > 100 else post.body_ar,
            "status": post.status,
            "promo_code": post.promo_code,
        })

    return {
        "month": month or datetime.now().month,
        "channel_filter": channel,
        "posts_by_date": grouped,
        "total_posts": len(posts),
    }


@router.patch("/posts/{post_id}/approve", dependencies=[Depends(auth_guard())])
def approve_post(
    post_id: int,
    session: Session = Depends(get_session),
    user_id: int = Depends(auth_guard()),
) -> PostOut:
    """Approve a draft post for publishing.

    Returns:
        Updated SocialPost object
    """
    try:
        post = social_svc.approve_post(session, post_id, approved_by=user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session.commit()

    promo_details = None
    if post.promo_code:
        promo_report = promo_svc.get_promo_usage_report(session, post.promo_code)
        if promo_report:
            promo_details = promo_report[0]

    return PostOut(
        post_id=post.post_id,
        channel=post.channel,
        title=post.title,
        body_ar=post.body_ar,
        body_en=post.body_en,
        image_ref=post.image_ref,
        status=post.status,
        scheduled_at=post.scheduled_at,
        published_at=post.published_at,
        created_at=post.created_at,
        promo_code=post.promo_code,
        promo_details=promo_details,
    )


@router.post("/posts/{post_id}/publish", dependencies=[Depends(auth_guard())])
def publish_post(
    post_id: int,
    session: Session = Depends(get_session),
) -> PostOut:
    """Publish an approved post immediately.

    Returns:
        Updated SocialPost object
    """
    try:
        post = social_svc.publish_post(session, post_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session.commit()

    promo_details = None
    if post.promo_code:
        promo_report = promo_svc.get_promo_usage_report(session, post.promo_code)
        if promo_report:
            promo_details = promo_report[0]

    return PostOut(
        post_id=post.post_id,
        channel=post.channel,
        title=post.title,
        body_ar=post.body_ar,
        body_en=post.body_en,
        image_ref=post.image_ref,
        status=post.status,
        scheduled_at=post.scheduled_at,
        published_at=post.published_at,
        created_at=post.created_at,
        promo_code=post.promo_code,
        promo_details=promo_details,
    )


# --- Promo Code Endpoints ---


@router.post("/promo-codes", dependencies=[Depends(auth_guard())])
def create_promo_code(
    data: CreatePromoCodeIn,
    session: Session = Depends(get_session),
    user_id: int = Depends(auth_guard()),
) -> PromoCodeOut:
    """Create a new promo code.

    Args:
        code: Unique code (e.g., 'SUMMER20', 'FIRSTBUY')
        discount_type: 'percentage' or 'fixed'
        discount_value: Discount amount (% or EGP)
        valid_from: Start datetime
        valid_until: End datetime
        description_ar: Arabic description (optional)
        description_en: English description (optional)
        max_uses: Maximum redemptions (None = unlimited)

    Returns:
        New PromoCode object
    """
    try:
        promo = promo_svc.create_promo_code(
            session,
            code=data.code,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            valid_from=data.valid_from,
            valid_until=data.valid_until,
            description_ar=data.description_ar,
            description_en=data.description_en,
            max_uses=data.max_uses,
            created_by=user_id,
        )
        session.commit()
    except promo_svc.PromoError as e:
        raise HTTPException(status_code=400, detail=e.message)

    remaining = "unlimited"
    if promo.max_uses:
        remaining = str(max(0, promo.max_uses - promo.current_uses))

    return PromoCodeOut(
        code=promo.code,
        discount_type=promo.discount_type,
        discount_value=float(promo.discount_value),
        valid_from=promo.valid_from,
        valid_until=promo.valid_until,
        description_ar=promo.description_ar,
        description_en=promo.description_en,
        max_uses=promo.max_uses,
        current_uses=promo.current_uses,
        is_active=promo.is_active,
        remaining_uses=remaining,
    )


@router.get("/promo-codes", dependencies=[Depends(auth_guard())])
def list_promo_codes(
    session: Session = Depends(get_session),
) -> dict:
    """List all promo codes with usage statistics.

    Returns:
        List of promo codes ordered by creation date (newest first)
    """
    report = promo_svc.get_promo_usage_report(session)
    return {
        "total": len(report),
        "codes": report,
    }


@router.get("/promo-codes/active", dependencies=[Depends(auth_guard())])
def get_active_promo_codes(
    session: Session = Depends(get_session),
) -> dict:
    """Get all currently valid and active promo codes.

    Returns:
        List of promo codes that are active and within validity window
    """
    codes = promo_svc.get_active_promo_codes(session)
    return {
        "total": len(codes),
        "codes": [
            {
                "code": c.code,
                "discount_type": c.discount_type,
                "discount_value": float(c.discount_value),
                "description_ar": c.description_ar,
                "description_en": c.description_en,
                "valid_until": c.valid_until.isoformat(),
            }
            for c in codes
        ],
    }


@router.get("/promo-codes/{code}/validate", dependencies=[Depends(auth_guard())])
def validate_promo_code(
    code: str,
    invoice_total: float = 0.0,
    session: Session = Depends(get_session),
) -> dict:
    """Validate a promo code for redemption at POS.

    Args:
        code: Promo code to validate
        invoice_total: Invoice total in EGP (for discount calculation)

    Returns:
        Validation result with discount details if valid
    """
    try:
        promo = promo_svc.validate_promo_code(session, code, invoice_total)
    except promo_svc.PromoError as e:
        raise HTTPException(status_code=400, detail=e.message)

    discount_amount, message = promo_svc.calculate_discount(promo, invoice_total)

    return {
        "valid": True,
        "code": promo.code,
        "discount_type": promo.discount_type,
        "discount_value": float(promo.discount_value),
        "invoice_total": invoice_total,
        "discount_amount": discount_amount,
        "final_total": round(invoice_total - discount_amount, 2),
        "message": message,
    }


@router.patch("/promo-codes/{code}/deactivate", dependencies=[Depends(auth_guard())])
def deactivate_promo_code(
    code: str,
    session: Session = Depends(get_session),
) -> PromoCodeOut:
    """Deactivate a promo code (prevent further redemptions).

    Returns:
        Updated PromoCode object
    """
    try:
        promo = promo_svc.deactivate_promo_code(session, code)
    except promo_svc.PromoError as e:
        raise HTTPException(status_code=400, detail=e.message)

    session.commit()

    remaining = "unlimited"
    if promo.max_uses:
        remaining = str(max(0, promo.max_uses - promo.current_uses))

    return PromoCodeOut(
        code=promo.code,
        discount_type=promo.discount_type,
        discount_value=float(promo.discount_value),
        valid_from=promo.valid_from,
        valid_until=promo.valid_until,
        description_ar=promo.description_ar,
        description_en=promo.description_en,
        max_uses=promo.max_uses,
        current_uses=promo.current_uses,
        is_active=promo.is_active,
        remaining_uses=remaining,
    )
