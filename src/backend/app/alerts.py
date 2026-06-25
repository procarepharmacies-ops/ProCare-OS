"""Operational alerts — expiry, low-stock / smart-reorder drafts, debtors.

Read-only in Phase 1 (shadow mode): the alerts surface what needs attention but
never mutate stock or send anything. They run per branch and consolidated, and
are consumed both by the API (`/api/alerts/*`) and the automation scheduler
(`scheduler.py`). Reorder and expiry write-offs become *actions* in Phase 2.
"""
from __future__ import annotations

from app.db import get_db
from app.queries import _branch_clause, low_stock


def expiry_alerts(branch="ALL") -> dict:
    """Batches at 90 / 30 / 7-day horizons + already-expired, with expected loss."""
    db = get_db()
    bc, bp = _branch_clause(branch, "branch_id")

    def bucket(lo, hi):
        return db.query(
            f"""SELECT product_name_ar, product_name_en, exp_date,
                       ROUND(qty_remaining,2) AS qty_remaining,
                       ROUND(expected_loss,2) AS expected_loss,
                       days_to_expiry, branch_id
                FROM vw_expiry_risk
                WHERE days_to_expiry BETWEEN ? AND ?{bc}
                ORDER BY days_to_expiry ASC""",
            (lo, hi, *bp),
        )

    expired = db.query(
        f"""SELECT product_name_ar, product_name_en, exp_date,
                   ROUND(qty_remaining,2) AS qty_remaining,
                   ROUND(expected_loss,2) AS expected_loss, days_to_expiry, branch_id
            FROM vw_expiry_risk
            WHERE days_to_expiry < 0{bc}
            ORDER BY days_to_expiry ASC""",
        bp,
    )
    # Auto-lock candidates: products whose ONLY on-hand stock is expired
    # (fixes eStock's "74 expired batches still sellable"). Advisory in Phase 1.
    lock_candidates = db.query(
        f"""SELECT p.product_id, p.name_ar AS product_name_ar, p.name_en AS product_name_en,
                   sb.branch_id, ROUND(SUM(sb.amount),2) AS expired_qty
            FROM stock_batches sb
            JOIN products p ON p.product_id = sb.product_id
            WHERE sb.amount > 0 AND p.has_expiry = 1
              AND sb.exp_date IS NOT NULL AND sb.exp_date <= date('now')
              AND NOT EXISTS (
                  SELECT 1 FROM stock_batches g
                  WHERE g.product_id = sb.product_id AND g.branch_id = sb.branch_id
                    AND g.amount > 0 AND (g.exp_date IS NULL OR g.exp_date > date('now'))
              ){bc.replace('branch_id', 'sb.branch_id')}
            GROUP BY p.product_id, sb.branch_id""",
        bp,
    )

    horizons = {"d90": bucket(0, 90), "d30": bucket(0, 30), "d7": bucket(0, 7)}
    total_loss = round(sum(r["expected_loss"] for r in horizons["d90"]) +
                       sum(r["expected_loss"] for r in expired), 2)
    return {
        "branch": str(branch).upper(),
        "counts": {
            "within_90": len(horizons["d90"]),
            "within_30": len(horizons["d30"]),
            "within_7": len(horizons["d7"]),
            "expired": len(expired),
            "lock_candidates": len(lock_candidates),
        },
        "expected_loss_at_risk": total_loss,
        "within_7": horizons["d7"],
        "within_30": horizons["d30"],
        "expired": expired,
        "lock_candidates": lock_candidates,
    }


def reorder_drafts(branch="ALL", limit=100) -> dict:
    """Smart-reorder DRAFTS for items at/below minimum. Human approves (Phase 2)."""
    items = low_stock(branch, limit=limit)
    drafts = []
    for it in items:
        on_hand = it["qty_on_hand"]
        target = max(it["min_stock"] * 2, it["min_stock"] + 10)
        suggest = int(max(target - on_hand, 0))
        if suggest <= 0:
            continue
        drafts.append({
            "product_name_ar": it["product_name_ar"],
            "product_name_en": it["product_name_en"],
            "branch_id": it["branch_id"],
            "on_hand": on_hand,
            "min_stock": it["min_stock"],
            "suggested_order_qty": suggest,
        })
    return {
        "branch": str(branch).upper(),
        "count": len(drafts),
        "note": "Draft only — no purchase order is sent. A human approves in Phase 2.",
        "drafts": drafts,
    }


def debtor_alerts(limit=100) -> dict:
    rows = get_db().query(
        """SELECT customer_name_ar, customer_name_en, mobile,
                  ROUND(balance,2) AS balance, credit_limit,
                  ROUND(over_limit_by,2) AS over_limit_by
           FROM vw_customer_debtors
           WHERE over_limit = 1
           ORDER BY over_limit_by DESC
           LIMIT ?""",
        (limit,),
    )
    return {
        "count": len(rows),
        "total_over_limit": round(sum(r["over_limit_by"] for r in rows), 2),
        "customers": rows,
    }
