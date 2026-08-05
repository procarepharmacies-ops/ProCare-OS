"""Pre-exposure security gate: the verdict rule (pure) + live check/set_password.

The rule decides whether ProCare may be put on the public internet, so each
blocker is asserted individually — a regression that silently drops one would
otherwise still look "safe" in aggregate.
"""
from __future__ import annotations

from app.services import auth, exposure


# --- evaluate_exposure(): pure verdict, no I/O ------------------------------
def test_clean_config_is_safe():
    out = exposure.evaluate_exposure(
        auth_enabled=True, secret_is_default=False, weak_accounts=[]
    )
    assert out["safe_to_expose"] is True
    assert out["blockers"] == []


def test_default_auth_secret_blocks():
    """The worst case: forged tokens need no password at all."""
    out = exposure.evaluate_exposure(
        auth_enabled=True, secret_is_default=True, weak_accounts=[]
    )
    assert out["safe_to_expose"] is False
    assert any("AUTH_SECRET" in b for b in out["blockers"])


def test_auth_disabled_blocks():
    out = exposure.evaluate_exposure(
        auth_enabled=False, secret_is_default=False, weak_accounts=[]
    )
    assert out["safe_to_expose"] is False
    assert any("AUTH_ENABLED" in b for b in out["blockers"])


def test_seeded_password_blocks_and_names_the_accounts():
    out = exposure.evaluate_exposure(
        auth_enabled=True, secret_is_default=False, weak_accounts=["admin", "cashier1"]
    )
    assert out["safe_to_expose"] is False
    blocker = next(b for b in out["blockers"] if "seeded demo password" in b)
    assert "admin" in blocker and "cashier1" in blocker


def test_every_blocker_is_reported_not_just_the_first():
    """An operator fixing one at a time must see the whole list."""
    out = exposure.evaluate_exposure(
        auth_enabled=False, secret_is_default=True, weak_accounts=["admin"]
    )
    assert out["safe_to_expose"] is False
    assert len(out["blockers"]) == 3


# --- set_password(): guards before touching the database --------------------
def test_set_password_rejects_the_seeded_password():
    out = exposure.set_password("admin", exposure.SEEDED_PASSWORD)
    assert out["ok"] is False
    assert "seeded" in out["reason"].lower()


def test_set_password_rejects_short_passwords():
    out = exposure.set_password("admin", "short")
    assert out["ok"] is False
    assert str(exposure.MIN_PASSWORD_LENGTH) in out["reason"]


def test_set_password_rejects_empty_username():
    assert exposure.set_password("", "a-long-enough-password")["ok"] is False


def test_set_password_rejects_unknown_user():
    out = exposure.set_password("no-such-user-here", "a-long-enough-password")
    assert out["ok"] is False
    assert "no employee" in out["reason"].lower()


def test_set_password_changes_the_hash_and_new_password_verifies():
    """End-to-end on the seeded test DB: the new password must actually work."""
    new = "a-genuinely-long-password-1"
    out = exposure.set_password("admin", new)
    assert out["ok"] is True, out

    from sqlalchemy import select

    from app.db import models as m
    from app.db.base import SessionLocal

    with SessionLocal() as s:
        pw_hash = s.execute(
            select(m.Employee.password_hash).where(m.Employee.username == "admin")
        ).scalar_one()

    assert auth.verify_password(new, pw_hash) is True
    # The seeded password must no longer open the account.
    assert auth.verify_password(exposure.SEEDED_PASSWORD, pw_hash) is False


# --- check(): live, read-only ----------------------------------------------
def test_check_runs_and_returns_a_verdict():
    out = exposure.check()
    assert out["ok"] is True
    assert isinstance(out["safe_to_expose"], bool)
    assert isinstance(out["blockers"], list)
    assert isinstance(out["weak_accounts"], list)


def test_check_flags_the_dev_secret_when_unset(monkeypatch):
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    out = exposure.check()
    assert out["auth_secret_is_default"] is True
    assert out["safe_to_expose"] is False


def test_check_accepts_a_real_secret(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "a-long-random-production-secret-value")
    out = exposure.check()
    assert out["auth_secret_is_default"] is False


def test_mirror_sentinel_accounts_are_not_flagged_as_weak():
    """eStock-mirrored employees carry '!estock-mirror' — not real logins."""
    from sqlalchemy import select

    from app.db import models as m
    from app.db.base import SessionLocal

    with SessionLocal() as s:
        s.add(
            m.Employee(
                username="mirrored-only-user",
                password_hash="!estock-mirror",
                role="assistant",
                name_ar="مرآة",
                is_active=True,
            )
        )
        s.commit()
        weak = exposure._weak_accounts(s)

    assert "mirrored-only-user" not in weak
