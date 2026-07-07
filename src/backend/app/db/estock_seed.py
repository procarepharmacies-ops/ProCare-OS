"""Seed an *eStock-shaped* source database with realistic raw data.

This stands in for the live eStock SQL Server (``stock`` on 192.168.1.2) when it
isn't reachable — e.g. in the Docker demo, where a second SQL Server container
plays the role of eStock so the continuous sync (``app.services.sync``) has a
real source to mirror from. The same code runs against SQLite (tests) and SQL
Server (the demo container), because the tables are defined with portable
SQLAlchemy Core types.

The table + column names match the 2026-06-23 audit (docs/02) so the read-only
mirror (``app.services.etl``) extracts them unchanged. This module writes the
*raw, messy* eStock shape on purpose (char(1) 'Y'/'N' flags, walk-in
``customer_id = 0``, NULL ``bill_date``, a negative stock row, a return) so the
sync's data-quality cleaning is exercised against real-looking input.

NOT used in production: there the source IS the real eStock and this never runs.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from sqlalchemy import (
    Unicode,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    create_engine,
    insert,
)

RNG = random.Random(20260627)
TODAY = date(2026, 6, 26)

# Realistic Egyptian-pharmacy catalogue (ar / en / scientific) — same shape as
# the ProCare demo seed, so the mirrored data looks like the real pharmacy.
DRUGS = [
    ("بانادول", "Panadol", "Paracetamol", "N"),
    ("أوجمنتين", "Augmentin", "Amoxicillin/Clavulanate", "Y"),
    ("كونجستال", "Congestal", "Paracetamol/Chlorphenamine", "N"),
    ("فلاجيل", "Flagyl", "Metronidazole", "N"),
    ("كلاريتين", "Claritine", "Loratadine", "N"),
    ("نوسبازم", "No-spa", "Drotaverine", "N"),
    ("فولتارين", "Voltaren", "Diclofenac", "N"),
    ("زيثروماكس", "Zithromax", "Azithromycin", "Y"),
    ("كونكور", "Concor", "Bisoprolol", "N"),
    ("جلوكوفاج", "Glucophage", "Metformin", "N"),
    ("نكسيوم", "Nexium", "Esomeprazole", "N"),
    ("أنتينال", "Antinal", "Nifuroxazide", "N"),
    ("بروفين", "Brufen", "Ibuprofen", "N"),
    ("كتافلام", "Cataflam", "Diclofenac Potassium", "N"),
    ("ريفو", "Rivo", "Aspirin", "N"),
    ("فيتامين سي", "Vitamin C", "Ascorbic Acid", "N"),
    ("موتيليوم", "Motilium", "Domperidone", "N"),
    ("سيبروسين", "Ciprocin", "Ciprofloxacin", "Y"),
    ("أوميبرازول", "Omez", "Omeprazole", "N"),
    ("هيستوب", "Histop", "Cetirizine", "N"),
    ("فاركولين", "Farcolin", "Salbutamol", "N"),
    ("لازكس", "Lasix", "Furosemide", "N"),
]
CUSTOMERS = [
    "أحمد محمد", "محمود علي", "فاطمة حسن", "سارة إبراهيم", "خالد يوسف", "منى سمير",
    "صيدلية النور", "مستشفى الأمل", "عيادة د. سمير", "ياسمين رضا", "طارق فؤاد", "ليلى كمال",
]
VENDORS = ["شركة المهن الطبية", "ابن سينا فارما", "يونايتد فارما", "مصر للأدوية", "فاركو"]

# --- eStock-shaped schema (audit column names, portable types) ---------------
metadata = MetaData()

Products = Table(
    "Products", metadata,
    Column("product_id", Integer, primary_key=True),
    Column("product_code", Unicode(50)),
    Column("product_name_ar", Unicode(150)),
    Column("product_name_en", Unicode(150)),
    Column("product_scientific_name", Unicode(200)),
    Column("product_drug", Unicode(1)),
    Column("product_has_expire", Unicode(1)),
    Column("sell_price", Numeric(18, 3)),
    Column("buy_price", Numeric(18, 3)),
    Column("tax_price", Numeric(18, 3)),
    Column("deleted", Unicode(1)),
    Column("active", Unicode(1)),
)
Customer = Table(
    "Customer", metadata,
    Column("customer_id", Integer, primary_key=True),
    Column("customer_name_ar", Unicode(150)),
    Column("customer_name_en", Unicode(150)),
    Column("mobile", Unicode(20)),
    Column("customer_max_money", Numeric(18, 3)),
    Column("customer_current_money", Numeric(18, 3)),
    Column("customer_start_money", Numeric(18, 3)),
    Column("deleted", Unicode(1)),
    Column("active", Unicode(1)),
)
Vendor = Table(
    "Vendor", metadata,
    Column("vendor_id", Integer, primary_key=True),
    Column("vendor_name_ar", Unicode(150)),
    Column("vendor_name_en", Unicode(150)),
    Column("tel", Unicode(20)),
    Column("mobile", Unicode(20)),
    Column("vendor_max_money", Numeric(18, 3)),
    Column("vendor_current_money", Numeric(18, 3)),
)
Product_Amount = Table(
    "Product_Amount", metadata,
    Column("pa_id", Integer, primary_key=True),
    Column("product_id", Integer),
    Column("store_id", Integer),
    Column("counter_id", Integer),
    Column("vendor_id", Integer),
    Column("amount", Numeric(18, 3)),
    Column("buy_price", Numeric(18, 3)),
    Column("sell_price", Numeric(18, 3)),
    Column("tax_price", Numeric(18, 3)),
    Column("exp_date", Date),
)
Sales_header = Table(
    "Sales_header", metadata,
    Column("sales_id", Integer, primary_key=True),
    Column("store_id", Integer),
    Column("customer_id", Integer),
    Column("bill_date", DateTime),
    Column("insert_date", DateTime),
    Column("total_bill", Numeric(18, 3)),
    Column("total_bill_net", Numeric(18, 3)),
    Column("total_disc_money", Numeric(18, 3)),
    Column("bill_cash", Numeric(18, 3)),
    Column("network_money", Numeric(18, 3)),
    Column("money_change", Numeric(18, 3)),
    Column("back", Unicode(1)),
)
Sales_details = Table(
    "Sales_details", metadata,
    Column("details_id", Integer, primary_key=True),
    Column("sales_id", Integer),
    Column("product_id", Integer),
    Column("counter_id", Integer),
    Column("amount", Numeric(18, 3)),
    Column("sell_price", Numeric(18, 3)),
    Column("buy_price", Numeric(18, 3)),
    Column("disc_money", Numeric(18, 3)),
    Column("total_sell", Numeric(18, 3)),
    Column("back", Unicode(1)),
)
Back_sales_header = Table(
    "Back_sales_header", metadata,
    Column("sales_id", Integer, primary_key=True),
    Column("store_id", Integer),
    Column("customer_id", Integer),
    Column("bill_date", DateTime),
    Column("insert_date", DateTime),
    Column("total_bill", Numeric(18, 3)),
    Column("total_bill_net", Numeric(18, 3)),
    Column("total_disc_money", Numeric(18, 3)),
    Column("bill_cash", Numeric(18, 3)),
    Column("network_money", Numeric(18, 3)),
    Column("money_change", Numeric(18, 3)),
    Column("back", Unicode(1)),
)
Back_Sales_details = Table(
    "Back_Sales_details", metadata,
    Column("details_id", Integer, primary_key=True),
    Column("sales_id", Integer),
    Column("product_id", Integer),
    Column("back_amount", Numeric(18, 3)),
    Column("back_price", Numeric(18, 3)),
    Column("buy_price", Numeric(18, 3)),
    Column("total_sell", Numeric(18, 3)),
    Column("back", Unicode(1)),
)


def seed_estock_source(engine, *, days: int = 60, drop: bool = True) -> dict:
    """Create eStock-shaped tables on ``engine`` and fill realistic raw data.

    Returns a summary of row counts. Deterministic (fixed RNG) so the sync is
    reproducible. Safe on SQLite and SQL Server.
    """
    if drop:
        metadata.drop_all(engine)
    metadata.create_all(engine)

    products, customers, vendors = [], [], []
    pa_rows, sh_rows, sd_rows = [], [], []
    bsh_rows, bsd_rows = [], []

    for i, (ar, en, sci, drug) in enumerate(DRUGS):
        sell = RNG.choice([12, 18, 25, 35, 48, 60, 85, 120, 7.5, 22.5])
        buy = round(sell * RNG.uniform(0.55, 0.78), 2)
        products.append(dict(
            product_id=101 + i, product_code=f"P{1000 + i}", product_name_ar=ar,
            product_name_en=en, product_scientific_name=sci, product_drug=drug,
            product_has_expire="Y", sell_price=sell, buy_price=buy, tax_price=0,
            deleted="N", active="Y",
        ))
    for i, name in enumerate(CUSTOMERS):
        limit = RNG.choice([0, 500, 1000, 2000, 5000])
        over = i % 5 == 0 and limit > 0
        bal = round(limit * RNG.uniform(1.05, 1.3), 2) if over else round(RNG.uniform(0, max(limit, 1) * 0.6), 2)
        customers.append(dict(
            customer_id=5 + i, customer_name_ar=name, customer_name_en=None,
            mobile="011" + "".join(str(RNG.randint(0, 9)) for _ in range(8)),
            customer_max_money=limit, customer_current_money=bal, customer_start_money=0,
            deleted="N", active="Y",
        ))
    for i, name in enumerate(VENDORS):
        vendors.append(dict(
            vendor_id=9 + i, vendor_name_ar=name, vendor_name_en=None, tel="02",
            mobile="010" + "".join(str(RNG.randint(0, 9)) for _ in range(8)),
            vendor_max_money=200000, vendor_current_money=round(RNG.uniform(0, 90000), 2),
        ))

    pa_id = 1
    for p in products:
        for store in (1, 2):
            for _ in range(RNG.randint(1, 2)):
                roll = RNG.random()
                if roll < 0.08:
                    exp = TODAY - timedelta(days=RNG.randint(5, 120))   # expired (cleaned out)
                    amount = RNG.randint(-3, 5)                          # incl. negative -> clamped
                elif roll < 0.25:
                    exp = TODAY + timedelta(days=RNG.randint(3, 60))
                    amount = RNG.randint(1, 40)
                else:
                    exp = TODAY + timedelta(days=RNG.randint(120, 720))
                    amount = RNG.randint(20, 200)
                pa_rows.append(dict(
                    pa_id=pa_id, product_id=p["product_id"], store_id=store, counter_id=500 + store,
                    vendor_id=RNG.choice(vendors)["vendor_id"], amount=amount,
                    buy_price=p["buy_price"], sell_price=p["sell_price"], tax_price=0, exp_date=exp,
                ))
                pa_id += 1

    sales_id, det_id = 1001, 1
    for day_offset in range(days, -1, -1):
        d = TODAY - timedelta(days=day_offset)
        for _ in range(RNG.randint(2, 8)):
            store = RNG.choice([1, 2])
            hour = RNG.randint(9, 22)
            insert_dt = datetime(d.year, d.month, d.day, hour, RNG.randint(0, 59))
            # eStock bug: bill_date often NULL on recent sales -> mirror COALESCEs.
            bill_dt = None if RNG.random() < 0.3 else insert_dt
            walk_in = RNG.random() < 0.5
            cust = 0 if walk_in else RNG.choice(customers)["customer_id"]
            lines = []
            gross = 0.0
            for _ in range(RNG.randint(1, 4)):
                p = RNG.choice(products)
                qty = RNG.randint(1, 3)
                total = round(float(p["sell_price"]) * qty, 2)
                gross += total
                lines.append((p, qty, total))
            net = round(gross, 2)
            sh_rows.append(dict(
                sales_id=sales_id, store_id=store, customer_id=cust, bill_date=bill_dt,
                insert_date=insert_dt, total_bill=gross, total_bill_net=net, total_disc_money=0,
                bill_cash=net, network_money=0, money_change=0, back="N",
            ))
            for p, qty, total in lines:
                sd_rows.append(dict(
                    details_id=det_id, sales_id=sales_id, product_id=p["product_id"],
                    counter_id=500 + store, amount=qty, sell_price=p["sell_price"],
                    buy_price=p["buy_price"], disc_money=0, total_sell=total, back="N",
                ))
                det_id += 1
            sales_id += 1

    # A couple of returns (back='Y') so the cleaning flags them and excludes them.
    bsh_rows.append(dict(
        sales_id=2001, store_id=1, customer_id=customers[0]["customer_id"],
        bill_date=datetime(TODAY.year, TODAY.month, TODAY.day, 9, 0), insert_date=datetime(TODAY.year, TODAY.month, TODAY.day, 9, 0),
        total_bill=12, total_bill_net=12, total_disc_money=0, bill_cash=12, network_money=0, money_change=0, back="Y",
    ))
    bsd_rows.append(dict(
        details_id=1, sales_id=2001, product_id=products[0]["product_id"],
        back_amount=1, back_price=12, buy_price=7, total_sell=12, back="Y",
    ))

    with engine.begin() as c:
        c.execute(insert(Products), products)
        c.execute(insert(Customer), customers)
        c.execute(insert(Vendor), vendors)
        c.execute(insert(Product_Amount), pa_rows)
        c.execute(insert(Sales_header), sh_rows)
        c.execute(insert(Sales_details), sd_rows)
        c.execute(insert(Back_sales_header), bsh_rows)
        c.execute(insert(Back_Sales_details), bsd_rows)

    return {
        "products": len(products), "customers": len(customers), "vendors": len(vendors),
        "stock_rows": len(pa_rows), "sales": len(sh_rows), "sale_lines": len(sd_rows),
        "returns": len(bsh_rows),
    }


def add_live_sale(engine, *, store_id: int = 1) -> int:
    """Append one new sale to the source (simulates a counter sale on eStock).

    Used to demonstrate that the continuous sync picks up new activity. Returns
    the new sales_id.
    """
    with engine.begin() as c:
        next_id = (c.execute(Sales_header.select()).rowcount, )  # noqa: F841
        max_id = c.exec_driver_sql("SELECT MAX(sales_id) FROM Sales_header").scalar() or 1000
        max_det = c.exec_driver_sql("SELECT MAX(details_id) FROM Sales_details").scalar() or 0
        sid = int(max_id) + 1
        pid = 101 + RNG.randint(0, len(DRUGS) - 1)
        now = datetime.now()
        c.execute(insert(Sales_header), [dict(
            sales_id=sid, store_id=store_id, customer_id=0, bill_date=now, insert_date=now,
            total_bill=25, total_bill_net=25, total_disc_money=0, bill_cash=25,
            network_money=0, money_change=0, back="N",
        )])
        c.execute(insert(Sales_details), [dict(
            details_id=int(max_det) + 1, sales_id=sid, product_id=pid, counter_id=500 + store_id,
            amount=1, sell_price=25, buy_price=15, disc_money=0, total_sell=25, back="N",
        )])
    return sid


def _engine_from_env():
    """Build the source engine from ESTOCK_* env (the demo container path)."""
    import os

    url = os.environ.get("ESTOCK_SEED_URL")
    if url:
        return create_engine(url)
    from app.config import settings

    src = settings.estock_sqlalchemy_url()
    if not src:
        raise SystemExit("No eStock source configured (set ESTOCK_SEED_URL or estock_source creds).")
    return create_engine(src)


if __name__ == "__main__":
    import json

    eng = _engine_from_env()
    summary = seed_estock_source(eng)
    print(json.dumps({"seeded_estock_source": summary}, ensure_ascii=False, indent=2, default=str))
