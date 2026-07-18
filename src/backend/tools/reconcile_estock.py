"""eStock reconciliation harness — proves the ETL mirror matches eStock.

Runs the (fixed) read-only mirror from the eStock `stock` SQL Server database
into a THROWAWAY SQLite file, then prints eStock source totals side-by-side with
the mirrored ProCare totals. Nothing in the real ProCare database is touched.

    python tools/reconcile_estock.py

This is the "fix code + reconcile before wiping" check: if the numbers match,
the same mirror can then be run against production with confidence.
"""
from __future__ import annotations

import decimal
import sqlite3
import sys
from pathlib import Path

# eStock (SQL Server) returns NUMERIC columns as Decimal; the scratch DB here is
# SQLite, whose driver can't bind Decimal. Adapt Decimal->float for the harness
# only (production runs on SQL Server, which binds Decimal natively).
sqlite3.register_adapter(decimal.Decimal, lambda d: float(d))

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.db import models as m

ES = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=stock;"
      "UID=sa;PWD=ProCareAdmin#Strong2024;Encrypt=yes;TrustServerCertificate=yes")
ES_URL = "mssql+pyodbc:///?odbc_connect=" + __import__("urllib.parse", fromlist=["quote_plus"]).quote_plus(ES)


def estock_totals(eng) -> dict:
    with eng.connect() as c:
        def one(sql):
            return c.execute(text(sql)).first()
        out = {}
        s1 = one("SELECT COUNT(*), SUM(CAST(total_bill_net AS float)) FROM Sales_header WHERE ISNULL(back,'')<>'Y'")
        s2 = one("SELECT COUNT(*), SUM(CAST(total_bill_net AS float)) FROM Branches_sales_header WHERE ISNULL(back,'')<>'Y'")
        out["sales_rows"] = (s1[0] or 0) + (s2[0] or 0)
        out["sales_net"] = (s1[1] or 0) + (s2[1] or 0)
        p1 = one("SELECT COUNT(*), SUM(CAST(total_bill AS float)) FROM Purchase_header")
        p2 = one("SELECT COUNT(*), SUM(CAST(total_bill AS float)) FROM Branches_purchase_header")
        out["purch_rows"] = (p1[0] or 0) + (p2[0] or 0)
        out["purch_gross"] = (p1[1] or 0) + (p2[1] or 0)
        t = one("SELECT COUNT(*), SUM(CAST(cash_depot_current_money AS float)) FROM Cash_depots")
        out["depots"] = t[0] or 0
        out["treasury"] = t[1] or 0
        pr = one("SELECT COUNT(*) FROM Products WHERE ISNULL(deleted,'1')='1'") or (0,)
        out["products_live"] = pr[0]
        return out


def main() -> int:
    src = create_engine(ES_URL)
    print("Reading eStock source totals...", flush=True)
    es = estock_totals(src)

    # Fresh throwaway ProCare (SQLite) — schema + minimal seed (branches/vendor).
    scratch = Path(__file__).resolve().parents[1] / "data" / "_recon_scratch.db"
    scratch.parent.mkdir(exist_ok=True)
    if scratch.exists():
        scratch.unlink()
    dst_eng = create_engine(f"sqlite:///{scratch}")
    m.Base.metadata.create_all(dst_eng)
    Session = sessionmaker(bind=dst_eng)
    with Session() as s:
        s.add_all([
            m.Branch(code="ELSANTA", name_ar="السنطه", name_en="Elsanta"),
            m.Branch(code="MASHALA", name_ar="مسهله", name_en="Mas-hala"),
            m.Vendor(name_ar="مورد", name_en="Vendor"),
        ])
        s.commit()

    from app.services import etl
    print("Running the fixed mirror into scratch SQLite (this reads 190k+ sales)...", flush=True)
    with Session() as s:
        counts = etl.mirror(src, s, store_branch_map={"1": "ELSANTA", "2": "MASHALA"}, wipe=True)

    # Mirrored totals
    with Session() as s:
        mr_rows, mr_net = s.execute(
            select(func.count(), func.coalesce(func.sum(m.Sale.total_net), 0)).where(m.Sale.is_return == False)  # noqa: E712
        ).one()
        mp_rows, mp_gross = s.execute(
            select(func.count(), func.coalesce(func.sum(m.Purchase.total_gross), 0))
        ).one()
        treasury = s.execute(
            select(func.coalesce(func.sum(m.LedgerEntry.debit - m.LedgerEntry.credit), 0)).where(
                m.LedgerEntry.account_type.in_(("cash", "bank"))
            )
        ).scalar_one()
        prod = s.execute(select(func.count()).select_from(m.Product).where(m.Product.is_deleted == False)).scalar_one()  # noqa: E712
        cashiers = s.execute(select(func.count(func.distinct(m.Sale.cashier_id)))).scalar_one()

    def line(label, e, g):
        match = "OK " if abs((e or 0) - (g or 0)) < max(1, abs(e or 0) * 0.001) else "DIFF"
        print(f"  {label:22} eStock={e:>14,.0f}  mirror={g:>14,.0f}  [{match}]")

    print("\n===== RECONCILIATION (eStock  vs  fixed mirror) =====")
    line("sales rows", es["sales_rows"], mr_rows)
    line("sales net", es["sales_net"], mr_net)
    line("purchase rows", es["purch_rows"], mp_rows)
    line("purchase gross", es["purch_gross"], mp_gross)
    line("treasury (cash+bank)", es["treasury"], treasury)
    line("products (live)", es["products_live"], prod)
    print(f"  distinct cashiers mirrored: {cashiers}")
    print(f"\n  mirror counts: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
