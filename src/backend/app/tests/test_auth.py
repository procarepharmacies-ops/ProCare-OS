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
