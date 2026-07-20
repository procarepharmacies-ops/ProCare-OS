"""Stocktaking (الجرد) endpoints: count sessions, count sheet, posting."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.services import stocktaking
from app.services.pos import POSError

router = APIRouter(prefix="/stocktaking", tags=["stocktaking"])


def _raise(e: POSError):
    raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


# In-memory ring buffer: last 20 stocktaking events for dashboard alert polling.
_RECENT_EVENTS: list[dict] = []


def _log_stocktake_alert(branch_id: int, message: str) -> None:
    """Push a lightweight event into the ring buffer for dashboard polling.
    No DB write needed — the frontend polls /stocktaking/recent-alerts.
    """
    global _RECENT_EVENTS
    _RECENT_EVENTS.append({
        "branch_id": branch_id,
        "message": message,
        "ts": datetime.utcnow().isoformat(),
    })
    # Keep only the last 20 events to avoid unbounded growth
    _RECENT_EVENTS = _RECENT_EVENTS[-20:]


def _raise(e: POSError):
    raise HTTPException(status_code=422, detail={"code": e.code, "message": e.message})


@router.get("")
def counts(
    branch_id: int | None = Query(None),
    session: Session = Depends(get_session),
):
    return {"counts": stocktaking.list_counts(session, branch_id or None)}


class CreateIn(BaseModel):
    branch_id: int
    count_type: str = Field("full", pattern="^(full|periodic|partial)$")
    scope: str | None = Field(None, pattern="^(stagnant)$")  # partial-count presets
    note: str | None = Field(None, max_length=300)
    created_by: int | None = None
    product_ids: list[int] | None = None  # optional scope for periodic/partial


@router.post("")
def create(payload: CreateIn, session: Session = Depends(get_session)):
    """Open a count session. ``periodic`` with no explicit product list counts
    the branch's 30-day top movers (الجرد الدوري); ``scope='stagnant'`` counts
    the stagnant items (جرد الأصناف الراكدة)."""
    try:
        product_ids = payload.product_ids
        count_type = payload.count_type
        note = payload.note
        if payload.scope == "stagnant" and not product_ids:
            from app.services import inventory

            report = inventory.stagnant_products(session, payload.branch_id, days=90)
            product_ids = [i["product_id"] for i in report["items"]]
            count_type = "partial"
            note = note or "جرد الأصناف الراكدة (٩٠ يوم بدون حركة)"
        elif count_type == "periodic" and not product_ids:
            product_ids = stocktaking.top_movers(session, payload.branch_id)
        result = stocktaking.create_count(
            session,
            payload.branch_id,
            count_type,
            note=note,
            created_by=payload.created_by,
            product_ids=product_ids,
        )
        _log_stocktake_alert(
            payload.branch_id,
            f"تم فتح جلسة جرد {count_type} | Stocktaking session opened"
        )
        return result
    except POSError as e:
        _raise(e)


@router.get("/{count_id}")
def detail(count_id: int, session: Session = Depends(get_session)):
    try:
        return stocktaking.get_count(session, count_id)
    except POSError as e:
        _raise(e)


class LineIn(BaseModel):
    line_id: int
    counted_qty: float | None = Field(None, ge=0)


class RecordIn(BaseModel):
    entries: list[LineIn]


@router.post("/{count_id}/lines")
def record(count_id: int, payload: RecordIn, session: Session = Depends(get_session)):
    """Save physically-counted quantities (save-as-you-go while counting)."""
    try:
        return stocktaking.record_lines(
            session, count_id, [e.model_dump() for e in payload.entries]
        )
    except POSError as e:
        _raise(e)


class PostIn(BaseModel):
    employee_id: int | None = None


@router.post("/{count_id}/post")
def post(count_id: int, payload: PostIn, session: Session = Depends(get_session)):
    """Apply all counted differences as stock adjustments and close the session."""
    try:
        count = stocktaking.get_count(session, count_id)
        result = stocktaking.post_count(session, count_id, employee_id=payload.employee_id)
        branch_id = count.get("branch_id", 0) if isinstance(count, dict) else 0
        _log_stocktake_alert(branch_id, f"تم ترحيل الجرد #{count_id} | Stocktaking #{count_id} posted")
        return result
    except POSError as e:
        _raise(e)


@router.post("/{count_id}/cancel")
def cancel(count_id: int, session: Session = Depends(get_session)):
    try:
        count = stocktaking.get_count(session, count_id)
        result = stocktaking.cancel_count(session, count_id)
        branch_id = count.get("branch_id", 0) if isinstance(count, dict) else 0
        _log_stocktake_alert(branch_id, f"تم إلغاء الجرد #{count_id} | Stocktaking #{count_id} cancelled")
        return result
    except POSError as e:
        _raise(e)


@router.get("/recent-alerts")
def recent_alerts(minutes: int = 5):
    """Return stocktaking events from the last N minutes (default 5).

    Used by the dashboard to show an instant red alert banner whenever
    any جرد session is opened, posted, or cancelled.
    """
    cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
    return {"alerts": [e for e in _RECENT_EVENTS if e["ts"] >= cutoff]}
