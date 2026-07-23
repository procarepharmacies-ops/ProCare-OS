"""Reorder proposals API (Phase 5): forecast-driven purchase recommendations.

GET /api/reorder/suggestions?branch_id= — list reorder suggestions by priority
GET /api/reorder/summary?branch_id= — summary grouped by vendor + priority
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db.base import get_session
from app.services import reorder as reorder_svc

router = APIRouter(prefix="/reorder", tags=["reorder"])


class ReorderSuggestionOut(BaseModel):
    product_id: int
    product_name_ar: str
    product_name_en: str
    current_stock: float
    daily_avg_demand: float
    days_to_stockout: float
    stockout_date: str | None
    suggested_qty: float
    unit_big: str | None
    unit_factor: float
    lead_time_days: int
    buy_price: float
    priority: str
    transfer_available_qty: float
    transfer_from_branch_id: int | None


@router.get("/suggestions", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def list_reorder_suggestions(
    branch_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """List reorder suggestions for a branch (ranked by priority).

    Combines forecasts + current stock to recommend:
    - Transfer from other branches (if available)
    - Purchase orders from best-price vendors
    - Prioritized by days-to-stockout (critical → urgent → normal → low)

    Each suggestion includes:
    - Current stock vs. forecasted demand
    - Transfer options + quantities available
    - Suggested vendors (ranked by price)
    - Priority level + urgency
    """
    suggestions = reorder_svc.generate_reorder_suggestions(session, branch_id)
    return {
        "suggestions": [
            ReorderSuggestionOut(**s) for s in suggestions
        ],
        "total": len(suggestions),
        "critical": sum(1 for s in suggestions if s["priority"] == "critical"),
        "urgent": sum(1 for s in suggestions if s["priority"] == "urgent"),
    }


@router.get("/summary", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def reorder_summary(
    branch_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """Summary view of reorder suggestions grouped by vendor + priority.

    Useful for:
    - Manager dashboard cards (total urgent/critical actions)
    - PO creation (grouped by vendor for efficient ordering)
    - Transfer coordination (total qty available at other branches)
    """
    suggestions = reorder_svc.generate_reorder_suggestions(session, branch_id)
    summary = reorder_svc.summarize_suggestions(suggestions)
    return {
        "branch_id": branch_id,
        **summary,
        "vendors": [
            {
                "vendor_name": name,
                "qty_to_order": data["qty"],
                "line_items_count": len(data["line_items"]),
            }
            for name, data in summary.get("by_vendor", {}).items()
        ],
    }
