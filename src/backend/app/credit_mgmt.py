"""Customer credit management — balance tracking and credit validation."""
from __future__ import annotations

from app.db import get_db


def check_credit_available(customer_id: int, amount: float) -> dict:
    """
    Check if customer has sufficient credit available.

    Args:
      customer_id: customers.id
      amount: amount to charge (in EGP)

    Returns:
      {
        "available": bool,
        "credit_limit": float,
        "current_balance": float,
        "available_credit": float,
        "over_limit_by": float (0 if not over limit)
      }
    """
    db = get_db()

    sql = """
        SELECT credit_limit, current_balance
        FROM customers
        WHERE id = ?
    """
    customer = db.query_one(sql, [customer_id])

    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    credit_limit = customer["credit_limit"] or 0
    current_balance = customer["current_balance"] or 0
    available_credit = credit_limit - current_balance

    new_balance = current_balance + amount
    over_limit_by = max(0, new_balance - credit_limit)
    will_exceed = new_balance > credit_limit

    return {
        "available": not will_exceed,
        "credit_limit": credit_limit,
        "current_balance": current_balance,
        "available_credit": available_credit,
        "over_limit_by": over_limit_by,
        "new_balance": new_balance,
        "will_exceed": will_exceed,
    }


def charge_credit(
    customer_id: int,
    amount: float,
    sale_id: int,
    branch_id: str,
    notes: str = "",
) -> int:
    """
    Charge a sale to customer credit.

    Updates customer.current_balance and creates ledger_entries.

    Args:
      customer_id: customers.id
      amount: amount to charge
      sale_id: sales.id
      branch_id: 'main' | 'elsanta' | 'mshala'
      notes: optional notes

    Returns:
      ledger_entry_id
    """
    db = get_db()
    branch = branch_id.lower().strip()

    # Verify customer exists and has credit limit
    customer = db.query_one("SELECT id, credit_limit FROM customers WHERE id = ?", [customer_id])
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    if not customer["credit_limit"]:
        raise ValueError(f"Customer {customer_id} has no credit limit")

    # Update customer balance
    sql = "UPDATE customers SET current_balance = current_balance + ? WHERE id = ?"
    db.execute(sql, [amount, customer_id])

    # Create ledger entry (customer ledger, debit)
    ledger_sql = """
        INSERT INTO ledger_entries
        (branch_id, entry_type, reference_type, reference_id, customer_id, amount, notes, created_at)
        VALUES (?, 'customer_credit', 'sale', ?, ?, ?, ?, datetime('now'))
    """
    db.execute(ledger_sql, [branch, sale_id, customer_id, amount, notes or ""])

    return db.query_one("SELECT last_insert_rowid() as id", [])["id"]


def get_customer_balance(customer_id: int) -> dict:
    """
    Get current credit status for a customer.

    Returns:
      {
        "customer_id": int,
        "name": str,
        "credit_limit": float,
        "current_balance": float,
        "available_credit": float,
        "is_over_limit": bool,
        "over_limit_by": float,
        "days_over_limit": int (estimated from ledger)
      }
    """
    db = get_db()

    customer = db.query_one(
        "SELECT id, name_ar, credit_limit, current_balance FROM customers WHERE id = ?",
        [customer_id],
    )

    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    credit_limit = customer["credit_limit"] or 0
    current_balance = customer["current_balance"] or 0
    available_credit = credit_limit - current_balance
    is_over = current_balance > credit_limit
    over_limit_by = max(0, current_balance - credit_limit)

    # Estimate days over limit (from oldest ledger entry in current balance state)
    days_over = 0
    if is_over:
        oldest_sql = """
            SELECT CAST((julianday('now') - julianday(created_at)) AS INTEGER) as days_ago
            FROM ledger_entries
            WHERE customer_id = ? AND entry_type = 'customer_credit'
            ORDER BY created_at ASC
            LIMIT 1
        """
        oldest = db.query_one(oldest_sql, [customer_id])
        days_over = oldest["days_ago"] if oldest else 0

    return {
        "customer_id": customer_id,
        "name": customer["name_ar"],
        "credit_limit": credit_limit,
        "current_balance": current_balance,
        "available_credit": available_credit,
        "is_over_limit": is_over,
        "over_limit_by": over_limit_by,
        "days_over_limit": days_over,
    }


def reconcile_customer_balance(customer_id: int) -> dict:
    """
    Recalculate customer balance from ledger (audit/reconciliation).

    Compares customers.current_balance with the sum of all ledger entries.
    If mismatch, updates customers.current_balance to ledger sum.

    Returns:
      {
        "customer_id": int,
        "recorded_balance": float,
        "ledger_sum": float,
        "mismatch": bool,
        "adjustment": float,
        "action": "none" | "corrected"
      }
    """
    db = get_db()

    customer = db.query_one(
        "SELECT id, current_balance FROM customers WHERE id = ?", [customer_id]
    )

    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    recorded_balance = customer["current_balance"] or 0

    # Sum all credit ledger entries for this customer
    ledger_sql = """
        SELECT COALESCE(SUM(amount), 0) as ledger_sum
        FROM ledger_entries
        WHERE customer_id = ? AND entry_type = 'customer_credit'
    """
    ledger_result = db.query_one(ledger_sql, [customer_id])
    ledger_sum = ledger_result["ledger_sum"] or 0

    mismatch = abs(recorded_balance - ledger_sum) > 0.01  # 1 fils tolerance
    adjustment = ledger_sum - recorded_balance

    action = "none"
    if mismatch:
        # Correct the balance
        db.execute("UPDATE customers SET current_balance = ? WHERE id = ?", [ledger_sum, customer_id])
        action = "corrected"

    return {
        "customer_id": customer_id,
        "recorded_balance": recorded_balance,
        "ledger_sum": ledger_sum,
        "mismatch": mismatch,
        "adjustment": adjustment,
        "action": action,
    }
