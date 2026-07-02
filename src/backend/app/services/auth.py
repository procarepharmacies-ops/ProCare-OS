"""Login + role-based session tokens.

Zero extra dependencies (matches the rest of this codebase): tokens are a
compact HMAC-signed JSON structure, not a full JWT library. Good enough for a
single-pharmacy LAN app; swap for a real JWT lib if ProCare ever needs
federated/multi-tenant auth.

Roles: "ceo" (full access), "manager" (branch-scoped, no salaries/financials),
"assistant" (POS + inventory only). Enforcement is opt-in via
``settings.auth_enabled`` so existing deployments/tests keep working until a
pharmacy turns it on.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m

ROLES = ("ceo", "manager", "assistant")
TOKEN_TTL_SECONDS = 60 * 60 * 12  # 12-hour shift-length session

# Dev fallback secret — MUST be overridden via AUTH_SECRET in production
# (docker-compose reads it from .env, never committed).
_DEV_SECRET = "procare-dev-secret-change-me"


def _secret() -> bytes:
    return os.environ.get("AUTH_SECRET", _DEV_SECRET).encode()


def hash_password(password: str) -> str:
    return "sha256$" + hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash or "")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def create_token(employee: m.Employee) -> str:
    payload = {
        "employee_id": employee.employee_id,
        "username": employee.username,
        "role": employee.role,
        "branch_id": employee.branch_id,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = _b64(json.dumps(payload).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def decode_token(token: str) -> dict | None:
    """Verify signature + expiry. Returns the payload dict, or None if invalid."""
    try:
        body, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(_unb64(body))
    except Exception:  # noqa: BLE001
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload


def authenticate(session: Session, username: str, password: str) -> m.Employee | None:
    emp = session.scalar(
        select(m.Employee).where(m.Employee.username == username, m.Employee.is_active == True)  # noqa: E712
    )
    if emp is None or not verify_password(password, emp.password_hash):
        return None
    return emp
