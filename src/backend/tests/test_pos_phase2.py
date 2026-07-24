"""Unit tests for Phase 2 POS operations (stock, credit, cashier, sales)."""
import pytest
from datetime import datetime, date

from app.pos import CreateSaleRequest, create_sale, get_sale_receipt, create_return
from app.stock_ops import (
    reserve_batch_fefo,
    get_stock_on_hand,
    deduct_stock,
    create_stock_movement,
)
from app.credit_mgmt import (
    check_credit_available,
    charge_credit,
    get_customer_balance,
    reconcile_customer_balance,
)
from app.cashier_ops import (
    open_cashier_shift,
    close_cashier_shift,
    get_current_shift,
    get_cashier_performance,
)
from app.db import get_db


class TestStockOps:
    """Stock operations: FEFO picking, deduction, movement tracking."""

    def test_fefo_picks_earliest_expiry_first(self):
        """Reserve batches picks earliest expiry first (FEFO)."""
        db = get_db()

        # Query demo data: product with multiple batches
        product = db.query_one(
            "SELECT id FROM products LIMIT 1", []
        )
        product_id = product["id"]

        branch = "main"

        # Get current stock
        batches_before = db.query(
            """
            SELECT batch_id, exp_date, amount
            FROM stock_batches
            WHERE product_id = ? AND branch_id = ? AND amount > 0
            ORDER BY exp_date ASC
            """,
            [product_id, branch],
        )

        if len(batches_before) < 2:
            pytest.skip("Not enough batches for FEFO test")

        # Reserve qty for 2+ batches
        qty_needed = sum(b["amount"] for b in batches_before[:2])

        allocated = reserve_batch_fefo(product_id, branch, qty_needed)

        # Verify first allocated batch has earliest exp_date
        assert allocated[0]["batch_id"] == batches_before[0]["batch_id"]
        assert allocated[0]["exp_date"] == batches_before[0]["exp_date"]

    def test_fefo_fails_with_insufficient_stock(self):
        """FEFO raises ValueError if insufficient stock available."""
        db = get_db()

        product = db.query_one("SELECT id FROM products LIMIT 1", [])
        product_id = product["id"]

        # Try to reserve 999999 units (impossible)
        with pytest.raises(ValueError, match="Insufficient stock"):
            reserve_batch_fefo(product_id, "main", 999999)

    def test_stock_movement_creates_record(self):
        """create_stock_movement creates a ledger entry."""
        db = get_db()

        batch = db.query_one("SELECT batch_id FROM stock_batches LIMIT 1", [])
        batch_id = batch["batch_id"]

        movement_id = create_stock_movement(
            batch_id=batch_id,
            movement_type="sale_reserved",
            qty=5,
            branch_id="main",
            reference_id=1,
            reference_type="sale",
        )

        assert movement_id > 0

        # Verify record exists
        mvmt = db.query_one(
            "SELECT movement_type, qty FROM stock_movements WHERE id = ?", [movement_id]
        )
        assert mvmt["movement_type"] == "sale_reserved"
        assert mvmt["qty"] == 5

    def test_get_stock_on_hand(self):
        """get_stock_on_hand sums available (non-expired) stock."""
        db = get_db()

        product = db.query_one("SELECT id FROM products LIMIT 1", [])
        product_id = product["id"]

        qty_main = get_stock_on_hand(product_id, "main")
        qty_elsanta = get_stock_on_hand(product_id, "elsanta")

        # Both should be non-negative
        assert qty_main >= 0
        assert qty_elsanta >= 0


class TestCreditManagement:
    """Customer credit: balance checks, charging, reconciliation."""

    def test_check_credit_available_not_over_limit(self):
        """check_credit_available returns available=True if within limit."""
        db = get_db()

        # Find a customer with credit_limit > 0
        customer = db.query_one(
            "SELECT id FROM customers WHERE credit_limit > 0 LIMIT 1", []
        )
        if not customer:
            pytest.skip("No customer with credit_limit in demo data")

        customer_id = customer["id"]

        # Check a small amount
        result = check_credit_available(customer_id, 100)

        assert isinstance(result, dict)
        assert "available" in result
        assert "credit_limit" in result
        assert "current_balance" in result
        assert result["credit_limit"] > 0

    def test_check_credit_over_limit(self):
        """check_credit_available detects when charging would exceed limit."""
        db = get_db()

        customer = db.query_one(
            "SELECT id, credit_limit FROM customers WHERE credit_limit > 0 LIMIT 1",
            []
        )
        if not customer:
            pytest.skip("No customer with credit_limit")

        customer_id = customer["id"]
        limit = customer["credit_limit"] or 1000

        # Try to charge more than limit
        result = check_credit_available(customer_id, limit + 1000)

        assert result["available"] is False
        assert result["over_limit_by"] > 0

    def test_charge_credit_updates_balance(self):
        """charge_credit increments customer balance."""
        db = get_db()

        customer = db.query_one(
            "SELECT id, current_balance FROM customers WHERE credit_limit > 0 LIMIT 1",
            []
        )
        if not customer:
            pytest.skip("No customer with credit_limit")

        customer_id = customer["id"]
        balance_before = customer["current_balance"] or 0

        # Charge 100
        charge_credit(customer_id, 100, sale_id=1, branch_id="main")

        # Verify balance updated
        customer_after = db.query_one(
            "SELECT current_balance FROM customers WHERE id = ?", [customer_id]
        )
        assert (customer_after["current_balance"] or 0) == balance_before + 100

    def test_get_customer_balance(self):
        """get_customer_balance returns current status."""
        db = get_db()

        customer = db.query_one("SELECT id FROM customers WHERE credit_limit > 0 LIMIT 1", [])
        if not customer:
            pytest.skip("No customer with credit_limit")

        customer_id = customer["id"]

        result = get_customer_balance(customer_id)

        assert result["customer_id"] == customer_id
        assert "credit_limit" in result
        assert "current_balance" in result
        assert "is_over_limit" in result

    def test_reconcile_customer_balance(self):
        """reconcile_customer_balance corrects mismatches."""
        db = get_db()

        customer = db.query_one("SELECT id FROM customers LIMIT 1", [])
        customer_id = customer["id"]

        result = reconcile_customer_balance(customer_id)

        # Should indicate no mismatch (or corrected if one existed)
        assert "action" in result
        assert result["action"] in ("none", "corrected")


class TestCashierOps:
    """Cashier shifts: open, close, performance tracking."""

    def test_open_cashier_shift(self):
        """open_cashier_shift creates a shift record."""
        db = get_db()

        employee = db.query_one("SELECT id FROM employees LIMIT 1", [])
        if not employee:
            pytest.skip("No employees in demo data")

        emp_id = employee["id"]

        shift_id = open_cashier_shift(emp_id, "main", opening_float=500)

        assert shift_id > 0

        # Verify record exists
        shift = db.query_one("SELECT id, opening_float FROM cashier_shifts WHERE id = ?", [shift_id])
        assert shift["opening_float"] == 500

    def test_close_cashier_shift_reconciles(self):
        """close_cashier_shift returns reconciliation details."""
        db = get_db()

        employee = db.query_one("SELECT id FROM employees LIMIT 1", [])
        if not employee:
            pytest.skip("No employees")

        emp_id = employee["id"]

        # Open a shift
        shift_id = open_cashier_shift(emp_id, "main", opening_float=500)

        # Close it
        result = close_cashier_shift(shift_id, closing_float=500)

        assert result["shift_id"] == shift_id
        assert "variance" in result
        assert "variance_pct" in result

    def test_get_current_shift(self):
        """get_current_shift returns active shift or None."""
        db = get_db()

        employee = db.query_one("SELECT id FROM employees LIMIT 1", [])
        if not employee:
            pytest.skip("No employees")

        emp_id = employee["id"]

        # No active shift initially
        shift = get_current_shift(emp_id)
        assert shift is None or shift["id"] > 0  # May have one from prev test

        # Open one
        open_shift_id = open_cashier_shift(emp_id, "main", 500)

        # Now should return it
        shift = get_current_shift(emp_id)
        assert shift is not None
        assert shift["id"] == open_shift_id

    def test_get_cashier_performance(self):
        """get_cashier_performance aggregates sales metrics."""
        db = get_db()

        employee = db.query_one("SELECT id FROM employees LIMIT 1", [])
        if not employee:
            pytest.skip("No employees")

        emp_id = employee["id"]

        today = date.today().isoformat()
        week_ago = date.fromordinal(date.today().toordinal() - 7).isoformat()

        result = get_cashier_performance(emp_id, "main", week_ago, today)

        assert "cashier_id" in result
        assert "bills_count" in result
        assert result["bills_count"] >= 0


class TestPOSSale:
    """POS sale creation: atomicity, FEFO, credit, ledger."""

    def test_create_sale_basic_cash(self):
        """create_sale creates a complete cash sale."""
        db = get_db()

        # Setup
        product = db.query_one("SELECT id FROM products LIMIT 1", [])
        if not product:
            pytest.skip("No products")

        product_id = product["id"]

        employee = db.query_one("SELECT id FROM employees LIMIT 1", [])
        if not employee:
            pytest.skip("No employees")

        emp_id = employee["id"]

        # Open shift
        shift_id = open_cashier_shift(emp_id, "main", 1000)

        # Create sale request
        req = CreateSaleRequest(
            branch_id="main",
            cashier_id=emp_id,
            customer_id=None,
            line_items=[{"product_id": product_id, "qty_sold": 2}],
            payment_method="cash",
        )

        valid, msg = req.validate()
        assert valid, msg

        # Create sale
        result = create_sale(req)

        assert result["status"] == "completed"
        assert result["items_count"] == 1
        assert result["total_amount"] > 0
        assert result["payment_method"] == "cash"

    def test_create_sale_insufficient_stock(self):
        """create_sale fails if insufficient stock."""
        db = get_db()

        product = db.query_one("SELECT id FROM products LIMIT 1", [])
        if not product:
            pytest.skip("No products")

        product_id = product["id"]
        employee = db.query_one("SELECT id FROM employees LIMIT 1", [])
        emp_id = employee["id"]

        open_cashier_shift(emp_id, "main", 1000)

        req = CreateSaleRequest(
            branch_id="main",
            cashier_id=emp_id,
            customer_id=None,
            line_items=[{"product_id": product_id, "qty_sold": 999999}],
            payment_method="cash",
        )

        with pytest.raises(ValueError, match="Insufficient stock"):
            create_sale(req)

    def test_create_sale_credit_over_limit(self):
        """create_sale rejects if customer credit would be exceeded."""
        db = get_db()

        # Find customer with low credit limit
        customer = db.query_one(
            "SELECT id, credit_limit FROM customers WHERE credit_limit > 0 LIMIT 1", []
        )
        if not customer:
            pytest.skip("No customer with credit_limit")

        customer_id = customer["id"]
        limit = (customer["credit_limit"] or 1000) + 1

        product = db.query_one("SELECT id, price FROM products WHERE price > 0 LIMIT 1", [])
        if not product:
            pytest.skip("No products with price")

        product_id = product["id"]
        price = product["price"]

        # Calculate qty that will exceed credit
        qty = int(limit / price) + 1

        employee = db.query_one("SELECT id FROM employees LIMIT 1", [])
        emp_id = employee["id"]

        open_cashier_shift(emp_id, "main", 1000)

        req = CreateSaleRequest(
            branch_id="main",
            cashier_id=emp_id,
            customer_id=customer_id,
            line_items=[{"product_id": product_id, "qty_sold": qty}],
            payment_method="credit",
            credit_amount=qty * price,
        )

        # Should fail
        with pytest.raises(ValueError, match="over credit limit"):
            create_sale(req)

    def test_get_sale_receipt(self):
        """get_sale_receipt retrieves a completed sale."""
        db = get_db()

        sale = db.query_one("SELECT id FROM sales LIMIT 1", [])
        if not sale:
            pytest.skip("No sales in demo data")

        sale_id = sale["id"]

        receipt = get_sale_receipt(sale_id)

        assert receipt["sale_id"] == sale_id
        assert "items" in receipt
        assert "total_amount" in receipt

    def test_create_return(self):
        """create_return reverses a prior sale."""
        db = get_db()

        sale = db.query_one("SELECT id FROM sales WHERE is_return IS NULL LIMIT 1", [])
        if not sale:
            pytest.skip("No sales to return")

        sale_id = sale["id"]

        result = create_return(
            original_sale_id=sale_id,
            return_lines=[],
            reason="customer request",
            approver_id=1,
        )

        assert result["original_sale_id"] == sale_id
        assert result["status"] == "completed"
        assert result["return_id"] > 0


class TestPOSValidation:
    """POS request validation."""

    def test_validate_invalid_branch(self):
        """Validation rejects invalid branch."""
        req = CreateSaleRequest(
            branch_id="invalid_branch",
            cashier_id=1,
            customer_id=None,
            line_items=[{"product_id": 1, "qty_sold": 1}],
            payment_method="cash",
        )

        valid, msg = req.validate()
        assert not valid
        assert "branch" in msg.lower()

    def test_validate_no_items(self):
        """Validation rejects empty sale."""
        req = CreateSaleRequest(
            branch_id="main",
            cashier_id=1,
            customer_id=None,
            line_items=[],
            payment_method="cash",
        )

        valid, msg = req.validate()
        assert not valid
        assert "items" in msg.lower()

    def test_validate_credit_requires_customer(self):
        """Validation rejects credit sale without customer."""
        req = CreateSaleRequest(
            branch_id="main",
            cashier_id=1,
            customer_id=None,
            line_items=[{"product_id": 1, "qty_sold": 1}],
            payment_method="credit",
            credit_amount=100,
        )

        valid, msg = req.validate()
        assert not valid
        assert "customer" in msg.lower()
