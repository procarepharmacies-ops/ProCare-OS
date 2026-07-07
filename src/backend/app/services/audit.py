"""In-system cash-flow & inventory audit — the owner's report, computed live.

One call produces the full audit for every branch from ProCare's own database
(which mirrors BOTH eStock stores once the sync is on — see /api/sync/status):

  * revenue / gross profit / bills over the window,
  * purchases (all vendors) and the purchases-to-sales ratio (alarm > 85%),
  * a vendor focus (e.g. PharmaOverseas): invoiced, paid, open balance,
  * treasury: cash position, in/out, cash-desk closures and variances,
  * stock: value at cost/retail, expired (cash lost), expiring ≤ 90 days
    (cash at risk), dead stock ≥ 90 days without a sale (cash locked),
  * receivables: total and the portion above credit limits.

The report always states its own data source honestly: ``live`` only when
ProCare runs on SQL Server AND the eStock mirror is configured — otherwise
``demo`` so nobody mistakes seeded numbers for the pharmacy's.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.db.base import IS_SQLITE
from app.services import sync
from app.services.common import TODAY, as_date, money

RATIO_ALARM = 0.85  # purchases/sales above this converts cash into shelf stock


def data_source() -> dict:
    live = (not IS_SQLITE) and sync.is_configured()
    return {
        "mode": "live" if live else "demo",
        "procare_db": "sqlserver" if not IS_SQLITE else "sqlite (dev)",
        "estock_sync_configured": sync.is_configured(),
        "hint": None if live else (
            "fill config/connections.json (procare_database = SQL Server Express, "
            "estock_source = read-only eStock login with store_branch_map for both "
            "branches) and restart — the same report then shows the real figures"
        ),
    }


def find_vendor(session: Session, query: str | None) -> m.Vendor | None:
    """Vendor focus for the report. Tries the query (Arabic or English,
    substring) and falls back to the vendor we owe the most."""
    vendors = session.scalars(select(m.Vendor).where(m.Vendor.is_active == True)).all()  # noqa: E712
    if query:
        q = query.strip().lower()
        for v in vendors:
            if q in (v.name_ar or "").lower() or q in (v.name_en or "").lower():
                return v
    return max(vendors, key=lambda v: float(v.current_balance or 0), default=None)


def cash_report(session: Session, months: int = 3, vendor_query: str | None = None) -> dict:
    start = TODAY - timedelta(days=30 * months)
    branches = session.scalars(select(m.Branch).order_by(m.Branch.branch_id)).all()
    vendor = find_vendor(session, vendor_query)

    out_branches = []
    for b in branches:
        bid = b.branch_id

        # --- sales ------------------------------------------------------------
        revenue, bills, discount = session.execute(
            select(
                func.coalesce(func.sum(m.Sale.total_net), 0),
                func.count(),
                func.coalesce(func.sum(m.Sale.total_discount), 0),
            ).where(
                m.Sale.branch_id == bid,
                m.Sale.is_return == False,  # noqa: E712
                as_date(m.Sale.sale_date) >= start,
            )
        ).one()
        gross_profit = session.execute(
            select(func.coalesce(func.sum(m.SaleLine.total_sell - m.SaleLine.amount * m.SaleLine.buy_price), 0))
            .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
            .where(
                m.Sale.branch_id == bid,
                m.Sale.is_return == False,  # noqa: E712
                as_date(m.Sale.sale_date) >= start,
            )
        ).scalar_one()
        returns_refunded = session.execute(
            select(func.coalesce(func.sum(m.Sale.total_net), 0)).where(
                m.Sale.branch_id == bid,
                m.Sale.is_return == True,  # noqa: E712
                as_date(m.Sale.sale_date) >= start,
            )
        ).scalar_one()

        # --- purchases ----------------------------------------------------------
        purchases_all = session.execute(
            select(func.coalesce(func.sum(m.Purchase.total_gross), 0)).where(
                m.Purchase.branch_id == bid,
                m.Purchase.is_return == False,  # noqa: E712
                m.Purchase.bill_date >= start,
            )
        ).scalar_one()
        purchase_returns = session.execute(
            select(func.coalesce(func.sum(m.Purchase.total_gross), 0)).where(
                m.Purchase.branch_id == bid,
                m.Purchase.is_return == True,  # noqa: E712
                m.Purchase.bill_date >= start,
            )
        ).scalar_one()
        ratio = (float(purchases_all) / float(revenue)) if float(revenue) > 0 else None

        # --- vendor focus ---------------------------------------------------------
        vendor_invoiced = vendor_paid = 0.0
        if vendor is not None:
            vendor_invoiced = float(
                session.execute(
                    select(func.coalesce(func.sum(m.Purchase.total_gross), 0)).where(
                        m.Purchase.branch_id == bid,
                        m.Purchase.vendor_id == vendor.vendor_id,
                        m.Purchase.is_return == False,  # noqa: E712
                        m.Purchase.bill_date >= start,
                    )
                ).scalar_one()
            )
            # Payments to the vendor = debits on his ledger account (a credit
            # purchase books a credit; settling it books a debit).
            vendor_paid = float(
                session.execute(
                    select(func.coalesce(func.sum(m.LedgerEntry.debit), 0)).where(
                        m.LedgerEntry.branch_id == bid,
                        m.LedgerEntry.account_type == "vendor",
                        m.LedgerEntry.account_ref == vendor.vendor_id,
                        as_date(m.LedgerEntry.entry_date) >= start,
                        m.LedgerEntry.ref_type != "purchase_return",
                    )
                ).scalar_one()
            )

        # --- treasury / cash ---------------------------------------------------------
        cash_in, cash_out = session.execute(
            select(
                func.coalesce(func.sum(m.LedgerEntry.debit), 0),
                func.coalesce(func.sum(m.LedgerEntry.credit), 0),
            ).where(m.LedgerEntry.branch_id == bid, m.LedgerEntry.account_type == "cash")
        ).one()
        expenses = session.execute(
            select(func.coalesce(func.sum(m.LedgerEntry.credit), 0)).where(
                m.LedgerEntry.branch_id == bid,
                m.LedgerEntry.account_type == "cash",
                m.LedgerEntry.ref_type.in_(("treasury_out", "treasury_adjust")),
                as_date(m.LedgerEntry.entry_date) >= start,
            )
        ).scalar_one()
        shifts, variance = session.execute(
            select(func.count(), func.coalesce(func.sum(m.CashShift.variance), 0)).where(
                m.CashShift.branch_id == bid,
                m.CashShift.status == "closed",
                as_date(m.CashShift.opened_at) >= start,
            )
        ).one()

        # --- stock ---------------------------------------------------------------------
        stock_cost, stock_retail = session.execute(
            select(
                func.coalesce(func.sum(m.StockBatch.amount * m.StockBatch.buy_price), 0),
                func.coalesce(func.sum(m.StockBatch.amount * m.StockBatch.sell_price), 0),
            ).where(m.StockBatch.branch_id == bid, m.StockBatch.amount > 0)
        ).one()
        expired_batches, expired_cost = session.execute(
            select(func.count(), func.coalesce(func.sum(m.StockBatch.amount * m.StockBatch.buy_price), 0)).where(
                m.StockBatch.branch_id == bid,
                m.StockBatch.amount > 0,
                m.StockBatch.exp_date != None,  # noqa: E711
                m.StockBatch.exp_date <= TODAY,
            )
        ).one()
        at_risk_90 = session.execute(
            select(func.coalesce(func.sum(m.StockBatch.amount * m.StockBatch.buy_price), 0)).where(
                m.StockBatch.branch_id == bid,
                m.StockBatch.amount > 0,
                m.StockBatch.exp_date != None,  # noqa: E711
                m.StockBatch.exp_date > TODAY,
                m.StockBatch.exp_date <= TODAY + timedelta(days=90),
            )
        ).scalar_one()
        # Dead stock: on-shelf products with zero sales in the window.
        sold_pids = select(m.SaleLine.product_id).join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id).where(
            m.Sale.branch_id == bid,
            m.Sale.is_return == False,  # noqa: E712
            as_date(m.Sale.sale_date) >= TODAY - timedelta(days=90),
        )
        dead_products, dead_cost = session.execute(
            select(
                func.count(func.distinct(m.StockBatch.product_id)),
                func.coalesce(func.sum(m.StockBatch.amount * m.StockBatch.buy_price), 0),
            ).where(
                m.StockBatch.branch_id == bid,
                m.StockBatch.amount > 0,
                m.StockBatch.product_id.not_in(sold_pids),
            )
        ).one()

        out_branches.append(
            {
                "branch_id": bid,
                "code": b.code,
                "name_ar": b.name_ar,
                "name_en": b.name_en,
                "revenue": money(revenue),
                "bills": bills,
                "discount": money(discount),
                "gross_profit": money(gross_profit),
                "sales_returns_refunded": money(returns_refunded),
                "purchases_all_vendors": money(purchases_all),
                "purchase_returns": money(purchase_returns),
                "purchases_to_sales_pct": round(ratio * 100, 1) if ratio is not None else None,
                "ratio_alarm": bool(ratio is not None and ratio > RATIO_ALARM),
                "vendor_invoiced": money(vendor_invoiced),
                "vendor_paid": money(vendor_paid),
                "vendor_gap": money(vendor_invoiced - vendor_paid),
                "expenses_window": money(expenses),
                "treasury_balance": money(float(cash_in) - float(cash_out)),
                "cash_desk": {"closed_shifts": shifts, "variance_total": money(variance)},
                "stock_cost": money(stock_cost),
                "stock_retail": money(stock_retail),
                "expired": {"batches": expired_batches, "cash_lost": money(expired_cost)},
                "expiring_90d_cost": money(at_risk_90),
                "dead_stock": {"products": dead_products, "cash_locked": money(dead_cost)},
            }
        )

    receivables_total = session.execute(
        select(func.coalesce(func.sum(m.Customer.current_balance), 0)).where(m.Customer.current_balance > 0)
    ).scalar_one()
    # Over-limit portion, computed in Python (SQLite lacks GREATEST):
    over_rows = session.execute(
        select(m.Customer.current_balance, m.Customer.credit_limit).where(
            m.Customer.credit_limit > 0, m.Customer.current_balance > m.Customer.credit_limit
        )
    ).all()
    receivables_over = sum(float(b) - float(l) for b, l in over_rows)
    debtors_over = len(over_rows)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window_months": months,
        "window_start": start.isoformat(),
        "data_source": data_source(),
        "vendor_focus": (
            {
                "vendor_id": vendor.vendor_id,
                "name_ar": vendor.name_ar,
                "name_en": vendor.name_en,
                "balance_now": money(vendor.current_balance),
            }
            if vendor
            else None
        ),
        "branches": out_branches,
        "receivables": {
            "total": money(receivables_total),
            "over_limit": money(receivables_over),
            "debtors_over_limit": debtors_over,
        },
        "ratio_alarm_threshold_pct": RATIO_ALARM * 100,
    }
