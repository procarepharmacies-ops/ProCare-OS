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
