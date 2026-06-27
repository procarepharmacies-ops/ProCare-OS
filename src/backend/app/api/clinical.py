"""Clinical drug-advisory endpoints (read-only, advisory-only).

Backs the POS advisory banner and the drug-info screen (docs/03 §6). Every
response is ADVISORY — it never blocks a sale. In-stock checks run against
ProCare's own database.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import clinical

router = APIRouter(prefix="/clinical", tags=["clinical"])


class BasketIn(BaseModel):
    product_ids: list[int] = Field(default_factory=list)
    branch_id: int | None = None
    min_severity: str = "moderate"
    lang: str = "ar"


@router.get("/status")
def status():
    """Advisory engine mode (offline curated rules vs live Titan) + coverage."""
    return clinical.status()


@router.post("/interactions")
def interactions(payload: BasketIn, session: Session = Depends(get_session)):
    """Advisory interactions among the products in a basket (POS banner)."""
    rows = clinical.interactions_for_basket(
        session, payload.product_ids, min_severity=payload.min_severity, lang=payload.lang
    )
    return {
        "advisory": True,
        "count": len(rows),
        "max_severity": rows[0]["severity"] if rows else None,
        "interactions": rows,
    }


@router.get("/products/{product_id}/substitutions")
def substitutions(
    product_id: int,
    branch_id: int | None = Query(None),
    lang: str = Query("ar"),
    session: Session = Depends(get_session),
):
    """In-stock generic/therapeutic alternatives for a drug at a branch."""
    return {
        "advisory": True,
        "substitutions": clinical.substitutions(session, product_id, branch_id or None, lang),
    }


@router.get("/products/{product_id}/dose")
def dose(
    product_id: int,
    age: float = Query(..., ge=0, le=120, description="Patient age in years"),
    lang: str = Query("ar"),
    session: Session = Depends(get_session),
):
    """Advisory dose for a patient's age. 200 with null when no rule applies."""
    return {"advisory": True, "dose": clinical.dose(session, product_id, age, lang)}


@router.get("/products/{product_id}")
def drug_info(
    product_id: int,
    branch_id: int | None = Query(None),
    lang: str = Query("ar"),
    session: Session = Depends(get_session),
):
    """Full drug card: ingredients, classes, in-stock alternatives, dosing flag."""
    info = clinical.drug_info(session, product_id, branch_id or None, lang)
    if info is None:
        return {"advisory": True, "drug": None}
    return {"advisory": True, "drug": info}
