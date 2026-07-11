"""Login + role-gated endpoints.

``settings.auth_enabled`` is read once at import time from the AUTH_ENABLED
env var, so these tests exercise the auth service and dependency logic
directly rather than flipping process-wide settings mid-suite.
"""
from __future__ import annotations

from app.api.auth import auth_guard
from app.services import auth as auth_svc


def test_login_succeeds_with_seeded_demo_account(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "procare123"})
    assert r.status_code == 200
    body = r.json()
    assert body["employee"]["role"] == "ceo"
    assert body["token"].count(".") == 1


def test_login_rejects_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_rejects_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


def test_me_requires_a_valid_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401

    login = client.post("/api/auth/login", json={"username": "sara", "password": "procare123"})
    token = login.json()["token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "manager"


def test_token_roundtrip_and_tamper_detection(session):
    from app.db import models as m
    from sqlalchemy import select

    emp = session.scalar(select(m.Employee).where(m.Employee.username == "admin"))
    token = auth_svc.create_token(emp)
    payload = auth_svc.decode_token(token)
    assert payload["role"] == "ceo"

    tampered = token[:-2] + "xx"
    assert auth_svc.decode_token(tampered) is None


def test_forgot_password_full_flow(client, session, monkeypatch):
    """Request a code (captured from the WhatsApp message), burn a wrong
    attempt, then reset with the right code and log in with the new password."""
    from app.db import models as m
    from app.services import whatsapp
    from sqlalchemy import select

    emp = session.scalar(select(m.Employee).where(m.Employee.username == "admin"))
    emp.phone = "01000000000"
    session.commit()

    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(whatsapp, "is_configured", lambda: True)
    monkeypatch.setattr(whatsapp, "send_text", lambda mobile, text: sent.append((mobile, text)) or True)

    r = client.post("/api/auth/forgot-password", json={"username": "admin"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert len(sent) == 1
    import re

    code = re.search(r"\b(\d{6})\b", sent[0][1]).group(1)

    # Wrong code burns an attempt.
    r = client.post("/api/auth/reset-password", json={"username": "admin", "code": "000000" if code != "000000" else "111111", "new_password": "NewPass!2026"})
    assert r.status_code == 401

    # Right code resets; old password stops working, new one works.
    r = client.post("/api/auth/reset-password", json={"username": "admin", "code": code, "new_password": "NewPass!2026"})
    assert r.status_code == 200
    assert client.post("/api/auth/login", json={"username": "admin", "password": "procare123"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "NewPass!2026"}).status_code == 200

    # Code is single-use.
    r = client.post("/api/auth/reset-password", json={"username": "admin", "code": code, "new_password": "OtherPass9"})
    assert r.status_code == 401

    # Restore the demo password for the rest of the suite.
    emp = session.scalar(select(m.Employee).where(m.Employee.username == "admin"))
    emp.password_hash = auth_svc.hash_password("procare123")
    session.commit()


def test_forgot_password_never_reveals_account_existence(client, monkeypatch):
    from app.services import whatsapp

    monkeypatch.setattr(whatsapp, "is_configured", lambda: True)
    monkeypatch.setattr(whatsapp, "send_text", lambda mobile, text: True)
    r = client.post("/api/auth/forgot-password", json={"username": "no-such-user"})
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_forgot_password_when_whatsapp_unconfigured(client, monkeypatch):
    from app.services import whatsapp

    monkeypatch.setattr(whatsapp, "is_configured", lambda: False)
    r = client.post("/api/auth/forgot-password", json={"username": "admin"})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "whatsapp_unavailable"


def test_reset_code_expiry_and_attempt_limit(client, session, monkeypatch):
    from datetime import datetime, timedelta
    from app.db import models as m
    from app.services import whatsapp
    from sqlalchemy import select

    emp = session.scalar(select(m.Employee).where(m.Employee.username == "sara"))
    emp.phone = "01000000001"
    session.commit()
    monkeypatch.setattr(whatsapp, "is_configured", lambda: True)
    monkeypatch.setattr(whatsapp, "send_text", lambda mobile, text: True)

    client.post("/api/auth/forgot-password", json={"username": "sara"})

    # Five wrong attempts -> locked out even with the right shape of request.
    for _ in range(5):
        r = client.post("/api/auth/reset-password", json={"username": "sara", "code": "999999", "new_password": "Whatever99"})
        assert r.status_code == 401
    r = client.post("/api/auth/reset-password", json={"username": "sara", "code": "999999", "new_password": "Whatever99"})
    assert r.json()["detail"]["code"] == "too_many_attempts"

    # Expired code is rejected and cleared.
    client.post("/api/auth/forgot-password", json={"username": "sara"})
    emp = session.scalar(select(m.Employee).where(m.Employee.username == "sara"))
    emp.reset_code_expires = datetime.utcnow() - timedelta(minutes=1)
    session.commit()
    r = client.post("/api/auth/reset-password", json={"username": "sara", "code": "123456", "new_password": "Whatever99"})
    assert r.json()["detail"]["code"] == "expired_code"


def test_auth_guard_is_noop_when_disabled(monkeypatch):
    """The default (AUTH_ENABLED unset) must not block anything — this is what
    keeps every other existing test green without auth headers."""
    from app.config import settings

    monkeypatch.setattr(settings, "auth_enabled", False)
    dep = auth_guard(("ceo",))

    class FakeRequest:
        headers: dict = {}

    assert dep(FakeRequest()) is None


def test_auth_guard_enforces_role_when_enabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    dep = auth_guard(("ceo",))

    class FakeRequest:
        def __init__(self, headers):
            self.headers = headers

    # No token at all -> 401.
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        dep(FakeRequest({}))
    assert exc.value.status_code == 401

    # Wrong role -> 403.
    from app.db.base import SessionLocal
    from app.db import models as m
    from sqlalchemy import select

    with SessionLocal() as s:
        assistant = s.scalar(select(m.Employee).where(m.Employee.username == "ahmed"))
        token = auth_svc.create_token(assistant)
    with pytest.raises(HTTPException) as exc:
        dep(FakeRequest({"authorization": f"Bearer {token}"}))
    assert exc.value.status_code == 403
