"""Barcode -> product map: learn-on-scan, idempotency, relink, backfill audit.

The DB is shared session-scoped, so every assertion works off a baseline delta
rather than an absolute count.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.db import models as m
from app.services import gtin_map
from app.services.pos import POSError

GTIN = "04006358001238"  # valid check digit (see fixtures/gs1_vectors.json)
EAN13 = "4006358001238"


def _two_products(session):
    rows = session.scalars(
        select(m.Product).where(m.Product.is_deleted == False).limit(2)  # noqa: E712
    ).all()
    assert len(rows) >= 2, "seed must provide at least two products"
    return rows[0], rows[1]


def _clear(session, gtin=GTIN):
    for row in session.scalars(
        select(m.ProductBarcode).where(m.ProductBarcode.gtin == gtin)
    ).all():
        session.delete(row)
    session.commit()


def test_learn_is_idempotent(session):
    """Re-learning the same pairing must be a no-op, not a duplicate row.

    This is what lets an offline queue replay a link with no idempotency key.
    """
    product, _ = _two_products(session)
    _clear(session)
    before = session.scalar(select(func.count()).select_from(m.ProductBarcode))

    first = gtin_map.learn(session, GTIN, product.product_id)
    assert first["created"] is True
    assert first["gtin"] == GTIN

    second = gtin_map.learn(session, GTIN, product.product_id)
    assert second["created"] is False
    assert second["seen_count"] == first["seen_count"] + 1

    after = session.scalar(select(func.count()).select_from(m.ProductBarcode))
    assert after == before + 1  # exactly one row, however many replays
    _clear(session)


def test_learn_rejects_conflicting_product_unless_forced(session):
    a, b = _two_products(session)
    _clear(session)
    gtin_map.learn(session, GTIN, a.product_id)

    with pytest.raises(POSError) as exc:
        gtin_map.learn(session, GTIN, b.product_id)
    assert exc.value.code == "gtin_taken"

    forced = gtin_map.learn(session, GTIN, b.product_id, force=True)
    assert forced["product_id"] == b.product_id
    _clear(session)


def test_learn_rejects_invalid_gtin(session):
    product, _ = _two_products(session)
    for bad in ("P1000", "100", "4006358001239"):
        with pytest.raises(POSError) as exc:
            gtin_map.learn(session, bad, product.product_id)
        assert exc.value.code == "bad_gtin"


def test_resolve_learns_from_product_code(session):
    """An unmapped GTIN that matches Product.code is learned on first use."""
    product, _ = _two_products(session)
    _clear(session)
    original = product.code
    product.code = EAN13  # catalogue holds the EAN-13 form
    session.commit()
    try:
        found = gtin_map.resolve(session, GTIN)
        assert found is not None and found.product_id == product.product_id
        # ...and the inference was persisted, so the next scan is a direct hit.
        mapping = session.scalars(
            select(m.ProductBarcode).where(m.ProductBarcode.gtin == GTIN)
        ).first()
        assert mapping is not None and mapping.product_id == product.product_id
        assert mapping.source == "backfill"
    finally:
        product.code = original
        session.commit()
        _clear(session)


def test_resolve_returns_none_for_unknown(session):
    _clear(session)
    assert gtin_map.resolve(session, GTIN) is None
    assert gtin_map.resolve(session, "P1000") is None
    assert gtin_map.resolve(session, None) is None


def test_relink_repairs_stale_product_id(session):
    """A full eStock reload recreates product rows; product_code survives."""
    product, _ = _two_products(session)
    _clear(session)
    gtin_map.learn(session, GTIN, product.product_id)
    mapping = session.scalars(
        select(m.ProductBarcode).where(m.ProductBarcode.gtin == GTIN)
    ).first()
    assert mapping.product_code == product.code

    mapping.product_id = None  # simulate the post-wipe stale state
    session.commit()

    result = gtin_map.relink(session)
    assert result["relinked"] >= 1
    session.refresh(mapping)
    assert mapping.product_id == product.product_id
    _clear(session)


def test_backfill_preview_writes_nothing(session):
    """Dry run answers 'does product_code hold real GTINs?' without writing."""
    before = session.scalar(select(func.count()).select_from(m.ProductBarcode))
    report = gtin_map.backfill_from_code(session, dry_run=True)
    assert report["dry_run"] is True
    assert report["written"] == 0
    assert session.scalar(select(func.count()).select_from(m.ProductBarcode)) == before
    # The dev seed uses "P1000"-style codes, so nothing validates as a GTIN.
    # If this ever fails on real data that is GOOD news — it means the real
    # catalogue carries barcodes and the backfill can seed the map directly.
    assert report["valid_gtin"] == 0


def test_backfill_writes_when_code_is_a_real_gtin(session):
    product, _ = _two_products(session)
    _clear(session)
    original = product.code
    product.code = EAN13
    session.commit()
    try:
        before = session.scalar(select(func.count()).select_from(m.ProductBarcode))
        report = gtin_map.backfill_from_code(session, dry_run=False)
        assert report["written"] == 1
        after = session.scalar(select(func.count()).select_from(m.ProductBarcode))
        assert after == before + 1
    finally:
        product.code = original
        session.commit()
        _clear(session)


def test_unlink_is_idempotent(session):
    product, _ = _two_products(session)
    _clear(session)
    row = gtin_map.learn(session, GTIN, product.product_id)
    assert gtin_map.unlink(session, row["barcode_id"])["deleted"] is True
    assert gtin_map.unlink(session, row["barcode_id"])["deleted"] is False
