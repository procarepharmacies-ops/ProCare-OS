"""Catalogue-quality endpoints: duplicate detection + Titan enrichment review.

All READ-ONLY. Nothing here writes to eStock — these endpoints produce the
review material; applying changes is a separate, explicitly-approved export.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db.base import get_session
from app.services import catalogue

router = APIRouter(prefix="/catalogue", tags=["catalogue"])


@router.get("/duplicates", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def duplicates(
    branch_id: int | None = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    session: Session = Depends(get_session),
):
    """Suspected duplicate products with survivor-choice evidence (stock,
    lifetime sales, last sale). Risk = how many copies hold live stock."""
    return catalogue.duplicate_groups(session, branch_id or None, limit=limit)


@router.get("/enrichment", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def enrichment(
    only_missing: bool = Query(True),
    limit: int = Query(500, ge=1, le=5000),
    min_score: int = Query(85, ge=0, le=100),
    session: Session = Depends(get_session),
):
    """Per-product Titan-vs-eStock field diffs staged for approval.
    ``only_missing=false`` also surfaces disagreements, not just blanks."""
    return catalogue.enrichment_proposals(
        session, only_missing=only_missing, limit=limit, min_score=min_score
    )


class DecisionIn(BaseModel):
    product_id: int
    field: str
    new_value: str | None = None
    old_value: str | None = None
    source: str | None = None
    status: str  # approved | rejected


class DecisionsIn(BaseModel):
    items: list[DecisionIn]


@router.post("/decisions", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def decisions(payload: DecisionsIn, request: Request, session: Session = Depends(get_session)):
    """Record approve/reject rulings and apply the durable ones to ProCare.
    eStock is untouched — approvals are staged for the reviewed write-back."""
    emp = getattr(request.state, "employee_id", None)
    return catalogue.record_decisions(
        session, [i.model_dump() for i in payload.items], employee_id=emp
    )


@router.get("/decisions/summary", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def decisions_summary(session: Session = Depends(get_session)):
    return catalogue.decision_summary(session)
