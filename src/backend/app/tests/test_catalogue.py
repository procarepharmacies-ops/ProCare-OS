"""Catalogue quality: duplicate detection + Titan enrichment proposals.

The safety property under test: strength is NEVER normalised away, so two
different strengths of the same brand can never be grouped as duplicates —
merging them would be a dispensing error.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.db import models as m
from app.db.base import SessionLocal
from app.services import catalogue


@pytest.fixture
def dupes():
    """Seed: a true duplicate pair, a pack-size variant pair, and a
    different-strength pair that must NOT be grouped."""
    s = SessionLocal()
    ids = {}
    try:
        specs = [
            # true duplicate: same name, double space (classic entry error)
            ("ZZDUP-A1", "بانادول  اكسترا 24 قرص", "PANADOL EXTRA 24 TAB"),
            ("ZZDUP-A2", "بانادول اكسترا 24 قرص", "PANADOL EXTRA 24 TAB"),
            # pack variant: same drug+strength, different box count
            ("ZZDUP-B1", "زيثرون 500 مجم 3 اقراص", "ZITHRONE 500MG 3 TAB"),
            ("ZZDUP-B2", "زيثرون 500 مجم 5 اقراص", "ZITHRONE 500MG 5 TAB"),
            # DIFFERENT STRENGTH — must never group
            ("ZZDUP-C1", "اوجمنتين 500 مجم", "AUGMENTIN 500 MG 20 TAB"),
            ("ZZDUP-C2", "اوجمنتين 1 جم", "AUGMENTIN 1 GM 20 TAB"),
        ]
        for code, ar, en in specs:
            p = m.Product(code=code, name_ar=ar, name_en=en, sell_price=10, buy_price=5)
            s.add(p)
            s.flush()
            ids[code] = p.product_id
        s.commit()
    finally:
        s.close()
    try:
        yield ids
    finally:
        s2 = SessionLocal()
        try:
            s2.execute(delete(m.Product).where(m.Product.code.like("ZZDUP-%")))
            s2.commit()
        finally:
            s2.close()


def _group_for(res, pid):
    for g in res["groups"]:
        if any(mem["product_id"] == pid for mem in g["members"]):
            return g
    return None


def test_exact_name_duplicate_is_high_confidence(dupes):
    with SessionLocal() as s:
        res = catalogue.duplicate_groups(s, limit=2000)
    g = _group_for(res, dupes["ZZDUP-A1"])
    assert g is not None, "identical English name must group"
    assert g["confidence"] == "high"
    assert {mem["product_id"] for mem in g["members"]} >= {dupes["ZZDUP-A1"], dupes["ZZDUP-A2"]}
    # a survivor is suggested but nothing is auto-applied
    assert g["suggested_survivor"] in (dupes["ZZDUP-A1"], dupes["ZZDUP-A2"])


def test_pack_variant_is_flagged_review_not_high(dupes):
    """3 TAB vs 5 TAB is the same drug but two real SKUs — surfaced for a human,
    never as a high-confidence merge."""
    with SessionLocal() as s:
        res = catalogue.duplicate_groups(s, limit=2000)
    g = _group_for(res, dupes["ZZDUP-B1"])
    if g is not None:
        assert g["confidence"] == "review"


def test_different_strengths_never_group(dupes):
    """The dispensing-safety invariant: 500 MG and 1 GM must never be duplicates."""
    with SessionLocal() as s:
        res = catalogue.duplicate_groups(s, limit=2000)
    g = _group_for(res, dupes["ZZDUP-C1"])
    if g is not None:
        member_ids = {mem["product_id"] for mem in g["members"]}
        assert dupes["ZZDUP-C2"] not in member_ids, "500 MG grouped with 1 GM!"


def test_duplicates_api(client):
    r = client.get("/api/catalogue/duplicates?limit=50")
    assert r.status_code == 200
    body = r.json()
    for key in ("group_count", "high_confidence", "needs_review", "groups"):
        assert key in body


def test_enrichment_api_only_missing_default(client):
    r = client.get("/api/catalogue/enrichment?limit=20")
    assert r.status_code == 200
    body = r.json()
    assert body["only_missing"] is True
    # every proposed diff must carry both sides so a reviewer can judge
    for p in body["proposals"]:
        for field, d in p["diffs"].items():
            assert "current" in d and "proposed" in d and d["action"] in ("fill", "replace")


def test_decisions_record_and_apply(client):
    """Approving a durable field applies it to ProCare AND stages it for the
    eStock export; rejecting records the ruling without touching the product."""
    from sqlalchemy import delete, select

    from app.db.base import SessionLocal

    products = client.get("/api/inventory/products?branch_id=1").json()["products"]
    a, b = products[0]["product_id"], products[1]["product_id"]
    try:
        r = client.post("/api/catalogue/decisions", json={"items": [
            {"product_id": a, "field": "uses", "new_value": "1.test indication",
             "source": "drugeye", "status": "approved"},
            {"product_id": b, "field": "uses", "new_value": "nope",
             "source": "drugeye", "status": "rejected"},
        ]})
        assert r.status_code == 200
        body = r.json()
        assert body["approved"] == 1 and body["rejected"] == 1
        assert body["applied_to_procare"] == 1

        with SessionLocal() as s:
            assert s.get(m.Product, a).uses == "1.test indication"
            # rejected proposal must NOT be written onto the product
            assert s.get(m.Product, b).uses != "nope"
            rows = s.scalars(select(m.CatalogueDecision)).all()
            assert {d.status for d in rows} == {"approved", "rejected"}
            # staged, not yet exported to eStock
            assert all(d.exported_at is None for d in rows)

        # Re-deciding the same product+field replaces the ruling in place.
        client.post("/api/catalogue/decisions", json={"items": [
            {"product_id": a, "field": "uses", "new_value": "1.test indication",
             "source": "drugeye", "status": "rejected"}]})
        with SessionLocal() as s:
            rows = s.scalars(select(m.CatalogueDecision).where(
                m.CatalogueDecision.product_id == a)).all()
            assert len(rows) == 1 and rows[0].status == "rejected"

        summary = client.get("/api/catalogue/decisions/summary").json()
        assert summary["rejected"] >= 2
    finally:
        with SessionLocal() as s:
            s.execute(delete(m.CatalogueDecision))
            for pid in (a, b):
                p = s.get(m.Product, pid)
                if p:
                    p.uses = None
            s.commit()


def test_name_fields_not_applied_locally(client):
    """name_ar/name_en are overwritten by every sync cycle, so approving them
    is recorded for the eStock export but deliberately NOT applied to ProCare —
    applying would silently revert and look broken."""
    from sqlalchemy import delete, select

    from app.db.base import SessionLocal

    pid = client.get("/api/inventory/products?branch_id=1").json()["products"][0]["product_id"]
    with SessionLocal() as s:
        before = s.get(m.Product, pid).name_en
    try:
        r = client.post("/api/catalogue/decisions", json={"items": [
            {"product_id": pid, "field": "name_en", "new_value": "SHOULD NOT APPLY",
             "source": "titan", "status": "approved"}]})
        assert r.status_code == 200
        assert r.json()["approved"] == 1
        assert r.json()["applied_to_procare"] == 0  # recorded only
        with SessionLocal() as s:
            assert s.get(m.Product, pid).name_en == before
            assert s.scalars(select(m.CatalogueDecision)).all()[0].status == "approved"
    finally:
        with SessionLocal() as s:
            s.execute(delete(m.CatalogueDecision))
            s.commit()
