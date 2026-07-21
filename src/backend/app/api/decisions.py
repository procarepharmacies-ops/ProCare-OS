"""Decision cards API (Phase 5): manager briefing endpoints.

GET /api/decisions — list open decision cards (daily briefing)
POST /api/decisions/{card_id}/dismiss — dismiss a card without action
POST /api/decisions/{card_id}/action — mark card as actioned (manager confirms action taken)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db.base import get_session
from app.services import decisions as decisions_svc

router = APIRouter(prefix="/decisions", tags=["decisions"])


class DecisionCardOut(BaseModel):
    card_id: int
    branch_id: int
    created_at: str | None
    card_type: str
    severity: str
    title_ar: str
    title_en: str
    body_ar: str
    body_en: str
    action_type: str | None
    ref_product_id: int | None
    status: str


class DismissRequest(BaseModel):
    pass


class ActionRequest(BaseModel):
    employee_id: int | None = None


@router.get("", dependencies=[Depends(auth_guard())])
def list_decision_cards(
    branch_id: int | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """List open decision cards for manager briefing (القرارات اليومية).

    Filtered by severity (critical first), then creation time.
    Includes all card types: stockout_risk, below_min, expiry_warning, overstocked.
    """
    cards = decisions_svc.get_open_decision_cards(session, branch_id)
    return {
        "cards": [DecisionCardOut(**c) for c in cards],
        "total": len(cards),
        "critical": sum(1 for c in cards if c["severity"] == "critical"),
        "warning": sum(1 for c in cards if c["severity"] == "warning"),
    }


@router.post("/{card_id}/dismiss", dependencies=[Depends(auth_guard())])
def dismiss_decision_card(
    card_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """Dismiss a decision card (manager reviewed, chose not to act).

    Card status changes to 'dismissed' but is not deleted (audit trail).
    """
    success = decisions_svc.dismiss_card(session, card_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")
    return {"status": "dismissed", "card_id": card_id}


@router.post("/{card_id}/action", dependencies=[Depends(auth_guard())])
def action_decision_card(
    card_id: int,
    request: ActionRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Mark a decision card as actioned (manager confirms action taken).

    Card status changes to 'actioned' with timestamp and optional employee_id
    (who actually executed the action, e.g., cashier who created the transfer).
    """
    success = decisions_svc.action_card(session, card_id, request.employee_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")
    return {"status": "actioned", "card_id": card_id}
