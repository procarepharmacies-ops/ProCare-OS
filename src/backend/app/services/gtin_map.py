"""Scanned barcode -> product resolution, with a self-healing catalogue.

``Product.code`` mirrors whatever eStock's ``product_code`` holds. That may be a
real EAN/GTIN, an internal code ("P1000"), or nothing useful — it is not
guaranteed, so nothing here assumes it. Instead:

* ``resolve()`` tries the learned map first, then falls back to matching
  ``Product.code`` against every de-padded GTIN variant. A fallback hit is
  **auto-learned**, so the second scan of that pack takes the fast path.
* ``learn()`` records a mapping a human confirmed at the counter. It is
  idempotent by construction (unique index + same-product no-op), which is what
  makes it safe to replay from an offline queue with no idempotency key.
* ``relink()`` repairs ``product_id`` after a full eStock reload has deleted and
  recreated the product rows.

Together these mean the catalogue converges on correct barcodes through normal
use, instead of requiring a data-entry project up front.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services import gs1
from app.services.pos import POSError


def _row(b: m.ProductBarcode, product: m.Product | None = None) -> dict:
    return {
        "barcode_id": b.barcode_id,
        "gtin": b.gtin,
        "product_id": b.product_id,
        "product_code": b.product_code,
        "name_ar": product.name_ar if product is not None else None,
        "name_en": product.name_en if product is not None else None,
        "source": b.source,
        "created_by": b.created_by,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "last_seen_at": b.last_seen_at.isoformat() if b.last_seen_at else None,
        "seen_count": b.seen_count,
    }


def resolve(session: Session, gtin: str | None) -> m.Product | None:
    """Find the product a GTIN belongs to, learning the mapping when inferred."""
    gtin14 = gs1.normalize_gtin(gtin)
    if not gtin14:
        return None

    mapping = session.scalars(
        select(m.ProductBarcode).where(m.ProductBarcode.gtin == gtin14)
    ).first()
    if mapping is not None and mapping.product_id is not None:
        product = session.get(m.Product, mapping.product_id)
        if product is not None and not product.is_deleted:
            mapping.seen_count = (mapping.seen_count or 0) + 1
            mapping.last_seen_at = datetime.now()
            session.commit()
            return product

    # Not mapped (or mapped to a row a sync removed): try the catalogue's own
    # code column against every de-padded form of the GTIN.
    variants = gs1.gtin_variants(gtin14)
    if not variants:
        return None
    product = session.scalars(
        select(m.Product).where(
            m.Product.code.in_(variants),
            m.Product.is_deleted == False,  # noqa: E712
        )
    ).first()
    if product is None:
        return None

    # Learn what we just inferred so the next scan is a single indexed lookup.
    try:
        learn(session, gtin14, product.product_id, source="backfill")
    except POSError:
        session.rollback()  # a conflicting mapping exists — resolution still stands
    return product


def learn(
    session: Session,
    gtin: str | None,
    product_id: int,
    *,
    employee_id: int | None = None,
    source: str = "scan",
    force: bool = False,
) -> dict:
    """Map a GTIN to a product. Idempotent — safe to replay.

    * no row yet          -> insert
    * row, same product   -> bump seen_count only (no-op)
    * row, other product  -> ``POSError('gtin_taken')`` unless ``force``
    """
    gtin14 = gs1.normalize_gtin(gtin)
    if not gtin14:
        raise POSError("bad_gtin", "باركود غير صالح / not a valid GTIN")
    product = session.get(m.Product, product_id)
    if product is None or product.is_deleted:
        raise POSError("product_not_found", f"الصنف غير موجود #{product_id} / product not found")

    existing = session.scalars(
        select(m.ProductBarcode).where(m.ProductBarcode.gtin == gtin14)
    ).first()
    now = datetime.now()

    if existing is None:
        row = m.ProductBarcode(
            gtin=gtin14,
            product_id=product.product_id,
            product_code=product.code,
            source=source,
            created_by=employee_id,
            last_seen_at=now,
            seen_count=1,
        )
        session.add(row)
        session.commit()
        return {"ok": True, "created": True, **_row(row, product)}

    if existing.product_id == product.product_id:
        existing.seen_count = (existing.seen_count or 0) + 1
        existing.last_seen_at = now
        existing.product_code = product.code  # keep the durable key fresh
        session.commit()
        return {"ok": True, "created": False, **_row(existing, product)}

    if not force:
        other = session.get(m.Product, existing.product_id) if existing.product_id else None
        raise POSError(
            "gtin_taken",
            "الباركود مرتبط بصنف آخر: "
            f"{other.name_ar if other is not None else existing.product_id}"
            " / barcode already linked to another product",
        )

    existing.product_id = product.product_id
    existing.product_code = product.code
    existing.source = source
    existing.created_by = employee_id
    existing.last_seen_at = now
    session.commit()
    return {"ok": True, "created": False, "repointed": True, **_row(existing, product)}


def unlink(session: Session, barcode_id: int) -> dict:
    """Remove a mapping (a mis-link fixed by a manager). Idempotent."""
    row = session.get(m.ProductBarcode, barcode_id)
    if row is None:
        return {"ok": True, "deleted": False}
    session.delete(row)
    session.commit()
    return {"ok": True, "deleted": True}


def relink(session: Session) -> dict:
    """Re-resolve ``product_id`` from ``product_code`` after a full eStock load.

    A full mirror deletes and recreates every product row, so previously-valid
    ``product_id`` values go stale. ``product_code`` is what the ETL dedupes on,
    so it survives. Fail-soft: bookkeeping must never break a sync.
    """
    fixed = orphaned = 0
    try:
        rows = session.scalars(
            select(m.ProductBarcode).where(m.ProductBarcode.product_code.is_not(None))
        ).all()
        if not rows:
            return {"checked": 0, "relinked": 0, "orphaned": 0}
        codes = {r.product_code for r in rows}
        by_code = {
            p.code: p
            for p in session.scalars(
                select(m.Product).where(
                    m.Product.code.in_(codes),
                    m.Product.is_deleted == False,  # noqa: E712
                )
            ).all()
        }
        for r in rows:
            product = by_code.get(r.product_code)
            if product is None:
                if r.product_id is not None:
                    r.product_id = None
                    orphaned += 1
            elif r.product_id != product.product_id:
                r.product_id = product.product_id
                fixed += 1
        session.commit()
        return {"checked": len(rows), "relinked": fixed, "orphaned": orphaned}
    except Exception:
        session.rollback()
        return {"checked": 0, "relinked": 0, "orphaned": 0, "error": True}


def backfill_from_code(
    session: Session, *, dry_run: bool = True, limit: int | None = None
) -> dict:
    """Seed the map from ``Product.code`` wherever it is already a valid GTIN.

    This is also the **verification step** for the open question "does eStock's
    product_code actually hold barcodes?". With ``dry_run`` (the default) nothing
    is written and the counts answer it: ``valid_gtin == 0`` means the catalogue
    carries internal codes and learn-on-scan must build the map instead.
    """
    stmt = select(m.Product).where(
        m.Product.code.is_not(None),
        m.Product.is_deleted == False,  # noqa: E712
    )
    if limit:
        stmt = stmt.limit(limit)  # .limit() only — .offset() breaks SQL Server 2008
    products = session.scalars(stmt).all()

    existing = {
        b.gtin: b.product_id
        for b in session.scalars(select(m.ProductBarcode)).all()
    }
    valid = already = written = 0
    conflicts: list[dict] = []
    samples: list[dict] = []

    for p in products:
        gtin14 = gs1.normalize_gtin(p.code)
        if not gtin14:
            continue
        valid += 1
        if len(samples) < 20:
            samples.append({"product_id": p.product_id, "code": p.code, "gtin": gtin14})
        owner = existing.get(gtin14)
        if owner is not None:
            if owner == p.product_id:
                already += 1
            else:
                conflicts.append(
                    {"gtin": gtin14, "product_id": p.product_id, "mapped_to": owner}
                )
            continue
        if not dry_run:
            session.add(
                m.ProductBarcode(
                    gtin=gtin14,
                    product_id=p.product_id,
                    product_code=p.code,
                    source="backfill",
                    seen_count=0,
                )
            )
            existing[gtin14] = p.product_id
            written += 1
    if not dry_run and written:
        session.commit()

    return {
        "dry_run": dry_run,
        "products": len(products),
        "valid_gtin": valid,
        "already_mapped": already,
        "written": written,
        "conflicts": conflicts[:50],
        "conflict_count": len(conflicts),
        "samples": samples,
    }


def recent(
    session: Session, *, source: str | None = None, limit: int = 200
) -> list[dict]:
    """Review feed for managers: what staff have linked, newest first."""
    stmt = select(m.ProductBarcode).order_by(m.ProductBarcode.barcode_id.desc()).limit(limit)
    if source:
        stmt = stmt.where(m.ProductBarcode.source == source)
    rows = session.scalars(stmt).all()
    products = {
        p.product_id: p
        for p in session.scalars(
            select(m.Product).where(
                m.Product.product_id.in_({r.product_id for r in rows if r.product_id})
            )
        ).all()
    } if rows else {}
    return [_row(r, products.get(r.product_id)) for r in rows]
