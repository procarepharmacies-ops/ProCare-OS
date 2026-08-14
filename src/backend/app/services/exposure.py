"""Pre-flight before ProCare is reachable from the public internet.

Opening a Cloudflare Tunnel turns a LAN-only pharmacy system into a public web
service in one command. Three defaults that are perfectly reasonable on a closed
LAN become critical holes the moment that happens, and none of them announce
themselves:

  1. ``AUTH_SECRET`` unset -> it falls back to the dev constant baked into this
     (public) repo. That secret HMAC-signs session tokens (``auth.py``), so
     anyone who reads the source can forge a CEO token. No password required.
     This is the worst of the three: changing passwords does not help while it
     holds.
  2. The seeded roster ships every account with the same known password. An
     account still using it is a published credential.
  3. ``AUTH_ENABLED`` false -> no login at all.

:func:`check` reports all three; the tunnel installer refuses to start while any
blocker stands. Read-only and fail-soft — it never mutates and never raises.

CLI (from ``src/backend``)::

    python -m app.services.exposure --check
    python -m app.services.exposure --set-password admin "new-strong-password"
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.db import models as m
from app.db.base import SessionLocal
from app.services import auth

# The fallback in auth._secret(). Public knowledge — it is in this repo.
DEV_SECRET = "procare-dev-secret-change-me"

# Every seeded employee gets this password (db/seed.py). Fine for a demo,
# a published credential once the system is reachable.
SEEDED_PASSWORD = "procare123"

# Short passwords fall to online guessing once a login form faces the internet.
MIN_PASSWORD_LENGTH = 12


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_exposure(
    *,
    auth_enabled: bool,
    secret_is_default: bool,
    weak_accounts: list[str],
) -> dict:
    """Pure verdict — no I/O, unit-testable without a database.

    Returns ``{"safe_to_expose", "blockers": [...], "warnings": [...]}``.
    A blocker means "do not open the tunnel"; the caller exits non-zero.
    """
    blockers: list[str] = []
    warnings: list[str] = []

    if secret_is_default:
        blockers.append(
            "AUTH_SECRET is the public dev default. Session tokens are HMAC-signed "
            "with it, so anyone reading this repo can forge a CEO token WITHOUT a "
            "password. Set AUTH_SECRET to a long random value in .env."
        )
    if not auth_enabled:
        blockers.append(
            "AUTH_ENABLED is off — the UI and API would be open to anyone with "
            "the URL. Set AUTH_ENABLED=true in .env."
        )
    if weak_accounts:
        listed = ", ".join(sorted(weak_accounts))
        blockers.append(
            f"{len(weak_accounts)} account(s) still use the seeded demo password: "
            f"{listed}. Change them "
            "(python -m app.services.exposure --set-password <user> <password>)."
        )

    return {
        "safe_to_expose": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }


def _weak_accounts(session) -> list[str]:
    """Usernames whose stored hash still verifies the seeded demo password.

    Checked by verifying rather than comparing hashes: the seed writes PBKDF2
    (random salt, so hashes differ per row) and older rows may carry the legacy
    unsalted sha256. ``verify_password`` handles both.
    """
    out: list[str] = []
    rows = session.execute(
        select(m.Employee.username, m.Employee.password_hash).where(
            m.Employee.is_active.is_(True)
        )
    ).all()
    for username, pw_hash in rows:
        if not pw_hash or pw_hash.startswith("!"):
            continue  # mirror sentinel — not a real login
        if auth.verify_password(SEEDED_PASSWORD, pw_hash):
            out.append(str(username))
    return out


def check() -> dict:
    """Live pre-exposure check. Read-only; reports errors, never raises."""
    try:
        secret_is_default = os.environ.get("AUTH_SECRET", DEV_SECRET) == DEV_SECRET
        auth_enabled = bool(getattr(settings, "auth_enabled", False))
        with SessionLocal() as s:
            weak = _weak_accounts(s)

        verdict = evaluate_exposure(
            auth_enabled=auth_enabled,
            secret_is_default=secret_is_default,
            weak_accounts=weak,
        )
        return {
            "ok": True,
            "auth_enabled": auth_enabled,
            "auth_secret_is_default": secret_is_default,
            "weak_accounts": weak,
            "checked_at": _now_iso(),
            **verdict,
        }
    except Exception as e:  # noqa: BLE001 — reported so the installer can stop
        return {
            "ok": False,
            "safe_to_expose": False,
            "error": f"{type(e).__name__}: {e}",
            "checked_at": _now_iso(),
        }


def set_password(username: str, new_password: str) -> dict:
    """Set ``username``'s login password locally (operator CLI).

    The HTTP reset flow needs a delivered code, which is circular when you are
    trying to secure the box *before* putting it online. This is the local,
    physically-present path. Refuses the seeded password and anything short.
    """
    uname = (username or "").strip()
    if not uname:
        return {"ok": False, "reason": "No username given."}
    if not new_password:
        return {"ok": False, "reason": "No password given."}
    if new_password == SEEDED_PASSWORD:
        return {"ok": False, "reason": "That is the seeded demo password. Choose another."}
    if len(new_password) < MIN_PASSWORD_LENGTH:
        return {
            "ok": False,
            "reason": f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        }

    try:
        with SessionLocal() as s:
            emp = s.execute(
                select(m.Employee).where(m.Employee.username == uname)
            ).scalar_one_or_none()
            if emp is None:
                return {"ok": False, "reason": f"No employee with username {uname!r}."}
            emp.password_hash = auth.hash_password(new_password)
            s.commit()
        return {"ok": True, "username": uname, "changed_at": _now_iso()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    import json

    arg = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if arg == "--check":
        out = check()
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        # 0 = safe to expose, 1 = blocked. deploy/ProCare-Cloudflare-Tunnel.bat
        # refuses to open the tunnel on anything non-zero.
        sys.exit(0 if out.get("safe_to_expose") else 1)
    elif arg == "--set-password":
        out = set_password(
            sys.argv[2] if len(sys.argv) > 2 else "",
            sys.argv[3] if len(sys.argv) > 3 else "",
        )
    else:
        out = {"ok": False, "reason": "usage: --check | --set-password <user> <password>"}

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    sys.exit(0 if out.get("ok") else 1)
