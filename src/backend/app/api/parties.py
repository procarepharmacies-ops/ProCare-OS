"""Customer & vendor endpoints (read-only + light customer edits)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import parties

router = APIRouter(tags=["parties"])


@router.get("/customers")
def customers(
    only_debtors: bool = Query(False),
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"customers": parties.list_customers(session, only_debtors, limit)}


@router.get("/customers/{customer_id}/statement")
def customer_statement(
    customer_id: int,
    limit: int = Query(200, ge=1, le=500),
    session: Session = Depends(get_session),
):
    statement = parties.customer_statement(session, customer_id, limit)
    if statement is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return statement


@router.get("/customers/{customer_id}/profile")
def customer_profile(
    customer_id: int,
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    """Customer 360: identity + address + loyalty, purchase history, and the
    medicines they take."""
    profile = parties.customer_profile(session, customer_id, limit)
    if profile is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return profile


class CustomerUpdateIn(BaseModel):
    address: str | None = Field(None, max_length=300)
    mobile: str | None = Field(None, max_length=20)


@router.post("/customers/{customer_id}")
def update_customer(customer_id: int, payload: CustomerUpdateIn, session: Session = Depends(get_session)):
    """Update editable customer fields (address, mobile)."""
    out = parties.update_customer(session, customer_id, payload.model_dump(exclude_unset=True))
    if out is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return out


@router.get("/vendors")
def vendors(limit: int = Query(200, ge=1, le=500), session: Session = Depends(get_session)):
    return {"vendors": parties.list_vendors(session, limit)}
