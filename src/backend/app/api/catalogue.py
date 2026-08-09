"""Catalogue-quality endpoints: duplicate detection, Titan enrichment review,
and the scanned-barcode (GTIN -> product) map.

**Nothing here ever writes to eStock.** The duplicate/enrichment endpoints are
read-only review material; applying those changes is a separate, explicitly
approved export. The barcode endpoints do write, but only to ProCare's own
``product_barcodes`` table — the map staff build by scanning during الجرد.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db import models
from app.db.base import get_session
from app.services import catalogue, gtin_map
from app.services.pos import POSError

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


# ---- Barcode map (scanned GTIN -> product) --------------------------------
# Review + repair surface for what staff learn while scanning during الجرد.


@router.get("/barcodes", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def barcodes(
    source: str | None = Query(None, pattern="^(scan|backfill|import)$"),
    limit: int = Query(200, ge=1, le=1000),
    session: Session = Depends(get_session),
):
    """Recently learned barcode->product links, newest first (review feed)."""
    return {"barcodes": gtin_map.recent(session, source=source, limit=limit)}


@router.delete("/barcodes/{barcode_id}", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def unlink_barcode(barcode_id: int, session: Session = Depends(get_session)):
    """Remove a mis-linked barcode. Idempotent."""
    return gtin_map.unlink(session, barcode_id)


class RepointIn(BaseModel):
    product_id: int
    employee_id: int | None = None


@router.post("/barcodes/{barcode_id}/repoint", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def repoint_barcode(barcode_id: int, payload: RepointIn, session: Session = Depends(get_session)):
    """Force a barcode onto a different product (resolves a `gtin_taken`)."""
    row = session.get(models.ProductBarcode, barcode_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "barcode not found"})
    try:
        return gtin_map.learn(
            session, row.gtin, payload.product_id,
            employee_id=payload.employee_id, source="scan", force=True,
        )
    except POSError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


@router.get("/gtin-backfill/preview", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def gtin_backfill_preview(
    limit: int | None = Query(None, ge=1, le=100000),
    session: Session = Depends(get_session),
):
    """Dry run: how many products already carry a valid GTIN in ``code``.

    This is the verification step for "does eStock's product_code actually hold
    barcodes?" — ``valid_gtin == 0`` means the catalogue uses internal codes and
    the map has to be built by learn-on-scan instead.
    """
    return gtin_map.backfill_from_code(session, dry_run=True, limit=limit)


@router.post("/gtin-backfill", dependencies=[Depends(auth_guard(("ceo",)))])
def gtin_backfill(
    limit: int | None = Query(None, ge=1, le=100000),
    session: Session = Depends(get_session),
):
    """Write the mappings the preview found. CEO only — it seeds the catalogue."""
    return gtin_map.backfill_from_code(session, dry_run=False, limit=limit)
