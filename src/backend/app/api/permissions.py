"""Permissions discovery API (Phase 6): show the current user their own
permission matrix — flags ON/OFF, limits, and what their role unlocks.

GET /api/permissions/me — the logged-in user's permissions.

Resolves the employee from the Bearer token when present; falls back to an
explicit ``employee_id`` query param (so the screen still works when auth is
not enabled). Any logged-in employee may view their own permissions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import auth as auth_svc
from app.services import permissions as svc

router = APIRouter(prefix="/permissions", tags=["permissions"])


def _resolve_employee_id(request: Request, employee_id: int | None) -> int | None:
    """Prefer the Bearer token's identity; fall back to the query param."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        payload = auth_svc.decode_token(auth.split(" ", 1)[1].strip())
        if payload and payload.get("employee_id"):
            return int(payload["employee_id"])
    return employee_id


@router.get("/me")
def my_permissions(
    request: Request,
    employee_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    resolved = _resolve_employee_id(request, employee_id)
    if resolved is None:
        raise HTTPException(status_code=400, detail={"code": "no_identity", "message": "No employee identity"})
    result = svc.my_permissions(session, resolved)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Employee not found"})
    return result
