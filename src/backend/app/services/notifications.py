"""Notification center + ticker (eStock News_bar / Flag parity).

A single operational feed that surfaces the events staff must not miss —
expiring stock, items below their minimum, and open shortage-sheet requests —
grouped into categories and shown both as a scrolling ribbon (the ticker) and a
full center screen.

The feed is **computed live** from current state, so there is no event row to
store or delete. Each live event carries a stable ``key``; dismissing one writes
a ``NotificationDismissal`` row and the feed then hides that key — mirroring how
eStock's News_bar respects its ``deleted`` flag. Everything here is read-only
against operational data and fail-soft: a broken source never blocks the feed.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services import alerts
from app.services.common import available_stock_filter, branch_filter, money, today

# Flag categories (News_bar/Flag parity), each bilingual with a default severity.
CATEGORIES = {
    "expiry": {"ar": "الصلاحية", "en": "Expiry", "severity": "warning"},
    "low_stock": {"ar": "نواقص المخزون", "en": "Low stock", "severity": "warning"},
    "shortage": {"ar": "كشكول النواقص", "en": "Shortage sheet", "severity": "info"},
}
_SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


def _expiry_events(session: Session, branch_id: int | None, horizon_days: int) -> list[dict]:
    """Expiring (and already-expired) batches as notification events, keyed by
    batch so a dismissal sticks to that specific batch."""
    rows = session.execute(
        select(
            m.StockBatch.batch_id,
            m.StockBatch.exp_date,
            m.StockBatch.amount,
            m.StockBatch.buy_price,
            m.Product.name_ar,
            m.Product.name_en,
            m.Branch.name_ar.label("branch_ar"),
            m.Branch.name_en.label("branch_en"),
        )
        .join(m.Product, m.Product.product_id == m.StockBatch.product_id)
        .join(m.Branch, m.Branch.branch_id == m.StockBatch.branch_id)
        .where(
            m.StockBatch.amount > 0,
            m.StockBatch.exp_date != None,  # noqa: E711
            branch_filter(m.StockBatch, branch_id),
            m.StockBatch.exp_date <= today() + timedelta(days=horizon_days),
        )
        .order_by(m.StockBatch.exp_date.asc())
    ).all()

    events = []
    for batch_id, exp, amount, buy, name_ar, name_en, branch_ar, branch_en in rows:
        days = (exp - today()).days
        severity = "critical" if days <= 0 else ("warning" if days <= 7 else "info")
        loss = money(float(amount) * float(buy))
        if days <= 0:
            title_ar, title_en = "صنف منتهي الصلاحية", "Expired item"
        else:
            title_ar, title_en = f"ينتهي خلال {days} يوم", f"Expires in {days}d"
        events.append({
            "key": f"expiry:{batch_id}",
            "category": "expiry",
            "severity": severity,
            "title_ar": title_ar,
            "title_en": title_en,
            "body_ar": f"{name_ar} — {branch_ar} — كمية {money(amount)} — خسارة متوقعة {loss}",
            "body_en": f"{name_en or name_ar} — {branch_en or branch_ar} — qty {money(amount)} — loss {loss}",
            "ref_type": "batch",
            "ref_id": batch_id,
            "sort_date": exp.isoformat(),
        })
    return events


def _low_stock_events(session: Session, branch_id: int | None) -> list[dict]:
    """Below-minimum products as events (critical when fully out of stock)."""
    events = []
    for item in alerts.low_stock(session, branch_id, limit=200):
        out = item["on_hand"] <= 0
        events.append({
            "key": f"low_stock:{item['product_id']}:{branch_id or 0}",
            "category": "low_stock",
            "severity": "critical" if out else "warning",
            "title_ar": "نفد المخزون" if out else "أقل من الحد الأدنى",
            "title_en": "Out of stock" if out else "Below minimum",
            "body_ar": f"{item['name_ar']} — المتاح {item['on_hand']} / الحد {item['min_stock']}",
            "body_en": f"{item['name_en'] or item['name_ar']} — on-hand {item['on_hand']} / min {item['min_stock']}",
            "ref_type": "product",
            "ref_id": item["product_id"],
            "sort_date": None,
        })
    return events


def _shortage_events(session: Session, branch_id: int | None) -> list[dict]:
    """Open shortage-sheet requests (كشكول النواقص) as events."""
    stmt = (
        select(m.ShortageItem, m.Product.name_ar, m.Product.name_en)
        .join(m.Product, m.Product.product_id == m.ShortageItem.product_id, isouter=True)
        .where(m.ShortageItem.status == "open", branch_filter(m.ShortageItem, branch_id))
        .order_by(m.ShortageItem.created_at.desc())
        .limit(200)
    )
    events = []
    for s, name_ar, name_en in session.execute(stmt):
        label_ar = name_ar or s.product_name or "صنف غير محدد"
        label_en = name_en or s.product_name or "unnamed item"
        events.append({
            "key": f"shortage:{s.shortage_id}",
            "category": "shortage",
            "severity": "info",
            "title_ar": "طلب ناقص",
            "title_en": "Shortage request",
            "body_ar": f"{label_ar} — كمية مطلوبة {money(s.qty_requested)}",
            "body_en": f"{label_en} — requested {money(s.qty_requested)}",
            "ref_type": "shortage",
            "ref_id": s.shortage_id,
            "sort_date": s.created_at.isoformat() if s.created_at else None,
        })
    return events


def _dismissed_keys(session: Session) -> set[str]:
    return set(session.scalars(select(m.NotificationDismissal.event_key)).all())


def _all_events(session: Session, branch_id: int | None, expiry_days: int) -> list[dict]:
    """Every live event across sources, with dismissed keys removed. Each source
    is guarded so one failing never blanks the whole feed."""
    events: list[dict] = []
    for builder in (
        lambda: _expiry_events(session, branch_id, expiry_days),
        lambda: _low_stock_events(session, branch_id),
        lambda: _shortage_events(session, branch_id),
    ):
        try:
            events.extend(builder())
        except Exception:  # noqa: BLE001 — fail-soft: a bad source can't kill the feed
            continue
    dismissed = _dismissed_keys(session)
    return [e for e in events if e["key"] not in dismissed]


def notification_center(session: Session, branch_id: int | None = None, expiry_days: int = 30) -> dict:
    """Full notification center: live events grouped by category, most-severe
    first, with per-category counts and a grand total for the badge."""
    events = _all_events(session, branch_id, expiry_days)

    groups = []
    for code, meta in CATEGORIES.items():
        items = [e for e in events if e["category"] == code]
        items.sort(key=lambda e: (_SEVERITY_RANK.get(e["severity"], 3), e.get("sort_date") or ""))
        groups.append({
            "category": code,
            "label_ar": meta["ar"],
            "label_en": meta["en"],
            "count": len(items),
            "items": items,
        })
    return {
        "total": len(events),
        "critical": sum(1 for e in events if e["severity"] == "critical"),
        "groups": groups,
    }


def ticker(session: Session, branch_id: int | None = None, limit: int = 12, expiry_days: int = 30) -> dict:
    """Flat, severity-ranked headline list for the ribbon, plus the total count
    so the bell can show an unread badge."""
    events = _all_events(session, branch_id, expiry_days)
    events.sort(key=lambda e: (_SEVERITY_RANK.get(e["severity"], 3), e.get("sort_date") or ""))
    return {
        "total": len(events),
        "critical": sum(1 for e in events if e["severity"] == "critical"),
        "items": events[:limit],
    }


def dismiss(session: Session, event_keys: list[str], branch_id: int | None = None, by: int | None = None) -> dict:
    """Dismiss one or more events by key (News_bar 'delete'). Idempotent — a key
    already dismissed is skipped, never duplicated."""
    existing = set(
        session.scalars(
            select(m.NotificationDismissal.event_key).where(
                m.NotificationDismissal.event_key.in_(event_keys or [])
            )
        ).all()
    )
    added = 0
    for key in event_keys or []:
        if not key or key in existing:
            continue
        session.add(m.NotificationDismissal(event_key=key, branch_id=branch_id or None, dismissed_by=by))
        existing.add(key)
        added += 1
    session.commit()
    return {"dismissed": added, "skipped": len(event_keys or []) - added}
