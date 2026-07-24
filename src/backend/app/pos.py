"""POS (Point of Sale) transaction engine — atomic sale creation and management."""
from __future__ import annotations

from datetime import datetime
from app.db import get_db
from app.stock_ops import reserve_batch_fefo, deduct_stock, get_stock_on_hand
from app.credit_mgmt import check_credit_available, charge_credit
from app.cashier_ops import get_current_shift


class CreateSaleRequest:
    """POS sale creation request."""

    def __init__(
        self,
        branch_id: str,
        cashier_id: int,
        customer_id: int | None,
        line_items: list[dict],
        payment_method: str,
        credit_amount: float = 0,
    ):
        self.branch_id = branch_id.lower().strip()
        self.cashier_id = cashier_id
        self.customer_id = customer_id
        self.line_items = line_items  # [{ product_id, qty_sold, price_override? }, ...]
        self.payment_method = payment_method  # 'cash' | 'credit' | 'mixed'
        self.credit_amount = credit_amount

    def validate(self) -> tuple[bool, str]:
        """Validate request before processing."""
        if self.branch_id not in ("main", "elsanta", "mshala"):
            return False, f"Invalid branch: {self.branch_id}"

        if self.cashier_id <= 0:
            return False, "Invalid cashier_id"

        if not self.line_items:
            return False, "No items in sale"

        if self.payment_method not in ("cash", "credit", "mixed"):
            return False, f"Invalid payment_method: {self.payment_method}"

        if self.payment_method in ("credit", "mixed") and not self.customer_id:
            return False, "credit sale requires customer_id"

        if self.payment_method == "credit" and self.credit_amount <= 0:
            return False, "credit sale requires credit_amount > 0"

        for item in self.line_items:
            if item.get("qty_sold", 0) <= 0:
                return False, "qty_sold must be > 0"

        return True, ""


def create_sale(req: CreateSaleRequest) -> dict:
    """
    Create a complete sale transaction (atomic).

    Validates inventory, customer credit, prices. Creates sale + sale_lines,
    deducts stock (FEFO), updates customer balance, posts ledger entries.

    Args:
      req: CreateSaleRequest

    Returns:
      {
        "sale_id": int,
        "branch_id": str,
        "cashier_id": int,
        "customer_id": int | None,
        "sale_date": str,
        "total_amount": float,
        "items_count": int,
        "payment_method": str,
        "status": "completed" | "pending_credit_approval",
        "lines": [{ product_id, qty_sold, unit_price, amount }, ...]
      }

    Raises:
      ValueError: validation error, insufficient stock, over credit limit, etc.
    """
    valid, reason = req.validate()
    if not valid:
        raise ValueError(f"Invalid sale request: {reason}")

    db = get_db()

    # Verify cashier exists and has active shift
    cashier = db.query_one("SELECT id FROM employees WHERE id = ?", [req.cashier_id])
    if not cashier:
        raise ValueError(f"Cashier {req.cashier_id} not found")

    shift = get_current_shift(req.cashier_id)
    if not shift:
        raise ValueError(f"Cashier {req.cashier_id} has no active shift")

    # Verify products & reserve stock (FEFO)
    allocations = {}  # product_id -> [{ batch_id, qty_allocated }, ...]
    sale_lines_data = []

    for item in req.line_items:
        product_id = item["product_id"]
        qty_needed = item["qty_sold"]
        price_override = item.get("price_override")

        # Get product
        product = db.query_one(
            "SELECT id, name_ar, price FROM products WHERE id = ?", [product_id]
        )
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Check stock availability
        available = get_stock_on_hand(product_id, req.branch_id)
        if available < qty_needed:
            raise ValueError(
                f"Insufficient stock for {product['name_ar']}: need {qty_needed}, available {available}"
            )

        # Reserve batches (FEFO)
        batches = reserve_batch_fefo(product_id, req.branch_id, qty_needed)
        allocations[product_id] = batches

        # Build sale_line
        unit_price = price_override or product["price"] or 0
        line_amount = qty_needed * unit_price

        sale_lines_data.append(
            {
                "product_id": product_id,
                "qty_sold": qty_needed,
                "unit_price": unit_price,
                "amount": line_amount,
                "batches": batches,
            }
        )

    # Validate customer credit (if credit sale)
    total_amount = sum(line["amount"] for line in sale_lines_data)

    if req.payment_method in ("credit", "mixed"):
        credit_check = check_credit_available(req.customer_id, req.credit_amount)
        if not credit_check["available"]:
            raise ValueError(
                f"Customer over credit limit by {credit_check['over_limit_by']:.2f} EGP"
            )

    # All validations pass; begin atomic transaction
    try:
        # Create sales header
        # Map to schema: use sale_class_id=1 for cash, 2 for credit
        sale_class_id = 1 if req.payment_method == "cash" else 2
        is_credit = 1 if req.payment_method in ("credit", "mixed") else 0

        sale_sql = """
            INSERT INTO sales
            (branch_id, cashier_id, customer_id, sale_class_id, sale_date,
             total_gross, total_discount, total_net, cash_paid, card_paid,
             is_credit, payment_method)
            VALUES (?, ?, ?, ?, datetime('now'), ?, 0, ?, ?, 0, ?)
        """
        # For now, gross = net (no discounts in Phase 2 implementation)
        db.execute(
            sale_sql,
            [
                1,  # branch_id as integer (will need to map from code)
                req.cashier_id,
                req.customer_id,
                sale_class_id,
                total_amount,  # total_gross
                total_amount,  # total_net
                total_amount if req.payment_method == "cash" else 0,  # cash_paid
                req.payment_method,
            ],
        )

        sale_id = db.query_one("SELECT last_insert_rowid() as sale_id", [])["sale_id"]

        # Create sale_lines
        for line in sale_lines_data:
            line_sql = """
                INSERT INTO sale_lines
                (sale_id, product_id, amount, sell_price, buy_price, total_sell,
                 qty_sold, unit_price, unit_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            # For cost, assume it's the product's buy_price for now
            product = db.query_one(
                "SELECT buy_price FROM products WHERE product_id = ?",
                [line["product_id"]]
            )
            buy_price = (product["buy_price"] if product else 0) or 0

            db.execute(
                line_sql,
                [
                    sale_id,
                    line["product_id"],
                    line["amount"],
                    line["unit_price"],
                    buy_price,
                    line["amount"],  # total_sell
                    line["qty_sold"],
                    line["unit_price"],
                    buy_price,  # unit_cost
                ],
            )

        # Deduct stock for all allocations
        for product_id, batches in allocations.items():
            deduct_stock(batches, sale_id, req.branch_id)

        # Charge customer credit (if applicable)
        if req.payment_method in ("credit", "mixed"):
            charge_credit(
                req.customer_id,
                req.credit_amount,
                sale_id,
                req.branch_id,
                notes=f"Sale #{sale_id}",
            )

        # Create GL ledger entry (revenue)
        ledger_sql = """
            INSERT INTO ledger_entries
            (branch_id, entry_date, account_type, ref_type, ref_id, debit, note)
            VALUES (?, datetime('now'), 'cash', 'sale', ?, ?, 'POS sale')
        """
        db.execute(ledger_sql, [1, sale_id, total_amount])

        return {
            "sale_id": sale_id,
            "branch_id": req.branch_id,
            "cashier_id": req.cashier_id,
            "customer_id": req.customer_id,
            "sale_date": datetime.now().isoformat(),
            "total_amount": total_amount,
            "items_count": len(sale_lines_data),
            "payment_method": req.payment_method,
            "status": "completed",
            "lines": sale_lines_data,
        }

    except Exception as e:
        # Transaction rolled back by DB adapter on exception
        raise ValueError(f"Sale creation failed: {str(e)}")


def get_sale_receipt(sale_id: int) -> dict:
    """
    Fetch a completed sale with all line details (for reprint/receipt).

    Returns:
      {
        "sale_id": int,
        "branch_id": str,
        "sale_date": str,
        "cashier_id": int,
        "customer_id": int | None,
        "total_amount": float,
        "items": [
          { product_id, name_ar, qty_sold, unit_price, amount, batches: [...] },
          ...
        ]
      }
    """
    db = get_db()

    sale = db.query_one(
        """
        SELECT sale_id, branch_id, created_at, cashier_id, customer_id, total_net
        FROM sales WHERE sale_id = ?
        """,
        [sale_id],
    )

    if not sale:
        raise ValueError(f"Sale {sale_id} not found")

    lines = db.query(
        """
        SELECT sl.product_id, sl.qty_sold, sl.unit_price, sl.amount, p.name_ar
        FROM sale_lines sl
        JOIN products p ON sl.product_id = p.product_id
        WHERE sl.sale_id = ?
        """,
        [sale_id],
    )

    # Enrich lines with batch info
    for line in lines:
        product_id = line["product_id"]
        batches = db.query(
            """
            SELECT DISTINCT batch_id, exp_date
            FROM stock_movements
            WHERE reference_id = ? AND reference_type = 'sale'
              AND movement_type = 'sale_deduction'
              AND batch_id IN (
                SELECT batch_id FROM stock_batches WHERE product_id = ?
              )
            """,
            [sale_id, product_id],
        )
        line["batches"] = batches

    return {
        "sale_id": sale_id,
        "branch_id": sale["branch_id"],
        "sale_date": sale["created_at"],
        "cashier_id": sale["cashier_id"],
        "customer_id": sale["customer_id"],
        "total_amount": sale["total_net"],
        "items": lines,
    }


def create_return(
    original_sale_id: int,
    return_lines: list[dict],
    reason: str,
    approver_id: int,
) -> dict:
    """
    Create a return (reversal) of a prior sale.

    Reverses stock deductions and customer charges.

    Args:
      original_sale_id: sales.id to reverse
      return_lines: [{ product_id, qty_returned }, ...]
      reason: reason for return
      approver_id: manager approving the return

    Returns:
      {
        "return_id": int,
        "original_sale_id": int,
        "return_date": str,
        "return_amount": float,
        "status": "completed"
      }
    """
    db = get_db()

    # Verify original sale
    original_sale = db.query_one(
        "SELECT sale_id, total_net, customer_id, branch_id FROM sales WHERE sale_id = ?",
        [original_sale_id],
    )
    if not original_sale:
        raise ValueError(f"Original sale {original_sale_id} not found")

    # Create return record
    return_sql = """
        INSERT INTO sales
        (branch_id, is_return, original_sale_id, customer_id, total_net, payment_method)
        VALUES (?, 1, ?, ?, ?, 'return')
    """
    db.execute(
        return_sql,
        [
            original_sale["branch_id"],
            original_sale_id,
            original_sale["customer_id"],
            original_sale["total_net"],
        ],
    )

    return_id = db.query_one("SELECT last_insert_rowid() as sale_id", [])["sale_id"]

    # Reverse stock movements (add back)
    mvmt_sql = "SELECT batch_id, qty FROM stock_movements WHERE reference_id = ? AND movement_type = 'sale_deduction'"
    movements = db.query(mvmt_sql, [original_sale_id])

    for mvmt in movements:
        batch_id = mvmt["batch_id"]
        qty = mvmt["qty"]

        # Add stock back
        db.execute("UPDATE stock_batches SET amount = amount + ? WHERE batch_id = ?", [qty, batch_id])

        # Create reverse movement
        reverse_sql = """
            INSERT INTO stock_movements
            (batch_id, movement_type, qty, reference_id, reference_type, notes)
            VALUES (?, 'return', ?, ?, 'return', ?)
        """
        db.execute(reverse_sql, [batch_id, qty, return_id, reason])

    # Reverse customer credit (if applicable)
    if original_sale["customer_id"]:
        db.execute(
            "UPDATE customers SET current_balance = current_balance - ? WHERE customer_id = ?",
            [original_sale["total_net"], original_sale["customer_id"]],
        )

    # Create GL reversal
    gl_sql = """
        INSERT INTO ledger_entries
        (branch_id, entry_date, account_type, ref_type, ref_id, credit, note)
        VALUES (?, datetime('now'), 'cash', 'return', ?, ?, ?)
    """
    db.execute(gl_sql, [original_sale["branch_id"], return_id, original_sale["total_net"], reason])

    return {
        "return_id": return_id,
        "original_sale_id": original_sale_id,
        "return_date": datetime.now().isoformat(),
        "return_amount": original_sale["total_net"],
        "status": "completed",
    }
