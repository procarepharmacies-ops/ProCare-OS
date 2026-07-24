"""Stock operations — FEFO batch picking, reservations, and deductions."""
from __future__ import annotations

from datetime import datetime, date
from app.db import get_db
from app.branches import normalize_branch


def reserve_batch_fefo(product_id: int, branch_id: str, qty_needed: int) -> list[dict]:
    """
    FEFO (First Expire First Out) batch picker.

    Allocate qty_needed across available batches, earliest expiry first.
    Create stock_movements records (type='sale_reserved').

    Args:
      product_id: product ID
      branch_id: 'main' | 'elsanta' | 'mshala'
      qty_needed: units to reserve

    Returns:
      [{ batch_id, qty_allocated, exp_date, amount_before }]
      Raises ValueError if insufficient stock available.
    """
    db = get_db()
    branch = normalize_branch(branch_id)

    # Query available batches: exp_date > today, amount > 0, ordered by exp_date ASC (FEFO)
    sql = """
        SELECT batch_id, amount, exp_date
        FROM stock_batches
        WHERE product_id = ? AND branch_id = ?
          AND amount > 0
          AND (exp_date > date('now') OR exp_date IS NULL)
        ORDER BY exp_date ASC, batch_id ASC
    """
    batches = db.query(sql, [product_id, branch])

    if not batches:
        raise ValueError(f"No available stock for product {product_id} on branch {branch}")

    allocated = []
    qty_remaining = qty_needed

    for batch in batches:
        if qty_remaining <= 0:
            break

        batch_id = batch["batch_id"]
        available_qty = batch["amount"]
        exp_date = batch["exp_date"]

        qty_to_allocate = min(qty_remaining, available_qty)

        allocated.append(
            {
                "batch_id": batch_id,
                "qty_allocated": qty_to_allocate,
                "exp_date": exp_date,
                "amount_before": available_qty,
            }
        )

        qty_remaining -= qty_to_allocate

    if qty_remaining > 0:
        raise ValueError(
            f"Insufficient stock for product {product_id}. Need {qty_needed}, "
            f"available {qty_needed - qty_remaining}"
        )

    return allocated


def create_stock_movement(
    batch_id: int,
    movement_type: str,
    qty: int,
    branch_id: str,
    reference_id: int | None = None,
    reference_type: str | None = None,
    notes: str | None = None,
) -> int:
    """
    Create a stock movement record.

    Args:
      batch_id: stock batch ID
      movement_type: 'sale_reserved' | 'sale_deduction' | 'purchase' | 'transfer' | 'expiry_lock'
      qty: quantity moved
      branch_id: 'main' | 'elsanta' | 'mshala'
      reference_id: sale_id | purchase_id | transfer_id
      reference_type: 'sale' | 'purchase' | 'transfer'
      notes: optional notes

    Returns:
      movement_id
    """
    db = get_db()
    branch = normalize_branch(branch_id)

    sql = """
        INSERT INTO stock_movements
        (batch_id, movement_type, qty, branch_id, reference_id, reference_type, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """
    db.execute(
        sql,
        [
            batch_id,
            movement_type,
            qty,
            branch,
            reference_id,
            reference_type,
            notes,
        ],
    )

    # Return the last inserted ID
    return db.query_one("SELECT last_insert_rowid() as id", [])["id"]


def deduct_stock(allocations: list[dict], sale_id: int, branch_id: str) -> None:
    """
    Apply stock deductions for a completed sale.

    Updates stock_batches.amount and creates stock_movements records
    (type='sale_deduction') for each allocation.

    Args:
      allocations: [{ batch_id, qty_allocated }, ...]
      sale_id: sales.id
      branch_id: 'main' | 'elsanta' | 'mshala'
    """
    db = get_db()
    branch = normalize_branch(branch_id)

    for alloc in allocations:
        batch_id = alloc["batch_id"]
        qty = alloc["qty_allocated"]

        # Deduct from stock_batches
        sql = "UPDATE stock_batches SET amount = amount - ? WHERE batch_id = ?"
        db.execute(sql, [qty, batch_id])

        # Create movement record
        create_stock_movement(
            batch_id=batch_id,
            movement_type="sale_deduction",
            qty=qty,
            branch_id=branch,
            reference_id=sale_id,
            reference_type="sale",
        )


def lock_expired_batches(branch_id: str) -> int:
    """
    Lock (set amount=0) for expired batches.

    Called daily by automation; prevents expired items from being sold.

    Returns:
      count of batches locked
    """
    db = get_db()
    branch = normalize_branch(branch_id)

    sql = """
        UPDATE stock_batches
        SET amount = 0
        WHERE branch_id = ? AND exp_date < date('now') AND amount > 0
    """
    db.execute(sql, [branch])

    # Count affected rows via a separate query
    count_sql = """
        SELECT COUNT(*) as count
        FROM stock_batches
        WHERE branch_id = ? AND exp_date < date('now') AND amount = 0
    """
    result = db.query_one(count_sql, [branch])
    return result["count"]


def get_stock_on_hand(product_id: int, branch_id: str) -> int:
    """Total available stock (amount > 0, not expired)."""
    db = get_db()
    branch = normalize_branch(branch_id)

    sql = """
        SELECT COALESCE(SUM(amount), 0) as total
        FROM stock_batches
        WHERE product_id = ? AND branch_id = ?
          AND amount > 0
          AND (exp_date > date('now') OR exp_date IS NULL)
    """
    result = db.query_one(sql, [product_id, branch])
    return result["total"] or 0


