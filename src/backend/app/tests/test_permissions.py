"""Phase 6 tests: permissions discovery (EMP_CONTROL parity)."""
from __future__ import annotations

from sqlalchemy import select

from app.db import models as m
from app.db.base import SessionLocal
from app.services import permissions as svc


def test_my_permissions_reports_flags_and_role_access():
    s = SessionLocal()
    try:
        # The seeded system admin (employee 1) is the CEO.
        emp = s.get(m.Employee, 1)
        out = svc.my_permissions(s, emp.employee_id)
        assert out["role"] == emp.role
        # Every EMP_CONTROL flag is reported with a bool + bilingual labels.
        codes = {f["code"] for f in out["flags"]}
        assert {"can_see_buy_price", "can_return", "can_void"} <= codes
        assert all(isinstance(f["enabled"], bool) and f["ar"] and f["en"] for f in out["flags"])
        assert out["granted_count"] == sum(1 for f in out["flags"] if f["enabled"])
        assert out["total_flags"] == len(svc.PERMISSION_FLAGS)
        # CEO sees the full role-access superset (accounting/employees included).
        if out["role"] == "ceo":
            en = {a["en"] for a in out["role_access"]}
            assert "Accounting & chart of accounts" in en
            assert "Employees & salaries" in en
    finally:
        s.close()


def test_flag_enabled_matches_the_employee_row():
    s = SessionLocal()
    try:
        emp = s.scalar(select(m.Employee).where(m.Employee.can_return == True))  # noqa: E712
        out = svc.my_permissions(s, emp.employee_id)
        can_return = next(f for f in out["flags"] if f["code"] == "can_return")
        assert can_return["enabled"] is True
        assert out["max_disc_per"] == float(emp.max_disc_per or 0)
    finally:
        s.close()


def test_missing_employee_returns_none():
    s = SessionLocal()
    try:
        assert svc.my_permissions(s, 999999) is None
    finally:
        s.close()


def test_role_access_is_nested_supersets():
    # assistant ⊂ manager ⊂ ceo
    a = {x["en"] for x in svc.ROLE_ACCESS["assistant"]}
    mgr = {x["en"] for x in svc.ROLE_ACCESS["manager"]}
    ceo = {x["en"] for x in svc.ROLE_ACCESS["ceo"]}
    assert a < mgr < ceo


# ------------------------------------------------------------------ API ----

def test_api_permissions_me_with_employee_id(client):
    r = client.get("/api/permissions/me", params={"employee_id": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["employee_id"] == 1
    assert "flags" in body and "role_access" in body


def test_api_permissions_me_missing_identity(client):
    # Auth disabled in tests + no employee_id → 400 (no identity to resolve).
    r = client.get("/api/permissions/me")
    assert r.status_code == 400


def test_api_permissions_me_unknown_employee(client):
    r = client.get("/api/permissions/me", params={"employee_id": 999999})
    assert r.status_code == 404
