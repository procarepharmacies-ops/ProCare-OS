"""Phase 6 derived alarm: البيع بأقل من التكلفة (selling at or below cost).

Every case builds its own products/batches with exact prices and tears them
down, so the assertions are on arithmetic we control rather than on whatever
the shared seed happens to contain.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.db import models as m
from app.db.base import SessionLocal
from app.services import alerts
from app.services import notifications as notif

_MARK = "ZZ-BELOWCOST-"  # product code prefix, so cleanup can find our rows


def _product(s, code: str, *, sell: float, buy: float) -> m.Product:
    p = m.Product(
        code=_MARK + code,
        name_ar=f"صنف {code}",
        name_en=f"Item {code}",
        sell_price=sell,
        buy_price=buy,
        is_active=True,
        is_deleted=False,
    )
    s.add(p)
    s.flush()
    return p


def _batch(s, product_id: int, branch_id: int, *, amount: float, buy: float) -> None:
    # exp_date left NULL: available_stock_filter() treats NULL as never-expired,
    # so these batches are sellable regardless of the business clock.
    s.add(m.StockBatch(product_id=product_id, branch_id=branch_id, amount=amount, buy_price=buy))


@pytest.fixture
def branch_id() -> int:
    with SessionLocal() as s:
        return s.scalars(select(m.Branch.branch_id)).first()


@pytest.fixture(autouse=True)
def cleanup():
    """Remove this module's rows (and any dismissals) after every test."""
    yield
    with SessionLocal() as s:
        pids = list(
            s.scalars(select(m.Product.product_id).where(m.Product.code.like(_MARK + "%"))).all()
        )
        if pids:
            s.execute(delete(m.StockBatch).where(m.StockBatch.product_id.in_(pids)))
            s.execute(delete(m.Product).where(m.Product.product_id.in_(pids)))
        s.execute(delete(m.NotificationDismissal))
        s.commit()


def _find(result: dict, product_id: int) -> dict | None:
    return next((i for i in result["items"] if i["product_id"] == product_id), None)


def test_below_cost_item_with_stock_is_flagged_with_exact_exposure(branch_id):
    with SessionLocal() as s:
        p = _product(s, "LOSS", sell=8.0, buy=10.0)
        _batch(s, p.product_id, branch_id, amount=20, buy=10.0)
        s.commit()
        pid = p.product_id

        row = _find(alerts.below_cost(s, branch_id), pid)

    assert row is not None, "an item selling under cost must be reported"
    assert row["reason"] == "below_cost"
    assert row["severity"] == "critical"  # stock on hand = real money bleeding
    assert row["cost"] == 10.0
    assert row["loss_per_unit"] == 2.0
    assert row["on_hand"] == 20.0
    assert row["exposure"] == 40.0  # 2 EGP lost x 20 units still on the shelf


def test_healthy_margin_is_not_flagged(branch_id):
    with SessionLocal() as s:
        p = _product(s, "OK", sell=15.0, buy=10.0)
        _batch(s, p.product_id, branch_id, amount=5, buy=10.0)
        s.commit()
        assert _find(alerts.below_cost(s, branch_id), p.product_id) is None


def test_zero_margin_is_flagged_but_only_as_a_warning(branch_id):
    """Selling exactly at cost loses nothing today, but leaves no room for the
    next vendor price rise — worth seeing, not worth alarming."""
    with SessionLocal() as s:
        p = _product(s, "FLAT", sell=10.0, buy=10.0)
        _batch(s, p.product_id, branch_id, amount=5, buy=10.0)
        s.commit()

        row = _find(alerts.below_cost(s, branch_id), p.product_id)

    assert row is not None
    assert row["reason"] == "zero_margin"
    assert row["severity"] == "warning"
    assert row["loss_per_unit"] == 0.0


def test_unpriced_item_that_still_has_stock_is_flagged(branch_id):
    """sell_price = 0 rings the item up free at the POS — the whole cost is lost."""
    with SessionLocal() as s:
        p = _product(s, "FREE", sell=0.0, buy=12.0)
        _batch(s, p.product_id, branch_id, amount=3, buy=12.0)
        s.commit()

        row = _find(alerts.below_cost(s, branch_id), p.product_id)

    assert row is not None
    assert row["reason"] == "unpriced"
    assert row["severity"] == "critical"
    assert row["exposure"] == 36.0


def test_item_with_no_cost_on_file_is_never_flagged(branch_id):
    """buy_price 0 with no stock value is missing data, not a loss — flagging it
    would bury the real ones under every unpriced catalogue row."""
    with SessionLocal() as s:
        p = _product(s, "NOCOST", sell=0.0, buy=0.0)
        _batch(s, p.product_id, branch_id, amount=4, buy=0.0)
        s.commit()
        assert _find(alerts.below_cost(s, branch_id), p.product_id) is None


def test_cost_is_the_weighted_average_of_the_batches_we_actually_hold(branch_id):
    """The catalogue price can be stale; what binds is what we paid for the
    stock on the shelf. 10 @ 9 + 30 @ 13 -> 12.0 average, above the 11 sell."""
    with SessionLocal() as s:
        p = _product(s, "WAVG", sell=11.0, buy=9.0)  # catalogue still says 9
        _batch(s, p.product_id, branch_id, amount=10, buy=9.0)
        _batch(s, p.product_id, branch_id, amount=30, buy=13.0)
        s.commit()

        row = _find(alerts.below_cost(s, branch_id), p.product_id)

    assert row is not None, "a vendor price rise not passed on must surface"
    assert row["cost"] == 12.0                # weighted average, not the 9 on file
    assert row["catalogue_buy_price"] == 9.0  # the stale price is reported too
    assert row["loss_per_unit"] == 1.0
    assert row["exposure"] == 40.0            # 1.0 x 40 units on hand


def test_price_list_errors_with_no_stock_are_opt_in(branch_id):
    with SessionLocal() as s:
        p = _product(s, "NOSTOCK", sell=5.0, buy=9.0)
        s.commit()
        pid = p.product_id

        assert _find(alerts.below_cost(s, branch_id), pid) is None

        row = _find(alerts.below_cost(s, branch_id, include_zero_stock=True), pid)
        assert row is not None
        assert row["cost"] == 9.0        # falls back to the catalogue price
        assert row["on_hand"] == 0.0
        assert row["exposure"] == 0.0    # nothing at risk yet
        assert row["severity"] == "warning"


def test_totals_and_ordering_put_the_biggest_bleeder_first(branch_id):
    with SessionLocal() as s:
        small = _product(s, "SMALL", sell=9.0, buy=10.0)   # 1 x 2  =  2
        big = _product(s, "BIG", sell=50.0, buy=60.0)      # 10 x 5 = 50
        _batch(s, small.product_id, branch_id, amount=2, buy=10.0)
        _batch(s, big.product_id, branch_id, amount=5, buy=60.0)
        s.commit()

        result = alerts.below_cost(s, branch_id)
        ours = [i for i in result["items"] if (i["code"] or "").startswith(_MARK)]

    assert [i["exposure"] for i in ours] == [50.0, 2.0]
    assert result["total_exposure"] >= 52.0
    assert result["count"] == len(result["items"])


def test_below_cost_reaches_the_notification_center_and_can_be_dismissed(branch_id):
    with SessionLocal() as s:
        p = _product(s, "NOTIF", sell=8.0, buy=10.0)
        _batch(s, p.product_id, branch_id, amount=20, buy=10.0)
        s.commit()
        pid = p.product_id

        center = notif.notification_center(s, branch_id=branch_id)
        group = next(g for g in center["groups"] if g["category"] == "below_cost")
        assert group["label_ar"] and group["label_en"]
        key = f"below_cost:{pid}:{branch_id}"
        assert any(i["key"] == key for i in group["items"])

        notif.dismiss(s, [key], branch_id=branch_id)
        after = notif.notification_center(s, branch_id=branch_id)
        after_group = next(g for g in after["groups"] if g["category"] == "below_cost")
        assert all(i["key"] != key for i in after_group["items"])


def test_zero_stock_rows_never_reach_the_feed(branch_id):
    """The alarm reports price-list errors on request; the feed must not, or a
    catalogue-wide pricing drift would drown the items actually losing money."""
    with SessionLocal() as s:
        p = _product(s, "FEEDNOSTOCK", sell=5.0, buy=9.0)
        s.commit()
        events = notif._below_cost_events(s, branch_id)
        assert all(e["ref_id"] != p.product_id for e in events)


def test_api_returns_below_cost_items(client, branch_id):
    with SessionLocal() as s:
        p = _product(s, "API", sell=8.0, buy=10.0)
        _batch(s, p.product_id, branch_id, amount=20, buy=10.0)
        s.commit()
        pid = p.product_id

    r = client.get("/api/alerts/below-cost", params={"branch_id": branch_id})
    assert r.status_code == 200
    body = r.json()
    row = _find(body, pid)
    assert row is not None
    assert row["exposure"] == 40.0
    assert body["total_exposure"] >= 40.0
