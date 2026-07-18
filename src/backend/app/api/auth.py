"""Login endpoint + reusable auth dependencies for protecting routers.

Enforcement is opt-in (``settings.auth_enabled``): when off (the default —
existing deployments and the test suite), every dependency here is a no-op so
nothing breaks. A pharmacy turns it on once real accounts are set up.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models as m
from app.db.base import get_session
from app.services import auth as auth_svc

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


def _require_token(request: Request) -> dict:
    """Decode the Bearer token unconditionally (used by /auth/me, which only
    makes sense when a token is actually presented)."""
    authz = request.headers.get("authorization", "")
    if not authz.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"code": "no_token", "message": "Missing bearer token"})
    payload = auth_svc.decode_token(authz[7:].strip())
    if payload is None:
        raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "Invalid or expired token"})
    return payload


def _employee_out(emp: m.Employee) -> dict:
    return {
        "employee_id": emp.employee_id,
        "name_ar": emp.name_ar,
        "name_en": emp.name_en,
        "username": emp.username,
        "role": emp.role,
        "branch_id": emp.branch_id,
    }


@router.options("/login")
def login_options():
    """CORS preflight handler."""
    return {}


def _log_event(session: Session, username: str, event: str, employee_id: int | None, request: Request | None) -> None:
    """Append to the security audit trail. Never lets logging break auth."""
    try:
        ip = request.client.host if request and request.client else None
        session.add(m.AuthEvent(username=username[:80], event=event, employee_id=employee_id, ip=ip))
        session.commit()
    except Exception:  # noqa: BLE001 — audit failure must not block login
        session.rollback()


@router.post("/login")
def login(payload: LoginIn, request: Request, session: Session = Depends(get_session)):
    username = payload.username.strip()
    emp = auth_svc.authenticate(session, username, payload.password)
    if emp is None:
        _log_event(session, username, "login_fail", None, request)
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Invalid username or password"})
    _log_event(session, username, "login_ok", emp.employee_id, request)
    return {"token": auth_svc.create_token(emp), "employee": _employee_out(emp)}


class ForgotPasswordIn(BaseModel):
    username: str


@router.options("/forgot-password")
def forgot_password_options():
    """CORS preflight handler."""
    return {}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordIn, session: Session = Depends(get_session)):
    """Self-service reset, step 1: WhatsApp a 6-digit code to the account's
    registered phone. Same generic answer whether or not the account exists."""
    result = auth_svc.request_reset(session, payload.username.strip())
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail={
            "code": result.get("code", "unavailable"),
            "message": "خدمة واتساب غير مفعلة على الخادم — تواصل مع المدير / WhatsApp is not configured — contact your manager",
        })
    return result


class ResetPasswordIn(BaseModel):
    username: str
    code: str
    new_password: str


@router.options("/reset-password")
def reset_password_options():
    """CORS preflight handler."""
    return {}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordIn, request: Request, session: Session = Depends(get_session)):
    """Self-service reset, step 2: verify the code, set the new password."""
    ok, reason = auth_svc.reset_password(
        session, payload.username.strip(), payload.code, payload.new_password
    )
    if ok:
        _log_event(session, payload.username.strip(), "reset_ok", None, request)
    if not ok:
        messages = {
            "invalid_code": "الكود غير صحيح / wrong code",
            "expired_code": "انتهت صلاحية الكود — اطلب كودًا جديدًا / code expired — request a new one",
            "too_many_attempts": "محاولات كثيرة — اطلب كودًا جديدًا / too many attempts — request a new code",
            "weak_password": "كلمة المرور يجب ألا تقل عن 8 أحرف / password must be at least 8 characters",
        }
        status = 422 if reason == "weak_password" else 401
        raise HTTPException(status_code=status, detail={"code": reason, "message": messages.get(reason, reason)})
    return {"ok": True}


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    token: dict = Depends(_require_token),
    session: Session = Depends(get_session),
):
    """Everyone changes their own initial password here (token required, old
    password re-verified). Minimal policy: 8+ characters."""
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=422, detail={"code": "weak_password", "message": "Password must be at least 8 characters"})
    emp = session.scalar(select(m.Employee).where(m.Employee.employee_id == token["employee_id"]))
    if emp is None or not auth_svc.verify_password(payload.old_password, emp.password_hash):
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials", "message": "Current password is wrong"})
    emp.password_hash = auth_svc.hash_password(payload.new_password)
    session.commit()
    _log_event(session, emp.username or "", "password_change", emp.employee_id, request)
    return {"ok": True}


@router.get("/me")
def me(payload: dict = Depends(_require_token), session: Session = Depends(get_session)):
    emp = session.scalar(select(m.Employee).where(m.Employee.employee_id == payload["employee_id"]))
    if emp is None:
        raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "Employee no longer exists"})
    return _employee_out(emp)


def auth_guard(roles: tuple[str, ...] | None = None):
    """Dependency factory for protecting a router/endpoint.

    - If ``settings.auth_enabled`` is False: no-op (returns None), so callers
      and existing tests are unaffected until a pharmacy opts in.
    - If True: requires a valid Bearer token; if ``roles`` is given, the
      token's role must be one of them (else 403).
    """

    def _dep(request: Request):
        if not settings.auth_enabled:
            return None
        payload = _require_token(request)
        if roles and payload.get("role") not in roles:
            raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "Insufficient role"})
        return payload

    return _dep
