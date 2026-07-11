"""ProCare ORM models — the OWN clean schema.

A faithful SQLAlchemy mapping of ``sql/procare-schema.sql``: real foreign keys,
NOT-NULL operational dates, ``amount >= 0`` checks, ``branch_id`` on every
operational row, returns unified onto the sales tables via ``is_return``. Money
is modelled as ``Numeric`` so totals are exact.

These run on SQLite in dev and SQL Server in production unchanged.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Reusable column types ------------------------------------------------------
Money = Numeric(18, 3)
Qty = Numeric(18, 3)


class Branch(Base):
    __tablename__ = "branches"

    branch_id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name_ar: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str] = mapped_column(String(100))
    is_pilot: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Company(Base):
    __tablename__ = "companies"

    company_id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(150))
    name_en: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class ProductGroup(Base):
    __tablename__ = "product_groups"

    group_id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Unit(Base):
    __tablename__ = "units"

    unit_id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(50))
    name_en: Mapped[str | None] = mapped_column(String(50), nullable=True)


class CustomerClass(Base):
    __tablename__ = "customer_classes"

    customer_class_id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(50))
    name_en: Mapped[str | None] = mapped_column(String(50), nullable=True)


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fast_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name_ar: Mapped[str] = mapped_column(String(150))
    name_en: Mapped[str | None] = mapped_column(String(150), nullable=True)
    scientific_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    titan_drug_id: Mapped[int | None] = mapped_column(nullable=True)

    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.company_id"), nullable=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("product_groups.group_id"), nullable=True)
    unit1_id: Mapped[int | None] = mapped_column(ForeignKey("units.unit_id"), nullable=True)

    is_controlled: Mapped[bool] = mapped_column(default=False)
    has_expiry: Mapped[bool] = mapped_column(default=True)
    allow_sale_zero: Mapped[bool] = mapped_column(default=False)

    sell_price: Mapped[float] = mapped_column(Money, default=0)
    buy_price: Mapped[float] = mapped_column(Money, default=0)
    tax_price: Mapped[float] = mapped_column(Money, default=0)
    wholesale_price: Mapped[float | None] = mapped_column(Money, nullable=True)

    min_stock: Mapped[float] = mapped_column(Qty, default=0)
    # Units (وحدات الصنف): the big unit (علبة) subdivides into ``unit_factor``
    # small units (شريط/أمبول/كبسولة). Stock amounts are ALWAYS in big units;
    # selling one small unit deducts 1/unit_factor of a big unit.
    unit_big: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit_small: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit_factor: Mapped[float] = mapped_column(Qty, default=1)
    # Merchandising: physical shelf/place code (eStock's Sites — 314 locations),
    # e.g. "A3", "رف الأطفال", "counter fridge".
    shelf_location: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("sell_price >= 0 AND buy_price >= 0 AND tax_price >= 0", name="CK_products_prices"),
        Index("IX_products_name_ar", "name_ar"),
        Index("IX_products_scientific", "scientific_name"),
    )


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    customer_class_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_classes.customer_class_id"), nullable=True
    )
    credit_limit: Mapped[float] = mapped_column(Money, default=0)
    current_balance: Mapped[float] = mapped_column(Money, default=0)
    opening_balance: Mapped[float] = mapped_column(Money, default=0)
    # Loyalty programme: whole points, earned on sales, spent via redemption.
    loyalty_points: Mapped[float] = mapped_column(Qty, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (Index("IX_customers_name", "name_ar"),)


class Vendor(Base):
    __tablename__ = "vendors"

    vendor_id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    credit_limit: Mapped[float] = mapped_column(Money, default=0)
    current_balance: Mapped[float] = mapped_column(Money, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    job_id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Employee(Base):
    __tablename__ = "employees"

    employee_id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Login role for the ProCare app itself (separate from eStock job titles):
    # "ceo" (full access), "manager" (branch-scoped, no salaries), "assistant"
    # (POS/inventory only). Defaults to the most restrictive tier.
    role: Mapped[str] = mapped_column(String(20), default="assistant")
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.job_id"), nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.branch_id"), nullable=True)
    basic_salary: Mapped[float] = mapped_column(Money, default=0)

    max_disc_per: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    can_see_buy_price: Mapped[bool] = mapped_column(default=False)
    can_edit_sell_price: Mapped[bool] = mapped_column(default=False)
    can_sale_credit: Mapped[bool] = mapped_column(default=False)
    can_return: Mapped[bool] = mapped_column(default=False)
    can_void: Mapped[bool] = mapped_column(default=False)
    can_change_shift: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # WhatsApp number for the self-service password reset (and future alerts).
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Pending reset code (hash only — the code itself is never stored) with a
    # short expiry and an attempt counter to stop brute-forcing.
    reset_code_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reset_code_expires: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reset_attempts: Mapped[int] = mapped_column(default=0)


class StockBatch(Base):
    __tablename__ = "stock_batches"

    batch_id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.vendor_id"), nullable=True)
    source_counter: Mapped[int | None] = mapped_column(nullable=True)
    amount: Mapped[float] = mapped_column(Qty, default=0)
    buy_price: Mapped[float] = mapped_column(Money, default=0)
    sell_price: Mapped[float] = mapped_column(Money, default=0)
    tax_price: Mapped[float] = mapped_column(Money, default=0)
    exp_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    product: Mapped[Product] = relationship()

    __table_args__ = (
        CheckConstraint("amount >= 0", name="CK_stock_amount"),
        Index("IX_stock_product_branch", "product_id", "branch_id"),
        Index("IX_stock_expiry", "exp_date", "branch_id"),
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    movement_id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("stock_batches.batch_id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    delta: Mapped[float] = mapped_column(Qty)
    reason: Mapped[str] = mapped_column(String(20))
    ref_id: Mapped[int | None] = mapped_column(nullable=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint(
            "reason IN ('sale','purchase','transfer_out','transfer_in','adjust','writeoff','opening','return')",
            name="CK_movements_reason",
        ),
        Index("IX_movements_ref", "reason", "ref_id"),
    )


class Sale(Base):
    __tablename__ = "sales"

    sale_id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.customer_id"), nullable=True)
    cashier_id: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    sale_date: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    total_gross: Mapped[float] = mapped_column(Money, default=0)
    total_discount: Mapped[float] = mapped_column(Money, default=0)
    total_net: Mapped[float] = mapped_column(Money, default=0)
    cash_paid: Mapped[float] = mapped_column(Money, default=0)
    card_paid: Mapped[float] = mapped_column(Money, default=0)
    change_given: Mapped[float] = mapped_column(Money, default=0)
    is_return: Mapped[bool] = mapped_column(default=False)
    is_credit: Mapped[bool] = mapped_column(default=False)
    # Return invoices point back at the sale they reverse (eStock's
    # Back_sales_header -> Sales_header link).
    original_sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.sale_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    lines: Mapped[list["SaleLine"]] = relationship(back_populates="sale", cascade="all, delete-orphan")
    customer: Mapped[Customer | None] = relationship()

    __table_args__ = (
        # No totals CHECK: the eStock mirror must carry legacy correction rows
        # verbatim (a handful of sales have small negative totals). Non-negative
        # totals for ProCare-created sales are enforced in services/pos.py.
        Index("IX_sales_date", "sale_date"),
        Index("IX_sales_branch_date", "branch_id", "sale_date"),
    )


class SaleLine(Base):
    __tablename__ = "sale_lines"

    line_id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.sale_id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("stock_batches.batch_id"), nullable=True)
    amount: Mapped[float] = mapped_column(Qty)
    sell_price: Mapped[float] = mapped_column(Money)
    buy_price: Mapped[float] = mapped_column(Money)
    disc_money: Mapped[float] = mapped_column(Money, default=0)
    total_sell: Mapped[float] = mapped_column(Money)
    is_return: Mapped[bool] = mapped_column(default=False)

    sale: Mapped[Sale] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()

    __table_args__ = (
        # >= 0 (not > 0): legacy eStock lines include zero-amount bonus/free
        # items. New POS lines are validated > 0 in services/pos.py.
        CheckConstraint("amount >= 0", name="CK_saleline_amount"),
        Index("IX_sale_lines_sale", "sale_id"),
        Index("IX_sale_lines_product", "product_id"),
    )


class Purchase(Base):
    __tablename__ = "purchases"

    purchase_id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.vendor_id"))
    bill_date: Mapped[date] = mapped_column(Date)
    bill_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_gross: Mapped[float] = mapped_column(Money, default=0)
    total_discount: Mapped[float] = mapped_column(Money, default=0)
    total_tax: Mapped[float] = mapped_column(Money, default=0)
    is_return: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    lines: Mapped[list["PurchaseLine"]] = relationship(back_populates="purchase", cascade="all, delete-orphan")


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"

    line_id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.purchase_id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("stock_batches.batch_id"), nullable=True)
    amount: Mapped[float] = mapped_column(Qty)
    bonus: Mapped[float] = mapped_column(Qty, default=0)
    buy_price: Mapped[float] = mapped_column(Money)
    sell_price: Mapped[float] = mapped_column(Money)
    exp_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    purchase: Mapped[Purchase] = relationship(back_populates="lines")


class StockTransfer(Base):
    __tablename__ = "stock_transfers"

    transfer_id: Mapped[int] = mapped_column(primary_key=True)
    from_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    to_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    status: Mapped[str] = mapped_column(String(20), default="requested")
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    lines: Mapped[list["StockTransferLine"]] = relationship(
        back_populates="transfer", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("status IN ('requested','in_transit','received','cancelled')", name="CK_transfer_status"),
        CheckConstraint("from_branch_id <> to_branch_id", name="CK_transfer_branches"),
    )


class StockTransferLine(Base):
    __tablename__ = "stock_transfer_lines"

    line_id: Mapped[int] = mapped_column(primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("stock_transfers.transfer_id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    from_batch_id: Mapped[int | None] = mapped_column(ForeignKey("stock_batches.batch_id"), nullable=True)
    to_batch_id: Mapped[int | None] = mapped_column(ForeignKey("stock_batches.batch_id"), nullable=True)
    amount: Mapped[float] = mapped_column(Qty)
    buy_price: Mapped[float] = mapped_column(Money, default=0)
    exp_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    transfer: Mapped[StockTransfer] = relationship(back_populates="lines")

    __table_args__ = (CheckConstraint("amount > 0", name="CK_transferline_amount"),)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    entry_id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    entry_date: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    account_type: Mapped[str] = mapped_column(String(20))
    account_ref: Mapped[int | None] = mapped_column(nullable=True)
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(nullable=True)
    debit: Mapped[float] = mapped_column(Money, default=0)
    credit: Mapped[float] = mapped_column(Money, default=0)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint(
            "account_type IN ('customer','vendor','cash','bank','branch','general')", name="CK_ledger_account"
        ),
        CheckConstraint("debit >= 0 AND credit >= 0", name="CK_ledger_amounts"),
        Index("IX_ledger_branch_date", "branch_id", "entry_date"),
        Index("IX_ledger_account", "account_type", "account_ref"),
    )


class PurchaseOrderDraft(Base):
    """Smart-reorder output. Drafts only — a human approves before sending.

    Mirrors the spec's ``auto_purchase_order`` (draft → manager approval).
    """

    __tablename__ = "purchase_order_drafts"

    draft_id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.vendor_id"), nullable=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    on_hand: Mapped[float] = mapped_column(Qty, default=0)
    suggested_qty: Mapped[float] = mapped_column(Qty, default=0)
    reason: Mapped[str] = mapped_column(String(40), default="below_min")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/approved/rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class EmployeeTask(Base):
    """Daily task assignments. CEO/managers create and assign; staff mark done.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "employee_tasks"

    task_id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.branch_id"), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/done
    # Priority (high/normal/low) drives ordering + colour; category groups the
    # daily plan (opening/closing/inventory/ordering/cleaning/approval/general).
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    category: Mapped[str] = mapped_column(String(20), default="general")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('pending','done')", name="CK_task_status"),
        Index("IX_tasks_assignee_status", "assignee_id", "status"),
        Index("IX_tasks_branch_due", "branch_id", "due_date"),
    )


class FootfallEvent(Base):
    """One person crossing the door line, pushed by the NVR / camera counter
    (``POST /api/footfall/event``). Powers visitors-vs-buyers conversion."""

    __tablename__ = "footfall_events"

    event_id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    ts: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    direction: Mapped[str] = mapped_column(String(3), default="in")  # in/out
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)  # NVR channel etc.

    __table_args__ = (
        CheckConstraint("direction IN ('in','out')", name="CK_footfall_direction"),
        Index("IX_footfall_branch_ts", "branch_id", "ts"),
    )


class CashShift(Base):
    """Cashier shift (eStock's Cash_disk_close — 1,647 closures): opened with a
    float, closed with a counted amount; expected cash is computed from the
    cash sales minus cash refunds recorded during the shift."""

    __tablename__ = "cash_shifts"

    shift_id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    cashier_id: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opening_float: Mapped[float] = mapped_column(Money, default=0)
    counted_cash: Mapped[float | None] = mapped_column(Money, nullable=True)
    expected_cash: Mapped[float | None] = mapped_column(Money, nullable=True)
    variance: Mapped[float | None] = mapped_column(Money, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open/closed

    __table_args__ = (
        CheckConstraint("status IN ('open','closed')", name="CK_shift_status"),
        Index("IX_shifts_branch_status", "branch_id", "status"),
    )


class EmployeeGoal(Base):
    """PMP / development-plan item per employee: a performance or training
    goal with a target date, tracked by the CEO/manager in reviews.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "employee_goals"

    goal_id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.employee_id"))
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    category: Mapped[str] = mapped_column(String(20), default="performance")
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("category IN ('performance','training','behavior')", name="CK_goal_category"),
        CheckConstraint("status IN ('active','achieved','dropped')", name="CK_goal_status"),
        Index("IX_goals_employee_status", "employee_id", "status"),
    )


class LoyaltyTransaction(Base):
    """One loyalty-points movement per customer: earned on a sale, clawed back
    on a return, spent on redemption, or a manual adjustment. The customer's
    ``loyalty_points`` column is the running balance; this is the audit trail.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "loyalty_transactions"

    loyalty_tx_id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.customer_id"))
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales.sale_id"), nullable=True)
    points_delta: Mapped[float] = mapped_column(Qty)  # + earn, - redeem/clawback
    kind: Mapped[str] = mapped_column(String(20))  # earn/redeem/clawback/adjust
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint("kind IN ('earn','redeem','clawback','adjust')", name="CK_loyalty_kind"),
        Index("IX_loyalty_customer", "customer_id", "created_at"),
    )


class Prescription(Base):
    """One captured doctor's prescription (photo taken on a phone at the
    counter). Gemini vision extracts the doctor + drug lines when a key is
    configured; otherwise staff type them in. Powers the doctor-prescribing-
    habits report for the pharmacy's area.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "prescriptions"

    prescription_id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.branch_id"), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.customer_id"), nullable=True)
    doctor_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    doctor_specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    clinic: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # JSON array of {name, dose, frequency, duration} the reader extracted.
    drugs_json: Mapped[str] = mapped_column(String(4000), default="[]")
    raw_text: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # gemini/manual
    # Workflow: captured (just read) -> reviewed (staff confirmed + matched to
    # catalogue products) -> dispensed (turned into a sale).
    status: Mapped[str] = mapped_column(String(20), default="captured")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    captured_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint("source IN ('gemini','manual')", name="CK_rx_source"),
        Index("IX_rx_doctor", "doctor_name"),
        Index("IX_rx_created", "created_at"),
    )


class ShortageItem(Base):
    """The stock-shortage sheet (eStock's Shortcoming — 5,754 rows): staff add
    what a customer asked for and we didn't have; purchasing works the list.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "shortage_items"

    shortage_id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.product_id"), nullable=True)
    # Free-text when the product isn't in the catalogue yet.
    product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    qty_requested: Mapped[float] = mapped_column(Qty, default=1)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open/ordered/received/cancelled
    reported_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('open','ordered','received','cancelled')", name="CK_shortage_status"),
        Index("IX_shortage_branch_status", "branch_id", "status"),
    )


class TreasuryTransfer(Base):
    """Cash moved between branch treasuries (eStock's Branch_money_order /
    Branch_money_convert — 1,102/1,098 rows). The ledger carries the two
    balanced cash entries; this row is the transfer document.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "treasury_transfers"

    transfer_id: Mapped[int] = mapped_column(primary_key=True)
    from_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    to_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    amount: Mapped[float] = mapped_column(Money)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint("amount > 0", name="CK_ttransfer_amount"),
        CheckConstraint("from_branch_id <> to_branch_id", name="CK_ttransfer_branches"),
    )


class Campaign(Base):
    """A WhatsApp marketing campaign: one message sent to a filtered audience
    of customers (all / debtors / top spenders / inactive). When the WhatsApp
    Cloud API is configured the send is automatic; otherwise the campaign
    yields per-customer click-to-chat links the staff work through.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "campaigns"

    campaign_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(String(2000))
    audience: Mapped[str] = mapped_column(String(20), default="all")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/sent
    recipient_count: Mapped[int] = mapped_column(default=0)
    sent_count: Mapped[int] = mapped_column(default=0)  # via Cloud API only
    created_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("audience IN ('all','debtors','top','inactive')", name="CK_campaign_audience"),
        CheckConstraint("status IN ('draft','sent')", name="CK_campaign_status"),
    )


class StockCount(Base):
    """Stocktaking session (الجرد) — eStock-style physical inventory count.

    ``full`` counts every live batch at the branch; ``periodic`` (الجرد الدوري)
    is the recurring spot-check of a subset (top movers / a shelf); ``partial``
    is an ad-hoc count. Lines snapshot the expected quantity at creation;
    posting applies counted quantities as adjustments (ضبط الأصناف) through the
    normal stock-movement audit trail. New table — ``create_all`` adds it
    automatically on existing databases.
    """

    __tablename__ = "stock_counts"

    count_id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    count_type: Mapped[str] = mapped_column(String(10), default="full")  # full/periodic/partial
    status: Mapped[str] = mapped_column(String(10), default="open")  # open/posted/cancelled
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    posted_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("count_type IN ('full','periodic','partial')", name="CK_count_type"),
        CheckConstraint("status IN ('open','posted','cancelled')", name="CK_count_status"),
    )


class StockCountLine(Base):
    """One batch inside a stocktaking session: expected (snapshot) vs counted
    (physical). ``posted_delta`` records the adjustment actually applied when
    the session was posted (counted minus the batch's live amount at post time,
    which may differ from the snapshot if sales happened during the count).

    ``batch_id``/``product_id`` are deliberately NOT foreign keys: the eStock
    mirror wipes and reloads batches/products every sync cycle, and جرد history
    must survive that (it's pharmacy history eStock knows nothing about). The
    count sheet outer-joins them and degrades gracefully when a reload removed
    a row; ``name_ar`` snapshots the product name so posted reports stay
    readable forever."""

    __tablename__ = "stock_count_lines"

    line_id: Mapped[int] = mapped_column(primary_key=True)
    count_id: Mapped[int] = mapped_column(ForeignKey("stock_counts.count_id"))
    batch_id: Mapped[int] = mapped_column()
    product_id: Mapped[int] = mapped_column()
    name_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expected_qty: Mapped[float] = mapped_column(Qty, default=0)
    counted_qty: Mapped[float | None] = mapped_column(Qty, nullable=True)
    posted_delta: Mapped[float | None] = mapped_column(Qty, nullable=True)

    __table_args__ = (
        Index("IX_count_lines_count", "count_id"),
        Index("IX_count_lines_batch", "batch_id"),
    )
