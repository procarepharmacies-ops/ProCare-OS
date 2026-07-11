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
import logging
import os
import secrets
import time
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m

log = logging.getLogger("procare.auth")

ROLES = ("ceo", "manager", "assistant")
TOKEN_TTL_SECONDS = 60 * 60 * 12  # 12-hour shift-length session

# Self-service password reset (WhatsApp code).
RESET_CODE_TTL_SECONDS = 10 * 60
RESET_MAX_ATTEMPTS = 5

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


# --- self-service password reset (code over WhatsApp) ------------------------
def request_reset(session: Session, username: str) -> dict:
    """Generate a 6-digit reset code and WhatsApp it to the account's phone.

    The response NEVER reveals whether the username exists or has a phone —
    always the same generic acknowledgement — so the endpoint can't be used to
    enumerate accounts. The only distinct answer is the global "WhatsApp is not
    configured on this server" state, which is not account-specific.
    """
    from app.services import whatsapp

    generic = {"ok": True}
    if not whatsapp.is_configured():
        return {"ok": False, "code": "whatsapp_unavailable"}
    emp = session.scalar(
        select(m.Employee).where(m.Employee.username == username, m.Employee.is_active == True)  # noqa: E712
    )
    if emp is None:
        return generic
    if not emp.phone:
        log.warning("password reset requested for %s but no phone on file", username)
        return generic
    code = f"{secrets.randbelow(1_000_000):06d}"
    emp.reset_code_hash = hash_password(code)
    emp.reset_code_expires = datetime.utcnow() + timedelta(seconds=RESET_CODE_TTL_SECONDS)
    emp.reset_attempts = 0
    session.commit()
    sent = whatsapp.send_text(
        emp.phone,
        f"صيدليات بروكير 💚\nكود استعادة كلمة المرور: {code}\n"
        "صالح لمدة 10 دقائق — لا تشاركه مع أي شخص.\n"
        f"ProCare password reset code: {code} (valid 10 minutes).",
    )
    log.info("password reset code for %s: whatsapp sent=%s", username, sent)
    return generic


def reset_password(session: Session, username: str, code: str, new_password: str) -> tuple[bool, str]:
    """Verify the WhatsApp code and set the new password.

    Returns (ok, reason). Wrong codes burn an attempt; after RESET_MAX_ATTEMPTS
    (or expiry) the pending code is invalidated and a new request is needed.
    """
    emp = session.scalar(
        select(m.Employee).where(m.Employee.username == username, m.Employee.is_active == True)  # noqa: E712
    )
    if emp is None or not emp.reset_code_hash or emp.reset_code_expires is None:
        return False, "invalid_code"
    if emp.reset_code_expires < datetime.utcnow():
        _clear_reset(session, emp)
        return False, "expired_code"
    if emp.reset_attempts >= RESET_MAX_ATTEMPTS:
        _clear_reset(session, emp)
        return False, "too_many_attempts"
    if not hmac.compare_digest(hash_password(code.strip()), emp.reset_code_hash):
        emp.reset_attempts += 1
        session.commit()
        return False, "invalid_code"
    if len(new_password) < 8:
        return False, "weak_password"
    emp.password_hash = hash_password(new_password)
    _clear_reset(session, emp)
    log.info("password reset completed for %s", username)
    return True, "ok"


def _clear_reset(session: Session, emp: m.Employee) -> None:
    emp.reset_code_hash = None
    emp.reset_code_expires = None
    emp.reset_attempts = 0
    session.commit()
