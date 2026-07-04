"""Branch treasury service — cash vouchers, inter-branch money transfers, and
per-branch balance accounts (eStock parity: Branch_money_order 1,102 rows /
Branch_money_convert 1,098 rows / Gedo_branches 9,271 rows / Cash_depots).

Everything is expressed as ``ledger_entries`` rows on the ``cash`` account of a
branch, so the branch balance is always derivable and auditable:

    balance(branch) = opening 0 + Σ debit − Σ credit  on account_type='cash'

* ``receive_voucher``  — money INTO the branch treasury  (ledger debit)
* ``pay_voucher``      — money OUT of the branch treasury (ledger credit)
* ``transfer_money``   — atomic branch→branch move: credit source, debit
                         destination, plus one TreasuryTransfer document row.
* ``adjust_balance``   — signed correction with a mandatory note (audit).
* ``branch_balances``  — the live balance per branch + activity counts.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import money
from app.services.pos import POSError


def _branch(session: Session, branch_id: int) -> m.Branch:
    b = session.get(m.Branch, branch_id)
    if b is None:
        raise POSError("branch_not_found", f"الفرع غير موجود #{branch_id} / branch not found")
    return b


def _cash_entry(branch_id: int, *, debit: float = 0.0, credit: float = 0.0,
                ref_type: str, ref_id: int | None = None, note: str | None = None) -> m.LedgerEntry:
    return m.LedgerEntry(
        branch_id=branch_id,
        account_type="cash",
        ref_type=ref_type,
        ref_id=ref_id,
        debit=debit,
        credit=credit,
        note=note,
    )


def receive_voucher(
    session: Session, branch_id: int, amount: float, *,
    note: str | None = None, employee_id: int | None = None, party: str | None = None,
) -> dict:
    """Cash received INTO the branch treasury (from a customer payment, the
    owner, another safe...). One auditable ledger debit."""
    if amount <= 0:
        raise POSError("bad_amount", "المبلغ يجب أن يكون أكبر من صفر / amount must be positive")
    _branch(session, branch_id)
    full_note = " / ".join(x for x in ("سند قبض", party, note) if x)
    entry = _cash_entry(branch_id, debit=float(amount), ref_type="treasury_in", note=full_note)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return {"entry_id": entry.entry_id, "branch_id": branch_id, "amount": money(amount), "kind": "receive"}


def pay_voucher(
    session: Session, branch_id: int, amount: float, *,
    note: str | None = None, employee_id: int | None = None, party: str | None = None,
) -> dict:
    """Cash paid OUT of the branch treasury (expense, vendor cash payment,
    owner draw...). Refuses to overdraw the treasury."""
    if amount <= 0:
        raise POSError("bad_amount", "المبلغ يجب أن يكون أكبر من صفر / amount must be positive")
    _branch(session, branch_id)
    bal = branch_balance(session, branch_id)
    if amount > bal + 1e-9:
        raise POSError(
            "insufficient_treasury",
            f"رصيد الخزينة غير كافٍ: متاح {money(bal)} مطلوب {money(amount)} / insufficient treasury balance",
        )
    full_note = " / ".join(x for x in ("سند صرف", party, note) if x)
    entry = _cash_entry(branch_id, credit=float(amount), ref_type="treasury_out", note=full_note)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return {"entry_id": entry.entry_id, "branch_id": branch_id, "amount": money(amount), "kind": "pay"}


def transfer_money(
    session: Session, from_branch_id: int, to_branch_id: int, amount: float, *,
    note: str | None = None, employee_id: int | None = None,
) -> dict:
    """Atomic treasury→treasury move between branches: one document row plus
    two balanced cash-ledger entries. All-or-nothing."""
    if from_branch_id == to_branch_id:
        raise POSError("same_branch", "لا يمكن التحويل لنفس الفرع / cannot transfer to the same branch")
    if amount <= 0:
        raise POSError("bad_amount", "المبلغ يجب أن يكون أكبر من صفر / amount must be positive")
    _branch(session, from_branch_id)
    _branch(session, to_branch_id)
    bal = branch_balance(session, from_branch_id)
    if amount > bal + 1e-9:
        raise POSError(
            "insufficient_treasury",
            f"رصيد خزينة الفرع المرسل غير كافٍ: متاح {money(bal)} مطلوب {money(amount)}",
        )
    try:
        doc = m.TreasuryTransfer(
            from_branch_id=from_branch_id,
            to_branch_id=to_branch_id,
            amount=float(amount),
            note=note,
            created_by=employee_id,
        )
        session.add(doc)
        session.flush()
        session.add(_cash_entry(
            from_branch_id, credit=float(amount), ref_type="treasury_transfer",
            ref_id=doc.transfer_id, note=f"تحويل نقدية إلى فرع #{to_branch_id}" + (f" / {note}" if note else ""),
        ))
        session.add(_cash_entry(
            to_branch_id, debit=float(amount), ref_type="treasury_transfer",
            ref_id=doc.transfer_id, note=f"تحويل نقدية من فرع #{from_branch_id}" + (f" / {note}" if note else ""),
        ))
        session.commit()
        session.refresh(doc)
        return {
            "transfer_id": doc.transfer_id,
            "from_branch_id": from_branch_id,
            "to_branch_id": to_branch_id,
            "amount": money(amount),
        }
    except Exception:
        session.rollback()
        raise


def adjust_balance(
    session: Session, branch_id: int, delta: float, *, note: str, employee_id: int | None = None,
) -> dict:
    """Signed treasury correction (stocktake of the safe, opening balance...).
    A note is mandatory — this is the audit trail for manual changes."""
    if not note or not note.strip():
        raise POSError("note_required", "سبب التسوية مطلوب / adjustment note is required")
    if delta == 0:
        raise POSError("bad_amount", "قيمة التسوية لا يمكن أن تكون صفراً / delta cannot be zero")
    _branch(session, branch_id)
    entry = _cash_entry(
        branch_id,
        debit=float(delta) if delta > 0 else 0.0,
        credit=-float(delta) if delta < 0 else 0.0,
        ref_type="treasury_adjust",
        note=f"تسوية خزينة: {note}",
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return {"entry_id": entry.entry_id, "branch_id": branch_id, "delta": money(delta)}


def branch_balance(session: Session, branch_id: int) -> float:
    """Live cash balance of one branch treasury from the ledger."""
    debit, credit = session.execute(
        select(
            func.coalesce(func.sum(m.LedgerEntry.debit), 0),
            func.coalesce(func.sum(m.LedgerEntry.credit), 0),
        ).where(
            m.LedgerEntry.branch_id == branch_id,
            m.LedgerEntry.account_type == "cash",
        )
    ).one()
    return money(float(debit) - float(credit))


def branch_balances(session: Session) -> list[dict]:
    """Balance + activity per branch — the branch balance accounts screen."""
    branches = session.scalars(select(m.Branch).order_by(m.Branch.branch_id)).all()
    rows = session.execute(
        select(
            m.LedgerEntry.branch_id,
            func.coalesce(func.sum(m.LedgerEntry.debit), 0),
            func.coalesce(func.sum(m.LedgerEntry.credit), 0),
            func.count(),
        )
        .where(m.LedgerEntry.account_type == "cash")
        .group_by(m.LedgerEntry.branch_id)
    ).all()
    by_branch = {bid: (float(d), float(c), n) for bid, d, c, n in rows}
    out = []
    for b in branches:
        d, c, n = by_branch.get(b.branch_id, (0.0, 0.0, 0))
        out.append(
            {
                "branch_id": b.branch_id,
                "name_ar": b.name_ar,
                "name_en": b.name_en,
                "cash_in": money(d),
                "cash_out": money(c),
                "balance": money(d - c),
                "entries": n,
            }
        )
    return out


def list_transfers(session: Session, branch_id: int | None = None, limit: int = 100) -> list[dict]:
    q = select(m.TreasuryTransfer).order_by(m.TreasuryTransfer.created_at.desc())
    if branch_id:
        q = q.where(
            (m.TreasuryTransfer.from_branch_id == branch_id) | (m.TreasuryTransfer.to_branch_id == branch_id)
        )
    names = {b.branch_id: b.name_ar for b in session.scalars(select(m.Branch)).all()}
    return [
        {
            "transfer_id": t.transfer_id,
            "from_branch_id": t.from_branch_id,
            "from_branch_name": names.get(t.from_branch_id, "?"),
            "to_branch_id": t.to_branch_id,
            "to_branch_name": names.get(t.to_branch_id, "?"),
            "amount": money(t.amount),
            "note": t.note,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in session.scalars(q.limit(limit)).all()
    ]


def recent_movements(session: Session, branch_id: int | None = None, limit: int = 100) -> list[dict]:
    """Recent treasury (cash-account) ledger lines — the treasury statement."""
    q = (
        select(m.LedgerEntry)
        .where(m.LedgerEntry.account_type == "cash")
        .order_by(m.LedgerEntry.entry_date.desc(), m.LedgerEntry.entry_id.desc())
    )
    if branch_id:
        q = q.where(m.LedgerEntry.branch_id == branch_id)
    return [
        {
            "entry_id": e.entry_id,
            "branch_id": e.branch_id,
            "entry_date": e.entry_date.isoformat() if e.entry_date else None,
            "ref_type": e.ref_type,
            "ref_id": e.ref_id,
            "debit": money(e.debit),
            "credit": money(e.credit),
            "note": e.note,
        }
        for e in session.scalars(q.limit(limit)).all()
    ]
