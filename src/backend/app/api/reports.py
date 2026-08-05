"""Stock reports + export endpoints.

Every report answers JSON by default; ``?format=csv`` streams the same rows as
UTF-8-BOM CSV (opens directly in Excel — the "data only" export). The branded
"ProCare template" export is the frontend's print stylesheet over this JSON.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import reports
from app.services.pos import POSError

router = APIRouter(prefix="/reports", tags=["reports"])


def _answer(rows: list[dict], key: str, fmt: str, filename: str):
    if fmt == "csv":
        return Response(
            content=reports.to_csv(rows),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )
    return {key: rows}


@router.get("/stock")
def stock(
    branch_id: int | None = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    session: Session = Depends(get_session),
):
    return _answer(reports.stock_on_hand(session, branch_id or None), "products", format, "stock-on-hand")


@router.get("/stock/batches")
def batches(
    branch_id: int | None = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    session: Session = Depends(get_session),
):
    return _answer(reports.stock_by_batch(session, branch_id or None), "batches", format, "stock-by-batch")


@router.get("/stock/movements")
def movements(
    branch_id: int | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    format: str = Query("json", pattern="^(json|csv)$"),
    session: Session = Depends(get_session),
):
    return _answer(
        reports.stock_movements(session, branch_id or None, days), "movements", format, "stock-movements"
    )


@router.get("/stock/valuation")
def valuation(
    format: str = Query("json", pattern="^(json|csv)$"),
    session: Session = Depends(get_session),
):
    return _answer(reports.stock_valuation(session), "branches", format, "stock-valuation")


@router.get("/item-movement")
def item_movement(
    product_id: int = Query(..., ge=1),
    start: date | None = Query(None),
    end: date | None = Query(None),
    days: int = Query(30, ge=1, le=730),
    branch_id: int | None = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    session: Session = Depends(get_session),
):
    """Per-day movement of one item (eStock حركة مبيعات صنف في فترة). Pass an
    explicit ``start``/``end`` window, or just ``days`` for the trailing N days
    ending today. CSV export gives the daily rows for Excel."""
    end = end or reports.today()
    start = start or (end - timedelta(days=days))
    try:
        result = reports.item_movement(session, product_id, start, end, branch_id or None)
    except POSError as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": str(e)})
    if format == "csv":
        return Response(
            content=reports.to_csv(result["rows"]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="item-movement.csv"'},
        )
    return result
