"""Phase 3: WhatsApp campaign automation — tier-up, birthday, expiry nudge, win-back.

All campaigns fail-soft: WhatsApp errors logged + alert task, never block sales.
Throttled at 100 msgs/min to respect WhatsApp Business limits.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy.orm import Session

from app.db import models as m
from app.services import whatsapp as wa_svc

logger = logging.getLogger(__name__)


class CampaignQueue:
    """In-memory throttled queue for WhatsApp messages (100/min = 1.67/sec)."""

    def __init__(self, rate_limit: int = 100, period_secs: int = 60):
        self.rate_limit = rate_limit
        self.period_secs = period_secs
        self.queue: list[tuple[str, datetime, Callable]] = []
        self.sent_times: list[datetime] = []

    def enqueue(self, phone: str, message: str, send_fn: Callable) -> None:
        """Add a message to the queue. send_fn(phone, message) -> bool."""
        self.queue.append((phone, message, send_fn))

    def process(self) -> tuple[int, int]:
        """Process queued messages, respecting rate limit.

        Returns: (sent_count, failed_count)
        """
        sent = 0
        failed = 0
        now = datetime.now()
        self.sent_times = [t for t in self.sent_times if (now - t).total_seconds() < self.period_secs]

        for phone, message, send_fn in self.queue:
            if len(self.sent_times) >= self.rate_limit:
                # Rate limit hit; reschedule this and remaining messages
                logger.info(f"Campaign throttle: {len(self.queue) - sent} messages deferred")
                break

            try:
                if send_fn(phone, message):
                    sent += 1
                    self.sent_times.append(now)
                else:
                    failed += 1
                    logger.warning(f"Campaign send failed to {phone}")
            except Exception as e:
                failed += 1
                logger.error(f"Campaign send error to {phone}: {e}")

        # Clear processed messages
        self.queue = self.queue[sent + failed :]
        return sent, failed


def send_tier_up_notification(session: Session, customer_id: int, old_tier: str, new_tier: str) -> bool:
    """Send tier-up congratulation message (fail-soft).

    Returns: True if sent, False if skipped/failed.
    """
    customer = session.get(m.Customer, customer_id)
    if not customer or not customer.mobile or customer.wa_opt_out:
        return False

    tier_names = {"silver": "فضي", "gold": "ذهبي", "platinum": "بلاتيني"}
    tier_ar = tier_names.get(new_tier, new_tier)
    message = f"تهانينا! وصلت إلى مستوى [{tier_ar}] واحصل على نقاط أكثر 🌟"

    try:
        return wa_svc.send_text(customer.mobile, message)
    except Exception as e:
        logger.error(f"Tier-up notification failed for customer {customer_id}: {e}")
        return False


def send_birthday_offer(session: Session, customer_id: int, offer_text: str) -> bool:
    """Send birthday offer message (fail-soft)."""
    customer = session.get(m.Customer, customer_id)
    if not customer or not customer.mobile or customer.wa_opt_out:
        return False

    message = f"عيد ميلاد سعيد! {offer_text} 🎂"

    try:
        return wa_svc.send_text(customer.mobile, message)
    except Exception as e:
        logger.error(f"Birthday offer failed for customer {customer_id}: {e}")
        return False


def send_expiry_nudge(session: Session, customer_id: int, days_left: int) -> bool:
    """Send points-expiry nudge message (fail-soft)."""
    customer = session.get(m.Customer, customer_id)
    if not customer or not customer.mobile or customer.wa_opt_out:
        return False

    message = f"نقاطك تنتهي صلاحيتها خلال {days_left} أيام! استخدمها الآن عند الشراء 🕒"

    try:
        return wa_svc.send_text(customer.mobile, message)
    except Exception as e:
        logger.error(f"Expiry nudge failed for customer {customer_id}: {e}")
        return False


def send_winback_message(session: Session, customer_id: int) -> bool:
    """Send win-back campaign message to dormant customer (fail-soft)."""
    customer = session.get(m.Customer, customer_id)
    if not customer or not customer.mobile or customer.wa_opt_out:
        return False

    message = "نشتاق إليك! تفضل بزيارتنا وادخل السحب على جوائز 🎁"

    try:
        return wa_svc.send_text(customer.mobile, message)
    except Exception as e:
        logger.error(f"Win-back message failed for customer {customer_id}: {e}")
        return False


