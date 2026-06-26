"""Read-only eStock → ProCare mirror ETL (Phase 1).

This is the pluggable adapter that, in production, reads the live eStock SQL
Server (``stock`` on 192.168.1.2) through a dedicated READ-ONLY login and writes
the cleaned rows into ProCare's own database — applying every data-quality rule
in ``docs/05-data-quality-and-fixes.md``:

  * ``sale_date = COALESCE(bill_date, insert_date)``  (eStock bill_date is often NULL)
  * exclude returns from sales metrics  (``back <> 'Y'``)
  * available stock = ``amount > 0`` AND not expired
  * FEFO ordering on expiry

GUARDRAIL: ProCare NEVER writes to eStock. This module opens the eStock engine
read-only and only SELECTs. It activates only when real read-only credentials
are present in ``config/connections.json``; otherwise the system runs on its own
seeded data (``app.db.seed``) so the whole stack is demonstrable offline.

The per-table SELECT→clean→UPSERT mappings are specified in the roadmap (Phase 1
checklist). They are intentionally not hard-coded against unverified column
shapes here — the eStock audit fixes column names, but the live login and final
incremental-sync watermark column are TBD and must be confirmed before the first
real run. ``status()`` reports exactly what is and isn't wired so the operator
knows the current state.
"""
from __future__ import annotations

from app.config import settings

# eStock source table -> ProCare destination, with the cleaning rule applied.
# (Row counts are from the 2026-06-23 audit; see docs/02 and docs/06.)
MIRROR_PLAN = [
    ("Products (53,474)", "products", "bilingual names; product_drug->is_controlled; has_expire->has_expiry"),
    ("Branches_Product_Amount (121,625)", "stock_batches", "per-branch batches; amount>0 for available; FEFO by exp_date"),
    ("Customer (1,197)", "customers", "credit_limit, current_balance kept; limit enforced at POS"),
    ("Vendor (87)", "vendors", "balances kept"),
    ("Sales_header (95,088)", "sales", "sale_date = COALESCE(bill_date, insert_date); back='Y' -> is_return"),
    ("Sales_details (183,906)", "sale_lines", "buy_price snapshot kept for profit"),
    ("Back_sales_header/details (4,359/4,212)", "sales/sale_lines", "is_return = 1"),
    ("Purchase_header/details (685/9,230)", "purchases/purchase_lines", "bonus + exp_date carried"),
    ("Gedo_* ledgers (93,925/88,359/2,878/9,271)", "ledger_entries", "unified, branch_id tagged"),
    ("Branch_order_* (8,204/61,872)", "stock_transfers/_lines", "batch identity + expiry travels"),
    ("Branch_money_* (1,102/1,098)", "cash_transfers", "inter-branch cash"),
]


def is_available() -> bool:
    """True only when a real read-only eStock login is configured."""
    return settings.estock_sqlalchemy_url() is not None


def status() -> dict:
    """Report whether the live mirror can run, and the planned table mappings."""
    available = is_available()
    return {
        "estock_source_configured": available,
        "mode": "live read-only mirror" if available else "offline (running on ProCare's own seeded data)",
        "guardrail": "ProCare NEVER writes to eStock — read-only ETL only.",
        "data_quality_rules": [
            "sale_date = COALESCE(bill_date, insert_date)",
            "exclude returns (back <> 'Y')",
            "available stock = amount > 0 AND not expired",
            "FEFO = ORDER BY exp_date ASC",
        ],
        "mirror_plan": [
            {"source": src, "destination": dst, "rule": rule} for src, dst, rule in MIRROR_PLAN
        ],
        "tbd": [
            "read-only eStock login name/permissions",
            "incremental-sync watermark column for delta loads",
            "Titan/Drug-Eye schema at D:\\Labirdo",
        ],
    }


def run_full_load() -> dict:
    """Entry point for the Phase-1 full mirror.

    Refuses to run (rather than guess) until a real read-only eStock login is
    configured, keeping the read-only guardrail explicit and safe.
    """
    if not is_available():
        return {
            "ran": False,
            "reason": "No read-only eStock credentials configured. "
            "Fill config/connections.json:estock_source, then re-run. "
            "The system runs on its own seeded data until then.",
        }
    # Live implementation: open the read-only eStock engine, SELECT per
    # MIRROR_PLAN applying the cleaning rules, UPSERT into ProCare. Deliberately
    # gated on a verified login + confirmed column shapes before first run.
    raise NotImplementedError(
        "Live eStock mirror is gated pending a verified read-only login and the "
        "confirmed incremental-sync watermark column (see docs/06 Phase 1)."
    )
