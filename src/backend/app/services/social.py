"""Phase 4: Social media content studio — content calendar, AI copywriting, promo codes.

All features fail-soft: LLM API failures fall back to template-based copywriting.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy.orm import Session

from app.db import models as m
from app.services.llm import complete as llm_complete

logger = logging.getLogger(__name__)


# --- AI Copywriting with Fallback Templates -----------------------------------

FALLBACK_TEMPLATES_AR = [
    "🎉 عروض حصرية هذا الأسبوع فقط! اكتشف أحدث منتجاتنا واستمتع بخصومات تصل إلى 50٪",
    "💊 صحتك أهم أولوياتنا. تابعونا للحصول على نصائح صحية يومية وأفضل العروض",
    "🔔 لا تفوت فرصة! منتجات جديدة وصلت للتو بأسعار خاصة لعملائنا الكرام",
    "⭐ شهر التغيير الصحي! كل ما تحتاجه لنمط حياة أفضل متوفر الآن",
    "🎁 اشتري اليوم واحصل على هديتك! عروض محدودة على منتجات صحية موثوقة",
]

FALLBACK_TEMPLATES_EN = [
    "🎉 Exclusive offers this week only! Discover our latest products with up to 50% off",
    "💊 Your health is our priority. Follow us for daily health tips and amazing deals",
    "🔔 Don't miss out! New products just arrived with special prices for our valued customers",
    "⭐ Health transformation month! Everything you need for a better lifestyle available now",
    "🎁 Shop today and get your gift! Limited offers on trusted health products",
]


def generate_social_copy(
    session: Session, context: dict, brand_name: str = "بروكير / Brocker"
) -> tuple[str, str]:
    """Generate bilingual social media copy using LLM or fallback templates.

    Args:
        session: Database session for context queries
        context: Dict with keys like 'offer_name', 'discount', 'product_type', 'urgency'
        brand_name: Brand name to include in the copy

    Returns:
        (body_ar, body_en) tuple
    """
    prompt = f"""Generate engaging, bilingual social media copy for a pharmacy.

Brand: {brand_name}
Context: {context}

Requirements:
- Arabic (Modern Standard Arabic - فصحى): Natural, compelling, healthcare-focused
- English: Clear, engaging, aligned with Arabic tone
- Include emoji for visual appeal
- 200 chars max (Arabic) / 150 chars max (English)
- Call-to-action (shop now / learn more / don't miss out)
- Professional but approachable tone

Return format:
ARABIC: [copy]
ENGLISH: [copy]"""

    try:
        result = llm_complete(prompt, max_tokens=500)
        if result and "ARABIC:" in result and "ENGLISH:" in result:
            lines = result.split("\n")
            body_ar = ""
            body_en = ""
            for line in lines:
                if line.startswith("ARABIC:"):
                    body_ar = line.replace("ARABIC:", "").strip()
                elif line.startswith("ENGLISH:"):
                    body_en = line.replace("ENGLISH:", "").strip()
            if body_ar and body_en:
                return body_ar, body_en
    except Exception as e:
        logger.warning(f"LLM copy generation failed, using fallback: {e}")

    # Fallback: random templates
    import random

    body_ar = random.choice(FALLBACK_TEMPLATES_AR)
    body_en = random.choice(FALLBACK_TEMPLATES_EN)
    return body_ar, body_en


def create_social_post(
    session: Session,
    channel: str,
    body_ar: str,
    body_en: str | None = None,
    title: str | None = None,
    image_ref: str | None = None,
    scheduled_at: datetime | None = None,
    created_by: int | None = None,
    promo_code: str | None = None,
) -> m.SocialPost:
    """Create a draft social media post (no commit).

    Args:
        session: Database session
        channel: 'fb' / 'ig' / 'wa-status' / 'tiktok' / 'linkedin'
        body_ar: Arabic content (required)
        body_en: English content (optional)
        title: Post title (optional)
        image_ref: Image URL or base64 reference (optional)
        scheduled_at: Publication datetime (optional)
        created_by: Employee ID (optional)
        promo_code: Linked promo code (optional)

    Returns:
        New SocialPost object (not yet committed)
    """
    post = m.SocialPost(
        channel=channel,
        body_ar=body_ar,
        body_en=body_en or body_ar,
        title=title,
        image_ref=image_ref,
        status="draft",
        scheduled_at=scheduled_at,
        created_by=created_by,
        promo_code=promo_code,
    )
    session.add(post)
    return post


def approve_post(session: Session, post_id: int, approved_by: int | None = None) -> m.SocialPost:
    """Approve a draft post for publishing (no commit).

    Returns:
        Updated SocialPost object
    """
    post = session.get(m.SocialPost, post_id)
    if not post:
        raise ValueError(f"Post {post_id} not found")
    if post.status not in ("draft", "approved"):
        raise ValueError(f"Cannot approve post with status {post.status}")
    post.status = "approved"
    post.approved_by = approved_by
    return post


def publish_post(session: Session, post_id: int) -> m.SocialPost:
    """Publish an approved post immediately (no commit).

    Returns:
        Updated SocialPost object
    """
    post = session.get(m.SocialPost, post_id)
    if not post:
        raise ValueError(f"Post {post_id} not found")
    if post.status not in ("approved", "scheduled"):
        raise ValueError(f"Cannot publish post with status {post.status}")
    post.status = "published"
    post.published_at = datetime.now()
    return post


def get_month_posts(session: Session, channel: str | None = None, month: int | None = None) -> list[m.SocialPost]:
    """Get all posts scheduled for a month (for calendar view).

    Args:
        session: Database session
        channel: Filter by channel (optional)
        month: Month number (1-12); defaults to current month

    Returns:
        List of SocialPost objects
    """
    from sqlalchemy import and_, extract, select

    if month is None:
        month = datetime.now().month
    year = datetime.now().year

    query = select(m.SocialPost).where(
        and_(
            extract("month", m.SocialPost.scheduled_at) == month,
            extract("year", m.SocialPost.scheduled_at) == year,
        )
    )
    if channel:
        query = query.where(m.SocialPost.channel == channel)

    return session.scalars(query).all()


def get_post_with_promo(session: Session, post_id: int) -> dict:
    """Get a post with its linked promo code details (if any).

    Returns:
        Dict with post + promo_code details
    """
    post = session.get(m.SocialPost, post_id)
    if not post:
        raise ValueError(f"Post {post_id} not found")

    promo = None
    if post.promo_code:
        promo = session.query(m.PromoCode).filter(m.PromoCode.code == post.promo_code).first()

    return {
        "post_id": post.post_id,
        "channel": post.channel,
        "title": post.title,
        "body_ar": post.body_ar,
        "body_en": post.body_en,
        "image_ref": post.image_ref,
        "status": post.status,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "promo_code": post.promo_code,
        "promo_details": {
            "code": promo.code,
            "discount_type": promo.discount_type,
            "discount_value": float(promo.discount_value),
            "valid_until": promo.valid_until.isoformat(),
            "current_uses": promo.current_uses,
            "max_uses": promo.max_uses,
        }
        if promo
        else None,
    }
