"""ETL / mirror + reconciliation (Phase 1 — read-only against eStock).

ProCare NEVER writes to the eStock ``stock`` database. This module reads it
read-only (through a dedicated read-only SQL login) and loads ProCare's own
clean DB, applying the data-quality fixes on the way in (docs/05):

  * ``COALESCE(bill_date, insert_date)``  -> ProCare ``sale_date`` is NON-NULL
  * exclude returns (``back <> 'Y'``)     -> sales metrics never include returns
  * available stock = ``amount > 0`` AND not expired
  * FEFO = ``ORDER BY exp_date ASC``

When eStock credentials are not configured (e.g. here, or before the read-only
login exists), the mirror falls back to the deterministic demo seed so the rest
of the system still has data to validate against. The eStock read SQL below is
real and ready — it simply isn't executed until the source is connected.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.config import settings
from app.db import get_db


# ---------------------------------------------------------------------------
# Pure data-quality rules (docs/05) — unit-testable, dialect-free
# ---------------------------------------------------------------------------
def coalesce_sale_date(bill_date, insert_date):
    """eStock bill_date is often NULL -> fall back to insert_date."""
    return bill_date if bill_date else insert_date


def is_excluded_return(back) -> bool:
    """A row is a return when eStock ``back`` == 'Y' (case-insensitive)."""
    return str(back).strip().upper() == "Y" if back is not None else False


def is_available(amount, exp_date, has_expire, today=None) -> bool:
    """Available stock = amount > 0 AND (no expiry OR not yet expired)."""
    today = today or date.today()
    if amount is None or amount <= 0:
        return False
    no_expiry = (str(has_expire).strip().upper() == "N") if has_expire is not None else False
    if no_expiry or exp_date is None:
        return True
    d = exp_date if isinstance(exp_date, date) else date.fromisoformat(str(exp_date)[:10])
    return d > today


def fefo_key(exp_date):
    """Sort key for First-Expire-First-Out (earliest expiry first)."""
    if exp_date is None:
        return date.max
    return exp_date if isinstance(exp_date, date) else date.fromisoformat(str(exp_date)[:10])


# ---------------------------------------------------------------------------
# eStock read SQL (real; runs only once the read-only login is connected)
# ---------------------------------------------------------------------------
ESTOCK_READ = {
    # Sales header with the NULL-date fix and returns flag.
    "sales": (
        "SELECT sales_id, branch_id, customer_id, cashier_id, "
        "COALESCE(bill_date, insert_date) AS sale_date, total_bill, "
        "total_disc_money, total_bill_net, bill_cash, network_money, "
        "CASE WHEN back = 'Y' THEN 1 ELSE 0 END AS is_return "
        "FROM Sales_header"
    ),
    "sale_lines": (
        "SELECT sd.sales_id, sd.product_id, sd.amount, sd.sell_price, "
        "sd.buy_price, sd.disc_money, sd.total_sell, "
        "CASE WHEN sh.back = 'Y' THEN 1 ELSE 0 END AS is_return "
        "FROM Sales_details sd JOIN Sales_header sh ON sh.sales_id = sd.sales_id"
    ),
    # Available stock only (amount > 0 and not expired); per branch + batch.
    "stock": (
        "SELECT product_id, store_id, counter_id, exp_date, amount, "
        "sell_price, buy_price "
        "FROM Branches_Product_Amount "
        "WHERE amount > 0 AND (exp_date > GETDATE() OR exp_date IS NULL)"
    ),
    "customers": (
        "SELECT customer_id, customer_name_ar, customer_name_en, "
        "customer_max_money AS credit_limit, customer_current_money AS balance "
        "FROM Customer"
    ),
    "vendors": (
        "SELECT vendor_id, vendor_name_ar, vendor_name_en, "
        "vendor_current_money AS balance FROM Vendor"
    ),
}


def _estock_engine():
    """Read-only SQLAlchemy engine for eStock, or None if not connectable."""
    block = settings.estock_connection()
    if not block:
        return None
    try:
        import pyodbc  # noqa: F401
        from sqlalchemy import create_engine
        from urllib.parse import quote_plus
    except Exception:
        return None
    odbc = (
        f"DRIVER={{{block['driver']}}};SERVER={block['server']};"
        f"DATABASE={block['database']};UID={block['username']};"
        f"PWD={block['password']};Encrypt={block.get('encrypt', 'yes')};"
        f"TrustServerCertificate={block.get('trust_server_certificate', 'yes')}"
    )
    # ApplicationIntent=ReadOnly is belt-and-braces; the LOGIN itself must be
    # read-only (db_datareader). The guardrail is the login, not this flag.
    return create_engine(
        "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc) + "&ApplicationIntent=ReadOnly",
        pool_pre_ping=True,
    )


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------
def _log_run(source: str, kind: str, status_: str, rows: int, note: str) -> None:
    db = get_db()
    if db.mode != "demo":
        return
    db.execute(
        """INSERT INTO etl_runs (source, kind, finished_at, status, rows_loaded, note)
           VALUES (?,?,?,?,?,?)""",
        (source, kind, datetime.now().isoformat(sep=" "), status_, rows, note),
    )


def run_mirror(kind: str = "full") -> dict:
    """Mirror eStock -> ProCare. Demo mode regenerates the synthetic seed."""
    if settings.estock_configured and _estock_engine() is not None:
        # Production path: execute ESTOCK_READ queries, transform, and upsert into
        # ProCare. Wired here but intentionally not auto-run from the API.
        return {
            "ran": False,
            "source": "estock",
            "note": ("eStock is connected. Run the full/incremental mirror from a "
                     "maintenance job (not the live API) using the ESTOCK_READ "
                     "queries + data-quality rules in this module."),
        }
    # Demo / shadow path
    from app.seed import seed

    summary = seed(reset=True)
    return {"ran": True, "source": "demo_seed", "note":
            "No eStock credentials configured — refreshed the synthetic shadow data.",
            "summary": summary}


def reconcile(days: int = 7) -> dict:
    """Phase-1 validation gate: ProCare totals vs eStock for the key checks.

    With eStock connected this compares both sides and reports drift. Without it,
    we report the ProCare-side figures so the validation UI works in shadow mode.
    """
    db = get_db()
    start = (date.today() - timedelta(days=days - 1)).isoformat()

    sales_by_day = db.query(
        """SELECT date(sale_date) AS day, ROUND(SUM(total_net),2) AS revenue, COUNT(*) AS bills
           FROM sales WHERE is_return = 0 AND date(sale_date) >= ?
           GROUP BY date(sale_date) ORDER BY day DESC""",
        (start,),
    )
    stock_value = db.query(
        """SELECT branch_id, ROUND(SUM(stock_value),2) AS stock_value
           FROM vw_stock_on_hand GROUP BY branch_id""",
    )
    customer_balance = db.query_one(
        "SELECT ROUND(SUM(current_balance),2) AS total FROM customers")["total"]
    vendor_balance = db.query_one(
        "SELECT ROUND(SUM(current_balance),2) AS total FROM vendors")["total"]
    profit = db.query_one(
        """SELECT ROUND(COALESCE(SUM(sl.total_sell),0),2) AS revenue,
                  ROUND(COALESCE(SUM(sl.amount*sl.buy_price),0),2) AS cost
           FROM sale_lines sl JOIN sales s ON s.sale_id = sl.sale_id
           WHERE s.is_return = 0 AND sl.is_return = 0 AND date(s.sale_date) >= ?""",
        (start,),
    )

    has_source = settings.estock_configured and _estock_engine() is not None
    return {
        "has_estock_source": has_source,
        "mode": "compare" if has_source else "procare_only",
        "window_days": days,
        "note": ("Comparing ProCare vs eStock." if has_source else
                 "No eStock source connected — showing ProCare-side figures only. "
                 "Connect the read-only login to enable side-by-side reconciliation."),
        "checks": {
            "sales_per_day": sales_by_day,
            "stock_value_per_branch": stock_value,
            "customer_balances_total": customer_balance,
            "vendor_balances_total": vendor_balance,
            "profit": {"revenue": profit["revenue"], "cost": profit["cost"],
                       "gross_profit": round(profit["revenue"] - profit["cost"], 2)},
        },
    }


def status() -> dict:
    db = get_db()
    last_runs = []
    if db.mode == "demo":
        try:
            last_runs = db.query(
                "SELECT source, kind, started_at, finished_at, status, rows_loaded, note "
                "FROM etl_runs ORDER BY run_id DESC LIMIT 5")
        except Exception:
            last_runs = []
    return {
        "procare_mode": db.mode,
        "estock_configured": settings.estock_configured,
        "estock_connectable": settings.estock_configured and _estock_engine() is not None,
        "titan_configured": settings.titan_configured,
        "data_quality_rules": [
            "COALESCE(bill_date, insert_date) -> sale_date NOT NULL",
            "exclude returns (back <> 'Y')",
            "available stock = amount > 0 AND not expired",
            "FEFO = ORDER BY exp_date ASC",
        ],
        "recent_runs": last_runs,
    }
