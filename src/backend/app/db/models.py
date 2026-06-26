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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    lines: Mapped[list["SaleLine"]] = relationship(back_populates="sale", cascade="all, delete-orphan")
    customer: Mapped[Customer | None] = relationship()

    __table_args__ = (
        CheckConstraint("total_gross >= 0 AND total_net >= 0 AND total_discount >= 0", name="CK_sales_totals"),
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
        CheckConstraint("amount > 0", name="CK_saleline_amount"),
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
