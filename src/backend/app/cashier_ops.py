"""Cashier shift operations — shift lifecycle and performance tracking."""
from __future__ import annotations

from datetime import datetime
from app.db import get_db


def open_cashier_shift(cashier_id: int, branch_id: str, opening_float: float) -> int:
    """
    Open a cashier shift.

    Args:
      cashier_id: employees.id
      branch_id: 'main' | 'elsanta' | 'mshala'
      opening_float: cash on hand at start

    Returns:
      shift_id
    """
    db = get_db()
    branch = branch_id.lower().strip()

    # Verify cashier exists
    emp = db.query_one("SELECT id FROM employees WHERE id = ?", [cashier_id])
    if not emp:
        raise ValueError(f"Cashier {cashier_id} not found")

    # Check for active shift (should be none)
    active = db.query_one(
        "SELECT id FROM cashier_shifts WHERE cashier_id = ? AND closed_at IS NULL",
        [cashier_id],
    )
    if active:
        raise ValueError(f"Cashier {cashier_id} already has an open shift")

    sql = """
        INSERT INTO cashier_shifts
        (cashier_id, branch_id, opening_float, opened_at)
        VALUES (?, ?, ?, datetime('now'))
    """
    db.execute(sql, [cashier_id, branch, opening_float])

    return db.query_one("SELECT last_insert_rowid() as id", [])["id"]


def close_cashier_shift(shift_id: int, closing_float: float, notes: str = "") -> dict:
    """
    Close a cashier shift with reconciliation.

    Compares opening_float + total_sales vs. closing_float.

    Args:
      shift_id: cashier_shifts.id
      closing_float: cash on hand at close
      notes: optional closing notes

    Returns:
      {
        "shift_id": int,
        "cashier_id": int,
        "opened_at": str,
        "closed_at": str,
        "opening_float": float,
        "closing_float": float,
        "total_sales": float,
        "expected_cash": float,
        "actual_cash": float,
        "variance": float,
        "variance_pct": float
      }
    """
    db = get_db()

    shift = db.query_one(
        """
        SELECT id, cashier_id, opening_float, opened_at
        FROM cashier_shifts
        WHERE id = ?
        """,
        [shift_id],
    )

    if not shift:
        raise ValueError(f"Shift {shift_id} not found")

    cashier_id = shift["cashier_id"]

    # Sum all sales by this cashier since shift opened
    sales_sql = """
        SELECT COALESCE(SUM(total_amount), 0) as total
        FROM sales
        WHERE cashier_id = ? AND created_at >= ?
    """
    sales_result = db.query_one(sales_sql, [cashier_id, shift["opened_at"]])
    total_sales = sales_result["total"] or 0

    expected_cash = shift["opening_float"] + total_sales
    variance = closing_float - expected_cash
    variance_pct = (variance / expected_cash * 100) if expected_cash > 0 else 0

    # Close the shift
    close_sql = """
        UPDATE cashier_shifts
        SET closed_at = datetime('now'), closing_float = ?, closing_notes = ?
        WHERE id = ?
    """
    db.execute(close_sql, [closing_float, notes or "", shift_id])

    return {
        "shift_id": shift_id,
        "cashier_id": cashier_id,
        "opened_at": shift["opened_at"],
        "closed_at": datetime.now().isoformat(),
        "opening_float": shift["opening_float"],
        "closing_float": closing_float,
        "total_sales": total_sales,
        "expected_cash": expected_cash,
        "actual_cash": closing_float,
        "variance": variance,
        "variance_pct": variance_pct,
    }


def get_current_shift(cashier_id: int) -> dict | None:
    """Get active (unclosed) shift for a cashier, or None."""
    db = get_db()

    sql = """
        SELECT id, opening_float, opened_at
        FROM cashier_shifts
        WHERE cashier_id = ? AND closed_at IS NULL
        LIMIT 1
    """
    return db.query_one(sql, [cashier_id])


def get_cashier_performance(
    cashier_id: int, branch_id: str, date_from: str, date_to: str
) -> dict:
    """
    Get cashier performance metrics for a date range.

    Args:
      cashier_id: employees.id
      branch_id: 'main' | 'elsanta' | 'mshala'
      date_from: ISO date string
      date_to: ISO date string

    Returns:
      {
        "cashier_id": int,
        "branch_id": str,
        "period": { "from": str, "to": str },
        "bills_count": int,
        "items_sold": int,
        "total_revenue": float,
        "total_cost": float,
        "total_profit": float,
        "avg_basket": float,
        "avg_profit_per_bill": float,
        "shifts_count": int,
        "cash_variance": float,
        "cash_variance_pct": float
      }
    """
    db = get_db()
    branch = branch_id.lower().strip()

    # Sales metrics
    sales_sql = """
        SELECT
          COUNT(DISTINCT s.id) as bills,
          COALESCE(SUM(sl.qty_sold), 0) as items,
          COALESCE(SUM(s.total_amount), 0) as revenue,
          COALESCE(SUM(sl.qty_sold * sl.unit_cost), 0) as cost
        FROM sales s
        LEFT JOIN sale_lines sl ON s.id = sl.sale_id
        WHERE s.cashier_id = ? AND s.branch_id = ?
          AND DATE(s.created_at) BETWEEN ? AND ?
    """
    sales_result = db.query_one(sales_sql, [cashier_id, branch, date_from, date_to])

    bills_count = sales_result["bills"] or 0
    items_sold = sales_result["items"] or 0
    total_revenue = sales_result["revenue"] or 0
    total_cost = sales_result["cost"] or 0
    total_profit = total_revenue - total_cost

    avg_basket = (total_revenue / bills_count) if bills_count > 0 else 0
    avg_profit = (total_profit / bills_count) if bills_count > 0 else 0

    # Shift metrics
    shifts_sql = """
        SELECT COUNT(*) as shifts, COALESCE(SUM(closing_float - opening_float -
          (SELECT COALESCE(SUM(total_amount), 0) FROM sales
           WHERE cashier_id = ? AND created_at >= cashier_shifts.opened_at
           AND created_at < COALESCE(cashier_shifts.closed_at, datetime('now')))), 0) as variance
        FROM cashier_shifts
        WHERE cashier_id = ? AND DATE(opened_at) BETWEEN ? AND ?
    """
    shifts_result = db.query_one(shifts_sql, [cashier_id, cashier_id, date_from, date_to])

    shifts_count = shifts_result["shifts"] or 0
    total_variance = shifts_result["variance"] or 0
    variance_pct = (total_variance / total_revenue * 100) if total_revenue > 0 else 0

    return {
        "cashier_id": cashier_id,
        "branch_id": branch,
        "period": {"from": date_from, "to": date_to},
        "bills_count": bills_count,
        "items_sold": items_sold,
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "avg_basket": avg_basket,
        "avg_profit_per_bill": avg_profit,
        "shifts_count": shifts_count,
        "cash_variance": total_variance,
        "cash_variance_pct": variance_pct,
    }
