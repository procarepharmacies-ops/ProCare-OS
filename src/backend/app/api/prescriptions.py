"""Prescription-reader endpoints: analyze a phone photo (Gemini vision when
configured), store the extraction, and the doctor-habits report."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import prescriptions as rx

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


class DrugLine(BaseModel):
    name: str
    dose: str | None = None
    frequency: str | None = None
    duration: str | None = None


class AnalyzeIn(BaseModel):
    # Base64 image WITHOUT the data: prefix; phone camera capture.
    image_b64: str
    mime_type: str = "image/jpeg"
    branch_id: int | None = None
    customer_id: int | None = None
    captured_by: int | None = None
    # When true (default) a successful extraction is stored immediately.
    save: bool = True


class ManualIn(BaseModel):
    branch_id: int | None = None
    customer_id: int | None = None
    doctor_name: str | None = None
    doctor_specialty: str | None = None
    clinic: str | None = None
    drugs: list[DrugLine] = []
    raw_text: str | None = None
    captured_by: int | None = None


@router.get("/status")
def status():
    return rx.status()


@router.post("/analyze")
def analyze(payload: AnalyzeIn, session: Session = Depends(get_session)):
    """Run the photo through the reader. Returns the extraction (and the saved
    record id when ``save`` is true). Falls back to ``needs_manual`` when no
    Gemini key is configured or the image could not be read."""
    data = rx.analyze_image(payload.image_b64, payload.mime_type)
    if data is None:
        return {"ok": False, "needs_manual": True, **rx.status()}
    saved_id = None
    if payload.save:
        record = rx.save(
            session,
            branch_id=payload.branch_id,
            customer_id=payload.customer_id,
            doctor_name=data.get("doctor_name"),
            doctor_specialty=data.get("doctor_specialty"),
            clinic=data.get("clinic"),
            drugs=data.get("drugs") or [],
            raw_text=data.get("raw_text"),
            source="gemini",
            captured_by=payload.captured_by,
        )
        saved_id = record.prescription_id
    return {"ok": True, "prescription_id": saved_id, "extraction": data}


@router.post("")
def create_manual(payload: ManualIn, session: Session = Depends(get_session)):
    record = rx.save(
        session,
        branch_id=payload.branch_id,
        customer_id=payload.customer_id,
        doctor_name=payload.doctor_name,
        doctor_specialty=payload.doctor_specialty,
        clinic=payload.clinic,
        drugs=[d.model_dump() for d in payload.drugs],
        raw_text=payload.raw_text,
        source="manual",
        captured_by=payload.captured_by,
    )
    return {"prescription_id": record.prescription_id}


@router.get("")
def list_all(
    branch_id: int | None = Query(None),
    doctor: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    return {"prescriptions": rx.list_prescriptions(session, branch_id or None, doctor, limit)}


@router.get("/doctor-habits")
def habits(
    branch_id: int | None = Query(None),
    days: int = Query(180, ge=7, le=730),
    session: Session = Depends(get_session),
):
    return {"days": days, "doctors": rx.doctor_habits(session, branch_id or None, days)}


class ReviewLine(BaseModel):
    name: str | None = None
    dose: str | None = None
    product_id: int | None = None
    qty: float = 1


class ReviewIn(BaseModel):
    drugs: list[ReviewLine] = []
    reviewed_by: int | None = None


@router.get("/{prescription_id}/resolve")
def resolve(prescription_id: int, branch_id: int | None = Query(None), session: Session = Depends(get_session)):
    """Per drug line, catalogue product candidates + on-hand stock for the
    review step (before turning the Rx into a sale)."""
    out = rx.resolve_products(session, prescription_id, branch_id or None)
    if out is None:
        raise HTTPException(status_code=404, detail="prescription not found")
    return out


@router.post("/{prescription_id}/review")
def review(prescription_id: int, payload: ReviewIn, session: Session = Depends(get_session)):
    out = rx.review(
        session, prescription_id, [d.model_dump() for d in payload.drugs], reviewed_by=payload.reviewed_by
    )
    if out is None:
        raise HTTPException(status_code=404, detail="prescription not found")
    return out


@router.get("/{prescription_id}/cart")
def cart(prescription_id: int, branch_id: int | None = Query(None), session: Session = Depends(get_session)):
    """Reviewed prescription as POS-ready cart lines (in-stock) + unresolved."""
    out = rx.cart_lines(session, prescription_id, branch_id or None)
    if out is None:
        raise HTTPException(status_code=404, detail="prescription not found")
    return out


@router.post("/{prescription_id}/dispensed")
def dispensed(prescription_id: int, session: Session = Depends(get_session)):
    out = rx.mark_dispensed(session, prescription_id)
    if out is None:
        raise HTTPException(status_code=404, detail="prescription not found")
    return out
