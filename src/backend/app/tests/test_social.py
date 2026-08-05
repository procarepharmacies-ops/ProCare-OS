"""Tests for social media content calendar and AI copywriting (Phase 4)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.db import models as m
from app.services import social as social_svc


@pytest.fixture
def sample_context() -> dict:
    """Sample context for AI copywriting."""
    return {
        "offer_name": "Summer Sale",
        "discount": "50%",
        "product_type": "Health & Wellness",
        "urgency": "This week only",
    }


def test_generate_social_copy_fallback(session):
    """Test fallback template-based copywriting when LLM unavailable."""
    context = {"offer_name": "Test Offer", "discount": "20%"}
    body_ar, body_en = social_svc.generate_social_copy(session, context)

    assert isinstance(body_ar, str)
    assert isinstance(body_en, str)
    assert len(body_ar) > 0
    assert len(body_en) > 0
    # Fallback templates should contain Arabic and English emoji
    assert any(emoji in body_ar for emoji in ["🎉", "💊", "🔔", "⭐", "🎁"])
    assert any(emoji in body_en for emoji in ["🎉", "💊", "🔔", "⭐", "🎁"])


def test_create_social_post_basic(session):
    """Test creating a basic social media post."""
    post = social_svc.create_social_post(
        session,
        channel="ig",
        body_ar="🎉 عرض حصري هذا الأسبوع فقط!",
        body_en="🎉 Exclusive offer this week only!",
        title="Summer Sale",
    )
    session.commit()

    assert post.post_id is not None
    assert post.channel == "ig"
    assert post.body_ar == "🎉 عرض حصري هذا الأسبوع فقط!"
    assert post.body_en == "🎉 Exclusive offer this week only!"
    assert post.title == "Summer Sale"
    assert post.status == "draft"


def test_create_social_post_with_scheduling(session):
    """Test creating a post with scheduled_at datetime."""
    scheduled = datetime.now() + timedelta(days=7)
    post = social_svc.create_social_post(
        session,
        channel="fb",
        body_ar="محتوى جديد قادم قريباً",
        body_en="New content coming soon",
        scheduled_at=scheduled,
    )
    session.commit()

    assert post.scheduled_at == scheduled
    assert post.status == "draft"


def test_create_social_post_with_promo_code(session):
    """Test creating a post linked to a promo code."""
    from app.services import promo as promo_svc

    # Create promo code first
    valid_from = datetime.now() - timedelta(days=1)
    valid_until = datetime.now() + timedelta(days=30)
    promo = promo_svc.create_promo_code(
        session,
        code="SOCIALSALE20",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
        description_ar="خصم من وسائل التواصل",
        description_en="Social media discount",
    )
    session.commit()

    # Create post with promo code
    post = social_svc.create_social_post(
        session,
        channel="ig",
        body_ar="احصل على 20% باستخدام الكود",
        body_en="Get 20% using code SOCIALSALE20",
        promo_code="SOCIALSALE20",
    )
    session.commit()

    assert post.promo_code == "SOCIALSALE20"


def test_create_social_post_defaults_body_en_to_body_ar(session):
    """Test that body_en defaults to body_ar if not provided."""
    post = social_svc.create_social_post(
        session,
        channel="wa-status",
        body_ar="محتوى بالعربية فقط",
        body_en=None,
    )
    session.commit()

    assert post.body_en == "محتوى بالعربية فقط"


def test_approve_post_from_draft(session):
    """Test approving a draft post."""
    post = social_svc.create_social_post(
        session,
        channel="ig",
        body_ar="محتوى",
        body_en="Content",
    )
    session.commit()

    approved = social_svc.approve_post(session, post.post_id, approved_by=1)
    session.commit()

    assert approved.status == "approved"
    assert approved.approved_by == 1


def test_approve_post_already_approved(session):
    """Test approving an already-approved post (idempotent)."""
    post = social_svc.create_social_post(
        session,
        channel="fb",
        body_ar="محتوى",
        body_en="Content",
    )
    session.commit()

    social_svc.approve_post(session, post.post_id, approved_by=1)
    session.commit()

    # Second approval should not raise error
    approved = social_svc.approve_post(session, post.post_id, approved_by=2)
    session.commit()

    assert approved.status == "approved"
    assert approved.approved_by == 2


def test_approve_post_not_found(session):
    """Test approving a post that doesn't exist."""
    with pytest.raises(ValueError, match="not found"):
        social_svc.approve_post(session, 99999, approved_by=1)


def test_publish_post_from_approved(session):
    """Test publishing an approved post."""
    post = social_svc.create_social_post(
        session,
        channel="ig",
        body_ar="محتوى",
        body_en="Content",
    )
    session.commit()

    social_svc.approve_post(session, post.post_id, approved_by=1)
    session.commit()

    published = social_svc.publish_post(session, post.post_id)
    session.commit()

    assert published.status == "published"
    assert published.published_at is not None


def test_publish_post_from_scheduled(session):
    """Test publishing a scheduled post before its scheduled time."""
    scheduled = datetime.now() + timedelta(days=7)
    post = social_svc.create_social_post(
        session,
        channel="ig",
        body_ar="محتوى",
        body_en="Content",
        scheduled_at=scheduled,
    )
    session.commit()

    social_svc.approve_post(session, post.post_id, approved_by=1)
    session.commit()

    # Change status to scheduled
    post = session.get(m.SocialPost, post.post_id)
    post.status = "scheduled"
    session.commit()

    published = social_svc.publish_post(session, post.post_id)
    session.commit()

    assert published.status == "published"


def test_publish_post_not_found(session):
    """Test publishing a post that doesn't exist."""
    with pytest.raises(ValueError, match="not found"):
        social_svc.publish_post(session, 99999)


def test_publish_post_invalid_status(session):
    """Test publishing a post that's in draft status (not approved/scheduled)."""
    post = social_svc.create_social_post(
        session,
        channel="ig",
        body_ar="محتوى",
        body_en="Content",
    )
    session.commit()

    with pytest.raises(ValueError, match="Cannot publish"):
        social_svc.publish_post(session, post.post_id)


def test_get_month_posts_current_month(session):
    """Test retrieving posts for current month."""
    today = datetime.now()
    post1 = social_svc.create_social_post(
        session,
        channel="ig",
        body_ar="محتوى 1",
        body_en="Content 1",
        scheduled_at=today,
    )
    post2 = social_svc.create_social_post(
        session,
        channel="fb",
        body_ar="محتوى 2",
        body_en="Content 2",
        scheduled_at=today + timedelta(days=5),
    )
    session.commit()

    posts = social_svc.get_month_posts(session, month=today.month)

    assert len(posts) >= 2
    assert any(p.post_id == post1.post_id for p in posts)
    assert any(p.post_id == post2.post_id for p in posts)


def test_get_month_posts_filtered_by_channel(session):
    """Test retrieving posts for a specific channel."""
    today = datetime.now()
    ig_post = social_svc.create_social_post(
        session,
        channel="ig",
        body_ar="محتوى إنستغرام",
        body_en="Instagram content",
        scheduled_at=today,
    )
    fb_post = social_svc.create_social_post(
        session,
        channel="fb",
        body_ar="محتوى فيسبوك",
        body_en="Facebook content",
        scheduled_at=today,
    )
    session.commit()

    ig_posts = social_svc.get_month_posts(session, channel="ig", month=today.month)

    assert all(p.channel == "ig" for p in ig_posts)
    assert any(p.post_id == ig_post.post_id for p in ig_posts)
    assert not any(p.post_id == fb_post.post_id for p in ig_posts)


def test_get_month_posts_empty_month(session):
    """Test retrieving posts for a month with no posts."""
    next_year_month = datetime.now().month + 6
    if next_year_month > 12:
        next_year_month -= 12

    posts = social_svc.get_month_posts(session, month=next_year_month)

    assert isinstance(posts, list)


def test_get_post_with_promo(session):
    """Test retrieving a post with linked promo details."""
    from app.services import promo as promo_svc

    # Create promo code
    valid_from = datetime.now() - timedelta(days=1)
    valid_until = datetime.now() + timedelta(days=30)
    promo = promo_svc.create_promo_code(
        session,
        code="TEST20",
        discount_type="percentage",
        discount_value=20.0,
        valid_from=valid_from,
        valid_until=valid_until,
        description_ar="اختبار",
        description_en="Test",
    )
    session.commit()

    # Create post with promo
    post = social_svc.create_social_post(
        session,
        channel="ig",
        body_ar="محتوى",
        body_en="Content",
        promo_code="TEST20",
    )
    session.commit()

    post_dict = social_svc.get_post_with_promo(session, post.post_id)

    assert post_dict["post_id"] == post.post_id
    assert post_dict["promo_code"] == "TEST20"
    assert post_dict["promo_details"] is not None
    assert post_dict["promo_details"]["code"] == "TEST20"
    assert post_dict["promo_details"]["discount_type"] == "percentage"
    assert post_dict["promo_details"]["discount_value"] == 20.0


def test_get_post_with_promo_no_promo(session):
    """Test retrieving a post with no linked promo."""
    post = social_svc.create_social_post(
        session,
        channel="ig",
        body_ar="محتوى",
        body_en="Content",
    )
    session.commit()

    post_dict = social_svc.get_post_with_promo(session, post.post_id)

    assert post_dict["post_id"] == post.post_id
    assert post_dict["promo_code"] is None
    assert post_dict["promo_details"] is None


def test_get_post_with_promo_not_found(session):
    """Test retrieving a post that doesn't exist."""
    with pytest.raises(ValueError, match="not found"):
        social_svc.get_post_with_promo(session, 99999)
