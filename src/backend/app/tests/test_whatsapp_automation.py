"""Tests for WhatsApp operational automation (manager alerts + return confirm).

Sends are self-gating and fail-soft: nothing goes out unless the Cloud API AND
a manager phone are configured, and a send failure never raises.
"""
from __future__ import annotations

import importlib

from app.services import whatsapp


def test_notify_manager_skips_without_phone(monkeypatch):
    monkeypatch.delenv("MANAGER_PHONE", raising=False)
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_ID", raising=False)
    import app.config as cfg
    importlib.reload(cfg)
    importlib.reload(whatsapp)
    # No phone, no API → no send, no error.
    assert whatsapp.notify_manager("hello") is False


def test_notify_manager_sends_when_configured(monkeypatch):
    monkeypatch.setenv("MANAGER_PHONE", "01000000000")
    monkeypatch.setenv("WHATSAPP_TOKEN", "tok")
    monkeypatch.setenv("WHATSAPP_PHONE_ID", "123")
    import app.config as cfg
    importlib.reload(cfg)
    importlib.reload(whatsapp)

    captured = {}

    def fake_send(mobile, text):
        captured["mobile"] = mobile
        captured["text"] = text
        return True

    monkeypatch.setattr(whatsapp, "send_text", fake_send)
    assert whatsapp.notify_manager("تنبيه") is True
    assert captured["mobile"] == "01000000000"

    # cleanup
    monkeypatch.delenv("MANAGER_PHONE", raising=False)
    monkeypatch.delenv("WHATSAPP_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_ID", raising=False)
    importlib.reload(cfg)
    importlib.reload(whatsapp)


def test_message_builders_shape():
    assert "بروكير" in whatsapp.daily_report_message({"sales_today": 100, "bills_today": 3})
    assert "طلب شراء" in whatsapp.reorder_drafts_message(5, 40)
    assert "صلاحية" in whatsapp.expiry_alert_message({"d7": 2, "d30": 5, "expired": 1}, 300)
    assert "#7" in whatsapp.transfer_request_message(7, "Main", "Elsanta", 3)


def test_scheduler_jobs_still_run_and_notify(monkeypatch):
    """The scheduler's compute+notify jobs must run cleanly even with no
    WhatsApp configured (notify is a no-op)."""
    from app.services import scheduler

    for job in ("expiry_alerts", "auto_purchase_order", "auto_reports"):
        out = scheduler.run_now(job)
        assert out["ran"] is True, job
