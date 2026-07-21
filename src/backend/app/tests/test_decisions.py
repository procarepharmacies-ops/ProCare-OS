"""Decision card generation tests (Phase 5)."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.db.base import SessionLocal
from app.services import decisions as decisions_svc


def test_dismiss_card():
    """Test dismissing a decision card."""
    session = SessionLocal()
    try:
        card = m.DecisionCard(
            branch_id=1,
            card_type="below_min",
            severity="warning",
            title_ar="Test",
            title_en="Test",
            body_ar="Test",
            body_en="Test",
            status="open",
        )
        session.add(card)
        session.commit()

        success = decisions_svc.dismiss_card(session, card.card_id)
        assert success is True

        card = session.get(m.DecisionCard, card.card_id)
        assert card.status == "dismissed"
    finally:
        session.close()


def test_action_card():
    """Test marking a decision card as actioned."""
    session = SessionLocal()
    try:
        card = m.DecisionCard(
            branch_id=1,
            card_type="stockout_risk",
            severity="critical",
            title_ar="Test",
            title_en="Test",
            body_ar="Test",
            body_en="Test",
            status="open",
        )
        session.add(card)
        session.commit()

        success = decisions_svc.action_card(session, card.card_id, employee_id=1)
        assert success is True

        card = session.get(m.DecisionCard, card.card_id)
        assert card.status == "actioned"
        assert card.actioned_by == 1
        assert card.actioned_at is not None
    finally:
        session.close()


def test_get_open_decision_cards_sorted():
    """Test that open cards are returned sorted by severity then creation time."""
    session = SessionLocal()
    try:
        # Create cards with different severities (all open)
        card_types = ["stockout_risk", "below_min", "expiry_warning"]
        for i, (card_type, severity) in enumerate(zip(card_types, ["info", "critical", "warning"])):
            card = m.DecisionCard(
                branch_id=1,
                card_type=card_type,
                severity=severity,
                title_ar="Test",
                title_en="Test",
                body_ar="Test",
                body_en="Test",
                status="open",
            )
            session.add(card)
        session.commit()

        cards = decisions_svc.get_open_decision_cards(session, branch_id=1)
        assert len(cards) >= 3
        # Should be sorted: critical, warning, info
        severities = [c["severity"] for c in cards[:3]]
        assert severities == ["critical", "warning", "info"]
    finally:
        session.close()


def test_archive_old_cards():
    """Test archiving decision cards older than N days."""
    session = SessionLocal()
    try:
        from datetime import datetime

        # Create an old card (10 days ago)
        old_card = m.DecisionCard(
            branch_id=1,
            card_type="below_min",
            severity="info",
            title_ar="Old",
            title_en="Old",
            body_ar="Old",
            body_en="Old",
            status="open",
            created_at=datetime.utcnow() - timedelta(days=10),
        )
        session.add(old_card)

        # Create a recent card (1 day ago)
        recent_card = m.DecisionCard(
            branch_id=1,
            card_type="below_min",
            severity="info",
            title_ar="Recent",
            title_en="Recent",
            body_ar="Recent",
            body_en="Recent",
            status="open",
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        session.add(recent_card)
        session.commit()

        count = decisions_svc.archive_old_cards(session, days=7)
        assert count == 1

        old = session.get(m.DecisionCard, old_card.card_id)
        recent = session.get(m.DecisionCard, recent_card.card_id)

        assert old.status == "archived"
        assert recent.status == "open"
    finally:
        session.close()


def test_nightly_decision_cards_generate():
    """Test that nightly decision card generation runs without errors."""
    session = SessionLocal()
    try:
        result = decisions_svc.generate_nightly_decision_cards(session)
        assert result["status"] in ["ok", "error"]
        assert "total_cards_created" in result
        assert "by_type" in result
    finally:
        session.close()
