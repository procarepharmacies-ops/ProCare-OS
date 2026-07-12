"""Predictive auto-purchasing under a daily budget.

Owner's rule: the purchasing budget is **80% of average daily sales**
(``PURCHASE_BUDGET_PCT``, default 0.8). Every run:

1. Computes the budget from the trailing 30-day average daily revenue.
2. Scores demand per product from three signals:
     * sales velocity (avg units/day, trailing 30 days),
     * prescription mentions (what area doctors are writing — the reader),
     * open customer requests on the shortage sheet.
3. Proposes order quantities to cover ``cover_days`` beyond ``lead_time_days``,
   most-urgent first, and CUTS OFF at the budget (cost-priced).
4. Writes ``PurchaseOrderDraft`` rows (reason ``predictive``) — drafts only, a
   human approves before anything is sent to a vendor.
"""
from __future__ import annotations

import os
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services import prescriptions as rx
from app.services.alerts import _avg_daily_consumption
from app.services.common import available_stock_filter, branch_filter, money, sql_day, today


def budget_pct() -> float:
    try:
        return float(os.environ.get("PURCHASE_BUDGET_PCT", "0.8") or 0.8)
    except ValueError:
        return 0.8


def daily_budget(session: Session, branch_id: int | None = None, days: int = 30) -> dict:
    """The purchasing budget: 80% (configurable) of average daily sales."""
    start = today() - timedelta(days=days - 1)
    revenue = session.execute(
        select(func.coalesce(func.sum(m.Sale.total_net), 0)).where(
            m.Sale.is_return == False,  # noqa: E712
            branch_filter(m.Sale, branch_id),
            sql_day(m.Sale.sale_date) >= start,
        )
    ).scalar_one()
    avg_daily = float(revenue) / days
    pct = budget_pct()
    # What was already spent on purchases today counts against today's budget.
    spent_today = session.execute(
        select(func.coalesce(func.sum(m.Purchase.total_gross), 0)).where(
            m.Purchase.is_return == False,  # noqa: E712
            branch_filter(m.Purchase, branch_id),
            m.Purchase.bill_date == today(),
        )
    ).scalar_one()
    budget = avg_daily * pct
    return {
        "window_days": days,
        "avg_daily_sales": money(avg_daily),
        "budget_pct": pct,
        "daily_budget": money(budget),
        "spent_today": money(spent_today),
        "remaining_today": money(max(budget - float(spent_today), 0)),
    }


def _on_hand(session: Session, branch_id: int | None) -> dict[int, float]:
    rows = session.execute(
        select(m.StockBatch.product_id, func.sum(m.StockBatch.amount))
        .where(available_stock_filter(), branch_filter(m.StockBatch, branch_id))
        .group_by(m.StockBatch.product_id)
    ).all()
    return {pid: float(q) for pid, q in rows}


def _shortage_signal(session: Session, branch_id: int | None) -> dict[int, float]:
    """Open shortage-sheet quantities per catalogue product (customer demand)."""
    q = select(m.ShortageItem.product_id, func.sum(m.ShortageItem.qty_requested)).where(
        m.ShortageItem.status == "open", m.ShortageItem.product_id != None  # noqa: E711
    )
    if branch_id:
        q = q.where(m.ShortageItem.branch_id == branch_id)
    return {pid: float(qty) for pid, qty in session.execute(q.group_by(m.ShortageItem.product_id)).all()}


def _rx_boost(product: m.Product, rx_counts: dict[str, int]) -> int:
    """Prescription mentions matching this product by name or ingredient."""
    if not rx_counts:
        return 0
    names = [n.lower() for n in (product.name_ar, product.name_en, product.scientific_name) if n]
    hits = 0
    for drug_name, count in rx_counts.items():
        for n in names:
            if drug_name in n or n in drug_name:
                hits += count
                break
    return hits


def _other_branch_stock(session: Session, branch_id: int, product_ids: list[int]) -> dict[int, list[dict]]:
    """Live availability of these products at every OTHER branch."""
    if not product_ids:
        return {}
    rows = session.execute(
        select(
            m.StockBatch.product_id, m.Branch.branch_id, m.Branch.name_ar,
            func.sum(m.StockBatch.amount),
        )
        .join(m.Branch, m.Branch.branch_id == m.StockBatch.branch_id)
        .where(
            m.StockBatch.product_id.in_(product_ids),
            m.StockBatch.branch_id != branch_id,
            available_stock_filter(),
        )
        .group_by(m.StockBatch.product_id, m.Branch.branch_id, m.Branch.name_ar)
    ).all()
    out: dict[int, list[dict]] = {}
    for pid, bid, bname, qty in rows:
        if qty and float(qty) > 0:
            out.setdefault(pid, []).append({"branch_id": bid, "branch": bname, "on_hand": money(qty)})
    return out


def purchase_plan(session: Session, branch_id: int) -> dict:
    """كشكول نواقص الفرع — the owner's purchasing doctrine, in order:

    1. أصناف رصيدها صفر (stocked-out items that actually sell),
    2. طلبات العملاء (open shortage-sheet requests),
    3. أصناف تحت الحد الأدنى (below min-stock).

    THE RULE: before buying anything, look at the other branches — if the item
    is available there, transfer it NOW and defer the purchase. Each row says
    ``action: transfer`` (with where/how much) or ``action: buy``.
    """
    consumption = _avg_daily_consumption(session, branch_id)
    on_hand = _on_hand(session, branch_id)
    requests = _shortage_signal(session, branch_id)

    entries: list[dict] = []
    seen: set[int] = set()

    def _need(pid: int, min_stock: float, req_qty: float) -> float:
        daily = consumption.get(pid, 0.0)
        cover = daily * 14  # two weeks of demand
        return max(cover, float(min_stock or 0), req_qty, 1.0) - on_hand.get(pid, 0.0)

    products = {
        p.product_id: p
        for p in session.scalars(
            select(m.Product).where(m.Product.is_deleted == False)  # noqa: E712
        )
    }
    # Priority 1: sells (recent consumption) but the shelf is EMPTY.
    for pid, daily in consumption.items():
        if daily > 0 and on_hand.get(pid, 0.0) <= 0 and pid in products:
            entries.append({"product_id": pid, "priority": 1, "reason": "رصيد صفر"})
            seen.add(pid)
    # Priority 2: a customer asked for it (open shortage sheet).
    for pid in requests:
        if pid not in seen and pid in products:
            entries.append({"product_id": pid, "priority": 2, "reason": "طلب عميل"})
            seen.add(pid)
    # Priority 3: below its minimum.
    for pid, p in products.items():
        if pid in seen or float(p.min_stock or 0) <= 0:
            continue
        if on_hand.get(pid, 0.0) < float(p.min_stock):
            entries.append({"product_id": pid, "priority": 3, "reason": "تحت الحد الأدنى"})

    others = _other_branch_stock(session, branch_id, [e["product_id"] for e in entries])
    rows = []
    for e in entries:
        p = products[e["product_id"]]
        need = round(_need(p.product_id, p.min_stock, requests.get(p.product_id, 0.0)), 3)
        if need <= 0:
            continue
        avail = others.get(p.product_id, [])
        transferable = sum(b["on_hand"] for b in avail)
        action = "transfer" if transferable >= min(need, 1.0) else "buy"
        rows.append(
            {
                "product_id": p.product_id,
                "name_ar": p.name_ar,
                "name_en": p.name_en,
                "priority": e["priority"],
                "reason": e["reason"],
                "on_hand": money(on_hand.get(p.product_id, 0.0)),
                "need": money(need),
                "requested_by_customers": money(requests.get(p.product_id, 0.0)),
                "other_branches": avail,
                "action": action,
                "buy_price": money(p.buy_price),
                "est_cost": money(need * float(p.buy_price or 0)),
            }
        )
    rows.sort(key=lambda r: (r["priority"], -r["est_cost"]))
    return {
        "branch_id": branch_id,
        "rows": rows,
        "transfer_first": sum(1 for r in rows if r["action"] == "transfer"),
        "to_buy": sum(1 for r in rows if r["action"] == "buy"),
        "budget": daily_budget(session, branch_id),
    }


def consolidated_plan(session: Session) -> dict:
    """طلبية شراء مجمعة للفروع — one vendor order combining every branch's BUY
    rows (transfer-first rows are excluded: they're moved, not bought), under
    the whole-network 80% budget."""
    branches = session.scalars(select(m.Branch).where(m.Branch.is_active == True)).all()  # noqa: E712
    per_product: dict[int, dict] = {}
    for b in branches:
        plan = purchase_plan(session, b.branch_id)
        for r in plan["rows"]:
            if r["action"] != "buy":
                continue
            agg = per_product.setdefault(
                r["product_id"],
                {
                    "product_id": r["product_id"],
                    "name_ar": r["name_ar"],
                    "priority": r["priority"],
                    "total_need": 0.0,
                    "buy_price": r["buy_price"],
                    "per_branch": [],
                },
            )
            agg["total_need"] = round(agg["total_need"] + r["need"], 3)
            agg["priority"] = min(agg["priority"], r["priority"])
            agg["per_branch"].append({"branch_id": b.branch_id, "branch": b.name_ar, "need": r["need"]})
    rows = sorted(per_product.values(), key=lambda r: (r["priority"], -r["total_need"] * r["buy_price"]))
    for r in rows:
        r["est_cost"] = money(r["total_need"] * r["buy_price"])
    budget = daily_budget(session, None)
    return {
        "rows": rows,
        "total_cost": money(sum(r["est_cost"] for r in rows)),
        "budget": budget,
    }


def propose(
    session: Session,
    branch_id: int | None = None,
    *,
    lead_time_days: int = 7,
    cover_days: int = 14,
) -> dict:
    """Compute the prioritized, budget-capped proposal WITHOUT writing drafts."""
    consumption = _avg_daily_consumption(session, branch_id)
    on_hand = _on_hand(session, branch_id)
    shortage = _shortage_signal(session, branch_id)
    rx_counts = rx.demand_signal(session, branch_id, days=30)
    budget = daily_budget(session, branch_id)
    remaining = budget["remaining_today"]

    products = session.scalars(
        select(m.Product).where(
            m.Product.is_active == True,  # noqa: E712
            m.Product.is_deleted == False,  # noqa: E712
        )
    ).all()

    candidates = []
    for p in products:
        pid = p.product_id
        daily = consumption.get(pid, 0.0)
        rx_hits = _rx_boost(p, rx_counts)
        requested = shortage.get(pid, 0.0)
        have = on_hand.get(pid, 0.0)
        # Predicted demand over the cover horizon: sales velocity plus the
        # prescription/request signals (each mention ≈ one expected unit).
        predicted = daily * (lead_time_days + cover_days) + rx_hits + requested
        need = max(predicted - have, 0.0)
        below_min = have < float(p.min_stock or 0)
        if need <= 0 and not below_min:
            continue
        qty = max(need, float(p.min_stock or 0) - have)
        qty = float(round(qty))
        if qty <= 0:
            continue
        cost = float(p.buy_price or 0) * qty
        # Urgency: days of stock left (0 velocity → only min-stock urgency).
        days_left = (have / daily) if daily > 0 else 999
        candidates.append(
            {
                "product_id": pid,
                "name_ar": p.name_ar,
                "name_en": p.name_en,
                "on_hand": money(have),
                "avg_daily_sales_units": round(daily, 2),
                "rx_mentions_30d": rx_hits,
                "customer_requests": money(requested),
                "days_of_stock_left": round(days_left, 1),
                "suggested_qty": qty,
                "unit_cost": money(p.buy_price or 0),
                "est_cost": money(cost),
                "reason": "predictive",
            }
        )

    # Most urgent first (least days of cover), then biggest demand signal.
    candidates.sort(key=lambda c: (c["days_of_stock_left"], -(c["rx_mentions_30d"] + c["customer_requests"])))

    within, deferred, running = [], [], 0.0
    for c in candidates:
        if running + c["est_cost"] <= remaining + 1e-9:
            running += c["est_cost"]
            within.append(c)
        else:
            deferred.append(c)

    return {
        "budget": budget,
        "proposed": within,
        "proposed_cost": money(running),
        "deferred_over_budget": deferred[:50],
        "signals": {
            "products_with_rx_signal": sum(1 for c in candidates if c["rx_mentions_30d"] > 0),
            "products_with_customer_requests": sum(1 for c in candidates if c["customer_requests"] > 0),
        },
    }


def generate_drafts(session: Session, branch_id: int, **kwargs) -> dict:
    """Write the within-budget proposal as PurchaseOrderDraft rows (replacing
    prior still-pending predictive drafts for the branch so reruns don't pile up)."""
    plan = propose(session, branch_id, **kwargs)
    session.query(m.PurchaseOrderDraft).filter(
        m.PurchaseOrderDraft.branch_id == branch_id,
        m.PurchaseOrderDraft.status == "draft",
        m.PurchaseOrderDraft.reason == "predictive",
    ).delete()
    created = 0
    for c in plan["proposed"]:
        session.add(
            m.PurchaseOrderDraft(
                branch_id=branch_id,
                product_id=c["product_id"],
                on_hand=c["on_hand"],
                suggested_qty=c["suggested_qty"],
                reason="predictive",
                status="draft",
            )
        )
        created += 1
    session.commit()
    return {**plan, "drafts_created": created}
