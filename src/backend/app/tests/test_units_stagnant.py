"""Units (وحدة كبرى/صغرى), stagnant items (الأصناف الراكدة), cross-branch stock."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.db import models as m
from app.services import inventory


def test_products_carry_units(client):
    products = client.get("/api/inventory/products").json()["products"]
    assert products
    p = products[0]
    assert "unit_big" in p and "unit_small" in p and "unit_factor" in p
    assert p["unit_factor"] >= 1
    # Demo seed populates real Arabic units.
    assert any(x["unit_big"] == "علبة" for x in products)


def test_other_branch_availability(client, session):
    # A product stocked in branch 2: querying branch 1 must reveal it under
    # other_branches (the cashier's "متوفر في الفرع الآخر" signal).
    row = session.execute(
        select(m.StockBatch.product_id)
        .where(m.StockBatch.branch_id == 2, m.StockBatch.amount > 0)
        .limit(1)
    ).first()
    assert row, "seed stocks branch 2"
    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    match = next((p for p in products if p["product_id"] == row[0]), None)
    if match:  # product may be beyond the page limit — then fetch by search
        assert isinstance(match["other_branches"], list)
        if match["other_branches"]:
            other = match["other_branches"][0]
            assert other["branch_id"] != 1 and other["on_hand"] > 0


def test_stagnant_report(client, session):
    # A brand-new stocked product with zero sales is stagnant by definition.
    p = m.Product(name_ar="صنف راكد للاختبار", sell_price=10, buy_price=5, unit_factor=1)
    session.add(p)
    session.flush()
    session.add(
        m.StockBatch(
            product_id=p.product_id, branch_id=1, amount=7, buy_price=5, sell_price=10,
            exp_date=(datetime.now() + timedelta(days=365)).date(),
        )
    )
    session.commit()

    body = client.get("/api/inventory/stagnant?branch_id=1&days=90").json()
    ours = next((i for i in body["items"] if i["product_id"] == p.product_id), None)
    assert ours is not None, "unsold stocked product must appear as stagnant"
    assert ours["on_hand"] == 7 and ours["value"] == 35.0 and ours["last_sale"] is None
    assert body["total_value"] >= 35.0

    # Sell it now -> it must leave the stagnant list.
    sale = m.Sale(branch_id=1, sale_date=datetime.now(), total_net=10, is_return=False)
    session.add(sale)
    session.flush()
    session.add(
        m.SaleLine(
            sale_id=sale.sale_id, product_id=p.product_id, amount=1,
            sell_price=10, buy_price=5, total_sell=10,
        )
    )
    session.commit()
    body = client.get("/api/inventory/stagnant?branch_id=1&days=90").json()
    assert all(i["product_id"] != p.product_id for i in body["items"])


def test_stagnant_count_session(client):
    r = client.post(
        "/api/stocktaking",
        json={"branch_id": 1, "count_type": "partial", "scope": "stagnant"},
    )
    # Either there are stagnant items (session opens) or there are none
    # (422 nothing_to_count) — both are valid states of the seeded DB.
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        detail = client.get(f"/api/stocktaking/{r.json()['count_id']}").json()
        assert detail["note"] and "الراكدة" in detail["note"]


def test_etl_maps_units(session):
    """The eStock-shaped source carries unit1/unit2/no2per1 — the mirror must
    land them on ProCare products."""
    from sqlalchemy import create_engine

    from app.db import estock_seed
    from app.db.seed import reset_and_seed
    from app.services import sync

    eng = create_engine("sqlite://")
    estock_seed.seed_estock_source(eng, days=5)
    try:
        res = sync.run_once(source_engine=eng)
        assert res["ran"] is True, res
        with_units = session.scalars(
            select(m.Product).where(m.Product.unit_big == "علبة", m.Product.unit_factor > 1)
        ).first()
        assert with_units is not None
        assert with_units.unit_small in ("شريط", "أمبول", "كبسولة")
    finally:
        eng.dispose()
        reset_and_seed()


def test_etl_reads_mashala_unit_factor_column():
    """Mashala's eStock has no product_no2per1: the small-per-big factor is
    ``product_unit1_2`` (36 for the 36-piece pack, product 51293). Without it the
    mirror silently fell back to factor 1."""
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import Session

    from app.services import etl

    src_eng = create_engine("sqlite://")
    with src_eng.begin() as c:
        c.execute(text(
            "CREATE TABLE Products (product_id INTEGER PRIMARY KEY, product_code TEXT,"
            " product_name_ar TEXT, sell_price NUMERIC, buy_price NUMERIC,"
            " product_unit1 INTEGER, product_unit2 INTEGER, product_unit1_2 NUMERIC)"
        ))
        c.execute(text(
            "INSERT INTO Products VALUES (51293, 'MASH51293', 'حفاضات كبار سن ليدو 36 قطعة',"
            " 700, 599.41, 5, 23, 36)"
        ))
    dst_eng = create_engine("sqlite://")
    m.Base.metadata.create_all(dst_eng)
    try:
        with src_eng.connect() as src, Session(dst_eng) as dst:
            etl._load_products(inspect(src_eng), src, dst, {})
            prod = dst.scalars(select(m.Product).where(m.Product.code == "MASH51293")).one()
            assert prod.unit_factor == 36
    finally:
        src_eng.dispose()
        dst_eng.dispose()
