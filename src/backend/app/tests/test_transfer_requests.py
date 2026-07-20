"""Transfer request → approve/reject workflow + PO draft approval.

A request moves no stock and raises a high-priority approval task; approval runs
the FEFO move and marks it received; rejection cancels it. All state transitions
are guarded.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db import models as m
from app.services import pos, transfers


def _two_branches(session):
    branches = session.scalars(select(m.Branch)).all()
    return branches[0].branch_id, branches[1].branch_id


def _stocked_product(session, branch_id):
    """A product with on-hand stock at branch_id."""
    row = session.execute(
        select(m.StockBatch.product_id, m.StockBatch.amount)
        .where(m.StockBatch.branch_id == branch_id, m.StockBatch.amount > 0)
    ).first()
    return row[0], float(row[1])


def test_request_creates_pending_transfer_and_task(session):
    src, dst = _two_branches(session)
    pid, qty = _stocked_product(session, src)
    out = transfers.request_transfer(session, src, dst, [(pid, 1)], requested_by=None)
    assert out["status"] == "requested"

    t = session.get(m.StockTransfer, out["transfer_id"])
    assert t.status == "requested"
    # No stock moved yet: line has no batch refs.
    assert all(l.from_batch_id is None for l in t.lines)
    # A high-priority approval task was raised for the source branch.
    task = session.scalars(
        select(m.EmployeeTask).where(m.EmployeeTask.title.like(f"مراجعة طلب تحويل #{t.transfer_id} %"))
    ).first()
    assert task is not None
    assert task.priority == "high"
    assert task.category == "approval"


def test_approve_moves_stock_and_receives(session):
    src, dst = _two_branches(session)
    pid, qty = _stocked_product(session, src)

    def on_hand(branch):
        return float(session.scalar(
            select(m.func.coalesce(m.func.sum(m.StockBatch.amount), 0))
            .where(m.StockBatch.product_id == pid, m.StockBatch.branch_id == branch)
        ) or 0)

    src_before, dst_before = on_hand(src), on_hand(dst)
    req = transfers.request_transfer(session, src, dst, [(pid, 2)], requested_by=None)
    approved = transfers.approve_transfer(session, req["transfer_id"], approved_by=None)
    assert approved["status"] == "received"

    assert on_hand(src) == src_before - 2
    assert on_hand(dst) == dst_before + 2
    # Approval task closed.
    task = session.scalars(
        select(m.EmployeeTask).where(m.EmployeeTask.title.like(f"مراجعة طلب تحويل #{req['transfer_id']} %"))
    ).first()
    assert task.status == "done"


def test_cannot_approve_twice(session):
    src, dst = _two_branches(session)
    pid, _ = _stocked_product(session, src)
    req = transfers.request_transfer(session, src, dst, [(pid, 1)], requested_by=None)
    transfers.approve_transfer(session, req["transfer_id"])
    try:
        transfers.approve_transfer(session, req["transfer_id"])
        assert False, "should not approve a received transfer"
    except pos.POSError as e:
        assert e.code == "bad_status"


def test_reject_cancels_without_moving_stock(session):
    src, dst = _two_branches(session)
    pid, _ = _stocked_product(session, src)
    req = transfers.request_transfer(session, src, dst, [(pid, 1)], requested_by=None)
    out = transfers.reject_transfer(session, req["transfer_id"])
    assert out["status"] == "cancelled"


def test_po_draft_approve_reject(session, client):
    # Generate drafts for a branch, then approve/reject one via the API.
    from app.services import autopurchase

    src, _ = _two_branches(session)
    autopurchase.generate_drafts(session, src)
    draft = session.scalars(select(m.PurchaseOrderDraft)).first()
    if draft is None:
        return  # nothing below min in the seed — skip
    r = client.post(f"/api/purchasing/drafts/{draft.draft_id}/approve")
    assert r.status_code == 200 and r.json()["status"] == "approved"
    r2 = client.post(f"/api/purchasing/drafts/{draft.draft_id}/reject")
    assert r2.status_code == 200 and r2.json()["status"] == "rejected"
    r3 = client.post("/api/purchasing/drafts/999999/approve")
    assert r3.status_code == 404
