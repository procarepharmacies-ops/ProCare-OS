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
    Text,
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
    # How that Titan link was resolved (tools/titan_extract.py): exact_name /
    # name_no_pack / name_tokens, with its confidence score. NULL = unmapped.
    titan_match_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    titan_match_score: Mapped[int | None] = mapped_column(nullable=True)

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
    # Classification (التصنيف): pharmaceutical form (أقراص/شراب/حقن/كريم…),
    # OTC vs prescription, and free-text uses/indications (الاستخدامات) — the
    # filter axes of the items screen alongside scientific name and shelf place.
    dosage_form: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_otc: Mapped[bool] = mapped_column(default=False)
    uses: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Merchandising: physical shelf/place code (eStock's Sites — 314 locations),
    # e.g. "A3", "رف الأطفال", "counter fridge".
    shelf_location: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Incentive points earned per unit sold (for OTC incentive list).
    incentive_points: Mapped[float] = mapped_column(Qty, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("sell_price >= 0 AND buy_price >= 0 AND tax_price >= 0", name="CK_products_prices"),
        Index("IX_products_name_ar", "name_ar"),
        Index("IX_products_scientific", "scientific_name"),
    )


class TitanDrug(Base):
    """Read-only mirror of the Titan / Drug-Eye drug master (docs/03).

    Loaded by ``tools/titan_extract.py`` from ``D:\\Labirdo\\TITAN.W1``'s
    ``tar.phy`` fixed-width file. ``titan_drug_id`` is the 1-based record slot
    in that file — Titan appends, so slots are stable between reloads.
    ``products.titan_drug_id`` points here once the mapping job resolves it.
    """

    __tablename__ = "titan_drugs"

    titan_drug_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    # Nullable: the TITAN.349 build carries drugs with an Arabic name only.
    name_en: Mapped[str | None] = mapped_column(String(60), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(60), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scientific_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Derived in tools/titan_extract.py — Titan stores no such flags directly.
    # origin: 'local' | 'import' | NULL (from manufacturer nationality).
    origin: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # is_medicine: from the therapeutic category (NULL = undetermined).
    is_medicine: Mapped[bool | None] = mapped_column(nullable=True)
    # Pre-computed normalised join keys (see tools/titan_extract.py `norm`).
    name_norm: Mapped[str] = mapped_column(String(80))
    sci_norm: Mapped[str | None] = mapped_column(String(80), nullable=True)
    loaded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        Index("IX_titan_drugs_name_norm", "name_norm"),
        Index("IX_titan_drugs_sci_norm", "sci_norm"),
    )


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    customer_class_id: Mapped[int | None] = mapped_column(
        ForeignKey("customer_classes.customer_class_id"), nullable=True
    )
    credit_limit: Mapped[float] = mapped_column(Money, default=0)
    current_balance: Mapped[float] = mapped_column(Money, default=0)
    opening_balance: Mapped[float] = mapped_column(Money, default=0)
    # Loyalty programme: whole points, earned on sales, spent via redemption.
    loyalty_points: Mapped[float] = mapped_column(Qty, default=0)
    # Phase 3: Loyalty tiers (silver/gold/platinum) computed nightly from 12-month spend.
    tier: Mapped[str] = mapped_column(String(20), default="silver")
    tier_spend_12m: Mapped[float] = mapped_column(Money, default=0)
    # CRM: Birthday (optional, captured at POS) + WhatsApp opt-out.
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    wa_opt_out: Mapped[bool] = mapped_column(default=False)
    # RFM segmentation (vip/regular/at_risk/dormant) computed daily.
    rfm_segment: Mapped[str] = mapped_column(String(20), default="regular")
    last_purchase_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
        Index("IX_movements_batch", "batch_id"),  # FK-check index (batch wipes)
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
        # FK-check index for the self-reference: deleting sales must not scan
        # the whole table per row to prove no return points at it.
        Index("IX_sales_original", "original_sale_id"),
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
        # FK-check index: without it, every stock_batches DELETE full-scans
        # this table per deleted row (35K batches x 190K lines took ~500s on
        # the dev SQLite before this index; 0.1s after).
        Index("IX_sale_lines_batch", "batch_id"),
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

    __table_args__ = (
        # FK-check indexes: purchase wipes delete by purchase_id; batch wipes
        # FK-check batch_id per deleted stock_batches row.
        Index("IX_purchase_lines_purchase", "purchase_id"),
        Index("IX_purchase_lines_batch", "batch_id"),
    )


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

    __table_args__ = (
        CheckConstraint("amount > 0", name="CK_transferline_amount"),
        # FK-check indexes (batch/transfer wipes).
        Index("IX_transfer_lines_transfer", "transfer_id"),
        Index("IX_transfer_lines_from", "from_batch_id"),
        Index("IX_transfer_lines_to", "to_batch_id"),
    )


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
    # Named adjustment reason (eStock Tuning_accounts parity) — only set on
    # manual adjustment entries (ref_type='adjust'); NULL for machine postings.
    reason_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
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
    assigned_agent: Mapped[str | None] = mapped_column(String(20), nullable=True)  # hermes|claude|gemini|antigravity|me
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
        Index("IX_loyalty_sale", "sale_id"),  # FK-check index (sale wipes)
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


class SocialPost(Base):
    """Social media content calendar post (فيسبوك/انستغرام/ستاتس واتس).

    Tracks content drafts, approvals, and publishing to multiple channels
    with bilingual captions and media refs. Phase 4: marketing studio.
    """

    __tablename__ = "social_posts"

    post_id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(20))  # fb / ig / wa-status
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    body_ar: Mapped[str] = mapped_column(String(2000))
    body_en: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    image_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)  # URL or base64 ref
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/approved/published
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    promo_code: Mapped[str | None] = mapped_column(String(50), nullable=True)  # link to promotion
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("channel IN ('fb','ig','wa-status','tiktok','linkedin')", name="CK_social_channel"),
        CheckConstraint("status IN ('draft','approved','published','scheduled')", name="CK_social_status"),
        Index("IX_social_posts_channel_date", "channel", "scheduled_at"),
        Index("IX_social_posts_promo", "promo_code"),
    )


class PromoCode(Base):
    """Discount promotion code (كود الخصم) — redeemable at POS.

    Tracks code, discount amount/percentage, validity window, usage limits.
    Phase 4: campaign→sales ROI tracking.
    """

    __tablename__ = "promo_codes"

    promo_code_id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    description_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    discount_type: Mapped[str] = mapped_column(String(10))  # percentage / fixed
    discount_value: Mapped[float] = mapped_column(Money)  # % or EGP amount
    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_until: Mapped[datetime] = mapped_column(DateTime)
    max_uses: Mapped[int | None] = mapped_column(nullable=True)  # NULL = unlimited
    current_uses: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("discount_type IN ('percentage','fixed')", name="CK_promo_type"),
        CheckConstraint("discount_value > 0", name="CK_promo_value"),
        CheckConstraint("current_uses >= 0", name="CK_promo_uses"),
        Index("IX_promo_codes_code", "code"),
        Index("IX_promo_codes_valid", "valid_from", "valid_until"),
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


class AgentRun(Base):
    """Audit trail for AI agent dispatches (absorbed from AgenticOS v2.0).

    Every agent task — whether dry-run, blocked, or executed — is recorded
    here for compliance and debugging. Linked optionally to an employee_task
    via ``task_id``.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(12), unique=True)
    agent: Mapped[str] = mapped_column(String(20))
    task: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(12))  # running|done|error|blocked
    output: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True, default=0)
    task_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('running','done','error','blocked')", name="CK_agent_run_status"),
        Index("IX_agent_runs_agent", "agent"),
        Index("IX_agent_runs_created", "created_at"),
    )


class SyncState(Base):
    """Per-source sync bookkeeping for the eStock mirror.

    ``full_synced_at`` records that this source completed a FULL branch load —
    the gate that lets later cycles run the fast incremental window instead of
    re-pulling all history. Kept in the database (not process memory) so a
    backend restart never silently re-triggers a multi-minute WAN full pull,
    and cleared naturally whenever the database is reset.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "sync_state"

    source_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    full_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_cycle_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)


class AuthEvent(Base):
    """Security audit trail: every login attempt, password reset and password
    change, with outcome. ``employee_id`` is NULL for failed attempts against
    unknown usernames (the attempted username is still recorded).

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "auth_events"

    event_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    event: Mapped[str] = mapped_column(String(20))  # login_ok/login_fail/reset_request/reset_ok/password_change
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint(
            "event IN ('login_ok','login_fail','reset_request','reset_ok','password_change')",
            name="CK_auth_event_kind",
        ),
        Index("IX_auth_events_created", "created_at"),
        Index("IX_auth_events_username", "username"),
    )


class ProductAffinity(Base):
    """Co-purchase affinity matrix for POS upsell/cross-sell suggestions.

    Nightly scheduler job computes lift (P(B|A) / P(B)) and support
    (% of all baskets containing both) from 90-day sales history. Ranked by lift.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "product_affinity"

    affinity_id: Mapped[int] = mapped_column(primary_key=True)
    product_a_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    product_b_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.branch_id"), nullable=True)
    lift: Mapped[float] = mapped_column(default=1.0)
    support: Mapped[float] = mapped_column(default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("lift > 0", name="CK_affinity_lift"),
        CheckConstraint("support >= 0 AND support <= 1", name="CK_affinity_support"),
        Index("IX_affinity_product_a", "product_a_id"),
        Index("IX_affinity_product_b", "product_b_id"),
        Index("IX_affinity_branch", "branch_id"),
    )


class IncentiveLedger(Base):
    """Incentive points earned/clawed-back per sale line by cashier.

    POS creates entries when incentivized items (``products.incentive_points > 0``)
    are sold; returns auto-claw back via negative entries. Monthly leaderboard
    aggregates per employee by summing over a calendar month.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "incentive_ledger"

    entry_id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.employee_id"))
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.sale_id"))
    sale_line_id: Mapped[int] = mapped_column(ForeignKey("sale_lines.line_id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    points: Mapped[float] = mapped_column(Qty)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        Index("IX_incentive_employee_created", "employee_id", "created_at"),
        Index("IX_incentive_sale", "sale_id"),
        Index("IX_incentive_branch_created", "branch_id", "created_at"),
    )


class Forecast(Base):
    """Nightly pre-computed demand forecasts per product×branch.

    Cached for <500ms dashboard queries. Generated by the scheduler via
    services/forecast.py:forecast_demand(). Holt-style exponential smoothing
    with day-of-week seasonality. Safe to re-run (idempotent).
    """

    __tablename__ = "forecasts"

    forecast_id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    forecast_date: Mapped[date] = mapped_column(Date)
    forecast_horizon: Mapped[int] = mapped_column(default=30)
    daily_avg: Mapped[float] = mapped_column(Qty, default=0.0)
    trend_per_day: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0)
    seasonality_factor: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0)
    projected_demand: Mapped[float] = mapped_column(Qty, default=0.0)
    stockout_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    days_of_cover: Mapped[float] = mapped_column(Numeric(10, 1), default=0.0)
    method: Mapped[str] = mapped_column(String(50), default="exp_smoothing")
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint("product_id", "branch_id", "forecast_date", name="UQ_forecast_uniq"),
        Index("IX_forecast_product_branch_date", "product_id", "branch_id", "forecast_date"),
        Index("IX_forecast_stockout_date", "stockout_date"),
    )


class DecisionCard(Base):
    """Daily briefing items: actionable insights for manager review.

    Created nightly by the scheduler from forecast/inventory state.
    Manager can approve action (create PO, transfer, etc.) or dismiss.
    Auto-archives after 7 days without action. Audit trail for all actions.
    """

    __tablename__ = "decision_cards"

    card_id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.branch_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    card_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )
    severity: Mapped[str] = mapped_column(String(20), default="info")
    title_ar: Mapped[str] = mapped_column(String(256))
    title_en: Mapped[str] = mapped_column(String(256))
    body_ar: Mapped[str] = mapped_column(Text)
    body_en: Mapped[str] = mapped_column(Text)
    action_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ref_product_id: Mapped[int | None] = mapped_column(ForeignKey("products.product_id"), nullable=True)
    ref_purchase_id: Mapped[int | None] = mapped_column(ForeignKey("purchases.purchase_id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    actioned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actioned_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)

    __table_args__ = (
        CheckConstraint("card_type IN ('stockout_risk', 'below_min', 'expiry_warning', 'overstocked', 'out_of_bounds')", name="CK_card_type"),
        CheckConstraint("severity IN ('critical', 'warning', 'info')", name="CK_card_severity"),
        CheckConstraint("status IN ('open', 'dismissed', 'actioned', 'archived')", name="CK_card_status"),
        Index("IX_card_branch_created", "branch_id", "created_at"),
        Index("IX_card_status", "status"),
        Index("IX_card_severity", "severity"),
    )


class CommissionRun(Base):
    """A posted sales-rep commission payout batch (حاسبة عمولة مندوب البيع).

    Mirrors eStock's rep-commission workflow: pick a period + a percentage,
    the system totals each rep's net sales (``sales.cashier_id``) and pays
    ``sales_value × rate``. A run is only written when the manager *posts* the
    preview, so it doubles as the auditable payout record. Voiding keeps the
    row (status='void') for the audit trail rather than deleting it.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "commission_runs"

    run_id: Mapped[int] = mapped_column(primary_key=True)
    # NULL = consolidated across all branches (matches branch_filter's None).
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.branch_id"), nullable=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    # Fallback rate applied to reps without a per-rep override, in percent.
    default_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    total_sales: Mapped[float] = mapped_column(Money, default=0)
    total_commission: Mapped[float] = mapped_column(Money, default=0)
    status: Mapped[str] = mapped_column(String(20), default="posted")
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    posted_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    lines: Mapped[list["CommissionRunLine"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("status IN ('posted', 'void')", name="CK_commission_status"),
        CheckConstraint("period_end >= period_start", name="CK_commission_period"),
        Index("IX_commission_branch_period", "branch_id", "period_start", "period_end"),
        Index("IX_commission_status", "status"),
    )


class CommissionRunLine(Base):
    """One sales-rep's line within a posted commission run — a snapshot of the
    net sales value, effective rate, and the resulting commission at post time.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "commission_run_lines"

    line_id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("commission_runs.run_id"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.employee_id"))
    sales_value: Mapped[float] = mapped_column(Money, default=0)
    bills_count: Mapped[int] = mapped_column(default=0)
    rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    commission: Mapped[float] = mapped_column(Money, default=0)

    run: Mapped[CommissionRun] = relationship(back_populates="lines")

    __table_args__ = (
        Index("IX_commission_line_run", "run_id"),
        Index("IX_commission_line_employee", "employee_id"),
    )




class NotificationDismissal(Base):
    """Dismissed-notification log for the notification center (News_bar parity).

    The notification feed is *computed live* from operational state (expiring
    batches, low stock, open shortages), so there is no event row to delete —
    instead each live event has a stable ``event_key`` and dismissing one writes
    a row here. The feed then hides any event whose key has been dismissed, the
    same way eStock's News_bar respects its ``deleted`` flag. Idempotent by key.

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "notification_dismissals"

    dismissal_id: Mapped[int] = mapped_column(primary_key=True)
    event_key: Mapped[str] = mapped_column(String(120), unique=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.branch_id"), nullable=True)
    dismissed_by: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        Index("IX_notif_dismissal_key", "event_key"),
    )


class ProductChange(Base):
    """Price / min-stock change log for a product (eStock Product_Changes parity).

    Written whenever ProCare edits a product's sell/buy price or minimum-stock
    level, so the pharmacy has a "who changed this price, from what, to what,
    and when" trail. One row per changed field. New table — ``create_all`` adds
    it automatically on existing databases.
    """

    __tablename__ = "product_changes"

    change_id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.product_id"))
    field: Mapped[str] = mapped_column(String(30))  # sell_price | buy_price | min_stock
    old_value: Mapped[float] = mapped_column(Money, default=0)
    new_value: Mapped[float] = mapped_column(Money, default=0)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        Index("IX_product_change_product", "product_id", "created_at"),
        Index("IX_product_change_created", "created_at"),
    )


class Shareholder(Base):
    """Company shareholder / owner (eStock ``company_Owner`` mirror, المساهمون).

    Read-only mirror of the owners register: each shareholder's current and
    starting capital. Dividends paid to them live in ``dividend_payments``.
    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "shareholders"

    shareholder_id: Mapped[int] = mapped_column(primary_key=True)
    # eStock coow_id, kept so the ETL can upsert without duplicating on re-sync.
    source_id: Mapped[int | None] = mapped_column(nullable=True, unique=True)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    name_ar: Mapped[str] = mapped_column(String(150))
    name_en: Mapped[str | None] = mapped_column(String(150), nullable=True)
    tel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_capital: Mapped[float] = mapped_column(Money, default=0)
    start_capital: Mapped[float] = mapped_column(Money, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    dividends: Mapped[list["DividendPayment"]] = relationship(
        back_populates="shareholder", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("IX_shareholder_source", "source_id"),
    )


class DividendPayment(Base):
    """A dividend paid to a shareholder for a year (eStock ``Gedo_Dividends_paied``).

    New table — ``create_all`` adds it automatically on existing databases.
    """

    __tablename__ = "dividend_payments"

    dividend_id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(nullable=True, unique=True)
    shareholder_id: Mapped[int] = mapped_column(ForeignKey("shareholders.shareholder_id"))
    year: Mapped[int | None] = mapped_column(nullable=True)
    # eStock Gedo_Financial journal link (gf_id) — kept for traceability.
    gf_id: Mapped[int | None] = mapped_column(nullable=True)
    amount: Mapped[float] = mapped_column(Money, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    shareholder: Mapped[Shareholder] = relationship(back_populates="dividends")

    __table_args__ = (
        Index("IX_dividend_shareholder", "shareholder_id"),
        Index("IX_dividend_year", "year"),
    )
