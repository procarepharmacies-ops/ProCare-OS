"""Employee incentive leaderboard and OTC incentive list management.

Tracks points earned per employee for selling incentivized OTC items,
and provides leaderboard views for motivation + monthly settlement.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.api.auth import auth_guard
from app.db import models as m
from app.db.base import get_session
from app.services import incentives as incentives_svc
from app.services.common import money

router = APIRouter(prefix="/incentives", tags=["incentives"])


class IncentivePointsIn(BaseModel):
    incentive_points: float


class ApplyItem(BaseModel):
    product_id: int
    points: float


class ApplyIn(BaseModel):
    items: list[ApplyItem]


@router.get("/leaderboard", dependencies=[Depends(auth_guard())])
def leaderboard(branch_id: int | None = None, month: str | None = None, session: Session = Depends(get_session)):
    """Monthly employee incentive leaderboard (top earners of the month).

    Args:
        branch_id: filter to one branch (None = all)
        month: "YYYY-MM" format (None = current month)

    Returns:
        List of employees ranked by points earned in the month, with their totals.
    """
    if month:
        try:
            month_date = datetime.strptime(month, "%Y-%m").date()
        except ValueError:
            month_date = date.today().replace(day=1)
    else:
        month_date = date.today().replace(day=1)

    month_start = month_date
    month_end = (month_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    stmt = (
        select(
            m.Employee.employee_id,
            m.Employee.name_ar,
            m.Employee.name_en,
            func.sum(m.IncentiveLedger.points).label("total_points"),
        )
        .join(m.IncentiveLedger, m.IncentiveLedger.employee_id == m.Employee.employee_id)
        .where(
            and_(
                m.IncentiveLedger.created_at >= month_start,
                m.IncentiveLedger.created_at < month_end + timedelta(days=1),
            )
        )
        .group_by(m.Employee.employee_id, m.Employee.name_ar, m.Employee.name_en)
        .order_by(desc(func.sum(m.IncentiveLedger.points)))
    )

    if branch_id:
        stmt = stmt.where(m.IncentiveLedger.branch_id == branch_id)

    rows = session.execute(stmt).all()
    return {
        "month": month or date.today().strftime("%Y-%m"),
        "entries": [
            {"employee_id": r[0], "name_ar": r[1], "name_en": r[2], "points": float(r[3] or 0)}
            for r in rows
        ],
    }


@router.get("/products", dependencies=[Depends(auth_guard())])
def incentivized_products(branch_id: int | None = None, session: Session = Depends(get_session)):
    """List all products with incentive points configured (OTC incentive list).

    Returns products ordered by incentive points (highest first).
    """
    stmt = select(m.Product).where(m.Product.incentive_points > 0).order_by(desc(m.Product.incentive_points))

    products = session.scalars(stmt).all()
    return {
        "products": [
            {
                "product_id": p.product_id,
                "name_ar": p.name_ar,
                "name_en": p.name_en,
                "code": p.code,
                "sell_price": float(p.sell_price),
                "incentive_points": float(p.incentive_points),
                "is_otc": p.is_otc,
            }
            for p in products
        ]
    }


@router.post("/products/{product_id}/incentive-points", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def set_incentive_points(product_id: int, payload: IncentivePointsIn, session: Session = Depends(get_session)):
    """Set/update incentive points for a product (manager+ only).

    Pass 0 to remove the incentive.
    """
    product = session.get(m.Product, product_id)
    if product is None or product.is_deleted:
        raise HTTPException(status_code=404, detail="product not found")

    product.incentive_points = float(payload.incentive_points)
    session.commit()

    return {
        "product_id": product.product_id,
        "name_ar": product.name_ar,
        "incentive_points": float(product.incentive_points),
    }


@router.get("/candidates", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def candidates(
    metric: str = "egp_margin",
    top_n: int = 3,
    branch_id: int | None = None,
    search: str | None = None,
    session: Session = Depends(get_session),
):
    """Incentive-list builder: active ingredients with competing brands, and
    the top ``top_n`` most-profitable brands of each by ``metric``
    (egp_margin | margin_pct | profit_volume). Each brand carries all three
    metric values so the UI can re-rank live. CEO/manager only."""
    return incentives_svc.incentive_candidates(
        session, metric=metric, top_n=top_n, branch_id=branch_id or None, search=search
    )


@router.post("/apply", dependencies=[Depends(auth_guard(("ceo", "manager")))])
def apply(payload: ApplyIn, session: Session = Depends(get_session)):
    """Bulk set/clear incentive points from the builder (points 0 = remove).
    CEO/manager only."""
    return incentives_svc.apply_incentives(
        session, [i.model_dump() for i in payload.items]
    )


@router.get("/employee/{employee_id}", dependencies=[Depends(auth_guard())])
def employee_incentive_history(
    employee_id: int, month: str | None = None, session: Session = Depends(get_session)
):
    """Incentive history for one employee: monthly summary and per-product breakdown.

    Args:
        employee_id: employee to query
        month: "YYYY-MM" format (None = current month)

    Returns:
        Monthly summary + detailed ledger entries.
    """
    employee = session.get(m.Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="employee not found")

    if month:
        try:
            month_date = datetime.strptime(month, "%Y-%m").date()
        except ValueError:
            month_date = date.today().replace(day=1)
    else:
        month_date = date.today().replace(day=1)

    month_start = month_date
    month_end = (month_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    stmt = (
        select(m.IncentiveLedger)
        .where(
            and_(
                m.IncentiveLedger.employee_id == employee_id,
                m.IncentiveLedger.created_at >= month_start,
                m.IncentiveLedger.created_at < month_end + timedelta(days=1),
            )
        )
        .order_by(desc(m.IncentiveLedger.created_at))
    )

    entries = session.scalars(stmt).all()
    total_points = sum(float(e.points) for e in entries)

    return {
        "employee_id": employee_id,
        "name_ar": employee.name_ar,
        "month": month or date.today().strftime("%Y-%m"),
        "total_points": total_points,
        "entries": [
            {
                "entry_id": e.entry_id,
                "sale_id": e.sale_id,
                "product_id": e.product_id,
                "points": float(e.points),
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
    }
