"""Two-phase transfer: request → ship (in_transit) → receive (confirm exp+qty)."""
from __future__ import annotations

from sqlalchemy import func, select

from app.db import models as m
from app.services import pos, transfers


def _two_branches(session):
    b = session.scalars(select(m.Branch)).all()
    return b[0].branch_id, b[1].branch_id


def _stocked(session, branch_id):
    row = session.execute(
        select(m.StockBatch.product_id).where(m.StockBatch.branch_id == branch_id, m.StockBatch.amount > 0)
    ).first()
    return row[0]


def _on_hand(session, pid, branch):
    return float(
        session.scalar(
            select(func.coalesce(func.sum(m.StockBatch.amount), 0)).where(
                m.StockBatch.product_id == pid, m.StockBatch.branch_id == branch
            )
        )
        or 0
    )


def test_ship_then_receive_full(session):
    src, dst = _two_branches(session)
    pid = _stocked(session, src)
    src0, dst0 = _on_hand(session, pid, src), _on_hand(session, pid, dst)

    req = transfers.request_transfer(session, src, dst, [(pid, 3)], requested_by=None)
    tid = req["transfer_id"]

    shipped = transfers.ship_transfer(session, tid)
    assert shipped["status"] == "in_transit"
    # Stock left the source, but has NOT yet entered the destination.
    assert _on_hand(session, pid, src) == src0 - 3
    assert _on_hand(session, pid, dst) == dst0
    # A receive task was raised for the destination branch.
    task = session.scalars(
        select(m.EmployeeTask).where(m.EmployeeTask.title.like(f"استلام تحويل #{tid} %"))
    ).first()
    assert task is not None and task.priority == "high"

    received = transfers.receive_transfer(session, tid)
    assert received["status"] == "received"
    assert _on_hand(session, pid, dst) == dst0 + 3
    # Receive task closed.
    task = session.scalars(
        select(m.EmployeeTask).where(m.EmployeeTask.title.like(f"استلام تحويل #{tid} %"))
    ).first()
    assert task.status == "done"


def test_receive_short_is_shrinkage(session):
    src, dst = _two_branches(session)
    pid = _stocked(session, src)
    dst0 = _on_hand(session, pid, dst)

    req = transfers.request_transfer(session, src, dst, [(pid, 4)], requested_by=None)
    tid = req["transfer_id"]
    transfers.ship_transfer(session, tid)

    detail = transfers.transfer_detail(session, tid)
    line_ids = [l["line_id"] for l in detail["lines"]]
    # Receive one less than shipped on the first line (breakage in transit).
    confirmations = {line_ids[0]: {"amount": max(detail["lines"][0]["amount"] - 1, 0)}}
    transfers.receive_transfer(session, tid, confirmations)
    # Destination gained (shipped - 1): shrinkage of exactly 1 unit.
    assert _on_hand(session, pid, dst) == dst0 + 3


def test_cannot_receive_before_ship(session):
    src, dst = _two_branches(session)
    pid = _stocked(session, src)
    req = transfers.request_transfer(session, src, dst, [(pid, 1)], requested_by=None)
    try:
        transfers.receive_transfer(session, req["transfer_id"])
        assert False, "cannot receive a requested (unshipped) transfer"
    except pos.POSError as e:
        assert e.code == "bad_status"


def test_api_ship_receive(client, session):
    src, dst = _two_branches(session)
    pid = _stocked(session, src)
    req = client.post(
        "/api/transfers/request",
        json={"from_branch_id": src, "to_branch_id": dst, "lines": [{"product_id": pid, "amount": 2}]},
    ).json()
    tid = req["transfer_id"]
    r = client.post(f"/api/transfers/{tid}/ship")
    assert r.status_code == 200 and r.json()["status"] == "in_transit"
    r = client.post(f"/api/transfers/{tid}/receive", json={"lines": []})
    assert r.status_code == 200 and r.json()["status"] == "received"
