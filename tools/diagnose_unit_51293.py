"""Diagnostic: investigate product 51293 unit-balance discrepancy.

Reads eStock (SELECT ONLY — never writes) from both branch servers and saves
results to .tmp/unit_diagnosis_51293.json (git-ignored).

Run from repo root:
    python tools/diagnose_unit_51293.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Locate repo root regardless of cwd
REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "src" / "backend"))

try:
    from app.config import settings
except Exception:
    settings = None


def _load_connections() -> dict:
    path = REPO / "config" / "connections.json"
    if not path.exists():
        raise FileNotFoundError(f"connections.json not found at {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_FALLBACK_DRIVERS = [
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server Native Client 10.0",
    "SQL Server",
]


def _build_url(src: dict, driver_override: str | None = None) -> str:
    import urllib.parse
    driver = driver_override or src.get("driver", "ODBC Driver 18 for SQL Server")
    server = src["server"]
    db = src["database"]
    user = src["username"]
    pwd = src["password"]
    encrypt = src.get("encrypt", "yes")
    trust = src.get("trust_server_certificate", "yes")
    driver_enc = urllib.parse.quote_plus(driver)
    return (
        f"mssql+pyodbc://{urllib.parse.quote_plus(user)}:{urllib.parse.quote_plus(pwd)}"
        f"@{server}/{db}?driver={driver_enc}"
        f"&Encrypt={encrypt}&TrustServerCertificate={trust}"
    )


def _create_engine_with_fallback(src: dict):
    """Try configured driver first, then each fallback in order."""
    from sqlalchemy import create_engine
    drivers = [src.get("driver")] + _FALLBACK_DRIVERS
    seen = set()
    last_err = None
    for drv in drivers:
        if not drv or drv in seen:
            continue
        seen.add(drv)
        try:
            url = _build_url(src, drv)
            engine = create_engine(url, connect_args={"timeout": 10})
            # Force an actual connection to test it
            with engine.connect():
                pass
            return engine, drv
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"No working ODBC driver found. Last error: {last_err}")


PRODUCT_CODE = "51293"

# SQL Server 2008-compatible queries (no OFFSET/FETCH, no DATEFROMPARTS, etc.)
SQL_PRODUCT = """
SELECT TOP 10
    product_id,
    product_code,
    product_name_ar,
    product_name_en,
    product_unit1,
    product_unit2,
    product_no2per1,
    buy_price,
    sell_price,
    active,
    deleted
FROM Products
WHERE product_code = :code
"""

SQL_PA = """
SELECT TOP 100
    pa.product_id,
    pa.store_id,
    pa.amount,
    pa.buy_price,
    pa.sell_price,
    pa.exp_date
FROM Product_Amount pa
INNER JOIN Products p ON p.product_id = pa.product_id
WHERE p.product_code = :code
ORDER BY pa.store_id, pa.exp_date
"""

# Branches_Product_Amount may not exist on every server
SQL_BPA = """
SELECT TOP 100
    bpa.product_id,
    bpa.store_id,
    bpa.amount,
    bpa.buy_price,
    bpa.sell_price,
    bpa.exp_date
FROM Branches_Product_Amount bpa
INNER JOIN Products p ON p.product_id = bpa.product_id
WHERE p.product_code = :code
ORDER BY bpa.store_id, bpa.exp_date
"""

SQL_SALES_SAMPLE = """
SELECT TOP 5
    sd.sales_id,
    sd.product_id,
    sd.amount,
    sd.sell_price,
    sh.bill_date
FROM Sales_details sd
INNER JOIN Sales_header sh ON sh.sales_id = sd.sales_id
INNER JOIN Products p ON p.product_id = sd.product_id
WHERE p.product_code = :code
ORDER BY sh.bill_date DESC
"""


def _rows_to_list(rows) -> list[dict]:
    """Convert SQLAlchemy Row/Mapping objects to plain dicts (JSON-serialisable)."""
    import decimal
    out = []
    for r in rows:
        d = {}
        for k, v in dict(r).items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
            elif isinstance(v, decimal.Decimal):
                d[k] = float(v)
            else:
                d[k] = v
        out.append(d)
    return out


def _pick(cols: set, *candidates: str) -> str | None:
    low = {c.lower(): c for c in cols}
    for c in candidates:
        if c.lower() in low:
            return low[c.lower()]
    return None


def _query_source(name: str, src_cfg: dict) -> dict:
    from sqlalchemy import inspect, text

    result: dict = {"source": name, "server": src_cfg["server"]}
    try:
        engine, driver_used = _create_engine_with_fallback(src_cfg)
        result["driver_used"] = driver_used
        insp = inspect(engine)

        with engine.connect() as conn:
            # --- introspect Products columns first ---
            p_cols = {c["name"] for c in insp.get_columns("Products")}
            col_pid      = _pick(p_cols, "product_id")
            col_code     = _pick(p_cols, "product_code", "code")
            col_name_ar  = _pick(p_cols, "product_name_ar", "name_ar")
            col_name_en  = _pick(p_cols, "product_name_en", "name_en")
            col_unit1    = _pick(p_cols, "product_unit1", "unit1", "unit_name")
            col_unit2    = _pick(p_cols, "product_unit2", "unit2", "sub_unit")
            col_factor   = _pick(p_cols, "product_no2per1", "no2per1", "unit2_per_unit1",
                                  "product_unit2_count", "unit_factor")
            col_buy      = _pick(p_cols, "buy_price")
            col_sell     = _pick(p_cols, "sell_price")
            col_active   = _pick(p_cols, "active")
            col_deleted  = _pick(p_cols, "deleted")

            result["products_columns_present"] = {
                "unit1": col_unit1, "unit2": col_unit2, "factor": col_factor
            }

            # Build SELECT dynamically using only columns that exist
            select_cols = ", ".join(c for c in [
                col_pid, col_code, col_name_ar, col_name_en,
                col_unit1, col_unit2, col_factor,
                col_buy, col_sell, col_active, col_deleted,
            ] if c)
            sql_prod = f"SELECT TOP 10 {select_cols} FROM Products WHERE {col_code} = :code"
            rows = conn.execute(text(sql_prod), {"code": PRODUCT_CODE}).mappings().all()
            result["product_master"] = _rows_to_list(rows)

            # --- Product_Amount ---
            if insp.has_table("Product_Amount"):
                pa_cols = {c["name"] for c in insp.get_columns("Product_Amount")}
                pa_pid    = _pick(pa_cols, "product_id")
                pa_store  = _pick(pa_cols, "store_id")
                pa_ctr    = _pick(pa_cols, "counter_id")
                pa_amt    = _pick(pa_cols, "amount")
                pa_buy    = _pick(pa_cols, "buy_price")
                pa_sell   = _pick(pa_cols, "sell_price")
                pa_exp    = _pick(pa_cols, "exp_date")
                result["Product_Amount_columns"] = sorted(pa_cols)
                pa_sel = ", ".join(f"pa.{c}" for c in [
                    pa_pid, pa_store, pa_ctr, pa_amt, pa_buy, pa_sell, pa_exp
                ] if c)
                sql_pa = (
                    f"SELECT TOP 100 {pa_sel} "
                    f"FROM Product_Amount pa "
                    f"INNER JOIN Products p ON p.{col_pid} = pa.{pa_pid} "
                    f"WHERE p.{col_code} = :code "
                    f"ORDER BY pa.{pa_store or '1'}, pa.{pa_exp or '1'}"
                )
                rows = conn.execute(text(sql_pa), {"code": PRODUCT_CODE}).mappings().all()
                result["Product_Amount"] = _rows_to_list(rows)
            else:
                result["Product_Amount"] = "TABLE_MISSING"

            # --- Branches_Product_Amount ---
            if insp.has_table("Branches_Product_Amount"):
                bpa_cols = {c["name"] for c in insp.get_columns("Branches_Product_Amount")}
                bpa_pid   = _pick(bpa_cols, "product_id")
                bpa_store = _pick(bpa_cols, "store_id")
                bpa_ctr   = _pick(bpa_cols, "counter_id", "pa_id")
                bpa_amt   = _pick(bpa_cols, "amount")
                bpa_buy   = _pick(bpa_cols, "buy_price")
                bpa_sell  = _pick(bpa_cols, "sell_price")
                bpa_exp   = _pick(bpa_cols, "exp_date")
                result["Branches_Product_Amount_columns"] = sorted(bpa_cols)
                bpa_sel = ", ".join(f"bpa.{c}" for c in [
                    bpa_pid, bpa_store, bpa_ctr, bpa_amt, bpa_buy, bpa_sell, bpa_exp
                ] if c)
                sql_bpa = (
                    f"SELECT TOP 100 {bpa_sel} "
                    f"FROM Branches_Product_Amount bpa "
                    f"INNER JOIN Products p ON p.{col_pid} = bpa.{bpa_pid} "
                    f"WHERE p.{col_code} = :code "
                    f"ORDER BY bpa.{bpa_store or '1'}, bpa.{bpa_exp or '1'}"
                )
                rows = conn.execute(text(sql_bpa), {"code": PRODUCT_CODE}).mappings().all()
                result["Branches_Product_Amount"] = _rows_to_list(rows)
            else:
                result["Branches_Product_Amount"] = "TABLE_MISSING"

            # --- Recent sales sample ---
            if insp.has_table("Sales_details") and insp.has_table("Sales_header"):
                sd_cols = {c["name"] for c in insp.get_columns("Sales_details")}
                sh_cols = {c["name"] for c in insp.get_columns("Sales_header")}
                sd_sid  = _pick(sd_cols, "sales_id")
                sd_pid  = _pick(sd_cols, "product_id")
                sd_amt  = _pick(sd_cols, "amount", "back_amount")
                sd_sell = _pick(sd_cols, "sell_price", "back_price")
                sh_date = _pick(sh_cols, "bill_date", "insert_date")
                if sd_sid and sd_pid and sd_amt:
                    sql_sales = (
                        f"SELECT TOP 5 sd.{sd_sid}, sd.{sd_pid}, sd.{sd_amt}, "
                        f"sd.{sd_sell or sd_amt}, sh.{sh_date or sd_sid} "
                        f"FROM Sales_details sd "
                        f"INNER JOIN Sales_header sh ON sh.{sd_sid} = sd.{sd_sid} "
                        f"INNER JOIN Products p ON p.{col_pid} = sd.{sd_pid} "
                        f"WHERE p.{col_code} = :code "
                        f"ORDER BY sh.{sh_date or sd_sid} DESC"
                    )
                    rows = conn.execute(text(sql_sales), {"code": PRODUCT_CODE}).mappings().all()
                    result["recent_sales_sample"] = _rows_to_list(rows)
                else:
                    result["recent_sales_sample"] = "COLUMN_MISSING"
            else:
                result["recent_sales_sample"] = "TABLE_MISSING"

        result["status"] = "ok"
    except Exception as e:  # noqa: BLE001
        result["status"] = "error"
        result["error"] = str(e)
    return result


def main() -> None:
    cfg = _load_connections()
    sources = cfg.get("estock_sources", [])
    if not sources:
        # Fall back to single-source config
        single = cfg.get("estock_source")
        if single:
            sources = [{"name": "default", **single}]
    if not sources:
        print("No estock_sources configured in connections.json", file=sys.stderr)
        sys.exit(1)

    all_results = []
    for src in sources:
        name = src.get("name", "unknown")
        print(f"Querying {name} ({src['server']}) ...", flush=True)
        r = _query_source(name, src)
        all_results.append(r)
        if r["status"] == "ok":
            print(f"  product_master rows: {len(r.get('product_master', []))}")
            print(f"  Product_Amount rows: {len(r.get('Product_Amount', []))}")
            print(f"  Branches_Product_Amount rows: {len(r.get('Branches_Product_Amount', []))}")
        else:
            print(f"  ERROR: {r['error']}")

    out_path = REPO / ".tmp" / "unit_diagnosis_51293.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
