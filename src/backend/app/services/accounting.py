"""Financial accounting and ledger endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import models as m


def list_ledger_entries(
    session: Session,
    branch_id: int | None = None,
    account_type: str | None = None,
    days: int = 30,
    limit: int = 500,
) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=days)
    q = select(m.LedgerEntry).where(m.LedgerEntry.entry_date >= cutoff).order_by(m.LedgerEntry.entry_date.desc())

    if branch_id:
        q = q.where(m.LedgerEntry.branch_id == branch_id)
    if account_type:
        q = q.where(m.LedgerEntry.account_type == account_type)

    rows = session.scalars(q.limit(limit)).all()
    return [
        {
            "entry_id": e.entry_id,
            "branch_id": e.branch_id,
            "entry_date": e.entry_date.isoformat() if e.entry_date else None,
            "account_type": e.account_type,
            "account_ref": e.account_ref,
            "ref_type": e.ref_type,
            "ref_id": e.ref_id,
            "debit": float(e.debit or 0),
            "credit": float(e.credit or 0),
            "note": e.note,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in rows
    ]


def trial_balance(session: Session, branch_id: int | None = None) -> dict:
    q = select(
        m.LedgerEntry.account_type,
        m.LedgerEntry.account_ref,
        func.sum(m.LedgerEntry.debit).label("total_debit"),
        func.sum(m.LedgerEntry.credit).label("total_credit"),
    ).group_by(m.LedgerEntry.account_type, m.LedgerEntry.account_ref)

    if branch_id:
        q = q.where(m.LedgerEntry.branch_id == branch_id)

    rows = session.execute(q).all()

    accounts = {}
    for account_type, account_ref, total_debit, total_credit in rows:
        key = f"{account_type}:{account_ref}" if account_ref else account_type
        accounts[key] = {
            "type": account_type,
            "ref": account_ref,
            "debit": float(total_debit or 0),
            "credit": float(total_credit or 0),
            "balance": float((total_debit or 0) - (total_credit or 0)),
        }

    return {
        "accounts": accounts,
        "total_debit": sum(a["debit"] for a in accounts.values()),
        "total_credit": sum(a["credit"] for a in accounts.values()),
    }


_ACCOUNT_TYPE_LABELS = {
    "customer": "العملاء",
    "vendor": "الموردون",
    "cash": "النقدية (الخزينة)",
    "bank": "البنوك",
    "branch": "الفروع",
    "general": "حسابات عامة",
}

_ACCOUNT_TYPES = ("customer", "vendor", "cash", "bank", "branch", "general")

# Named adjustment reasons — eStock's Tuning_accounts (تسويات) reason list.
# A manual journal entry tagged with one of these is an *adjustment*
# (ref_type='adjust'); the code is stored on the ledger row so the
# adjustments report can group by reason. Bilingual so the UI reads in either
# language and the reports stay legible.
ADJUSTMENT_REASONS = [
    {"code": "opening_balance", "ar": "رصيد افتتاحي", "en": "Opening balance"},
    {"code": "discount_allowed", "ar": "خصم مسموح به", "en": "Discount allowed"},
    {"code": "bad_debt", "ar": "ديون معدومة", "en": "Bad debt write-off"},
    {"code": "inventory_writeoff", "ar": "إهلاك / تلف مخزون", "en": "Inventory write-off"},
    {"code": "cash_short", "ar": "عجز خزينة", "en": "Cash shortage"},
    {"code": "cash_over", "ar": "زيادة خزينة", "en": "Cash overage"},
    {"code": "expense", "ar": "مصروف نثري", "en": "Petty expense"},
    {"code": "correction", "ar": "تصحيح قيد", "en": "Entry correction"},
    {"code": "other", "ar": "أخرى", "en": "Other"},
]
_REASON_BY_CODE = {r["code"]: r for r in ADJUSTMENT_REASONS}


def adjustment_reasons() -> list[dict]:
    """The Tuning_accounts (تسويات) reason catalogue for the manual-adjustment UI."""
    return ADJUSTMENT_REASONS


def chart_of_accounts(session: Session, branch_id: int | None = None) -> dict:
    """شجرة الحسابات — the account tree grouped by type, each type carrying its
    sub-accounts with resolved names (customer/vendor/branch) and net balance.
    Builds on the trial-balance aggregation, adding readable names + Arabic
    group headers so it reads like eStock's chart of accounts."""
    tb = trial_balance(session, branch_id)
    # Resolve names for the ref-bearing account types in one pass each.
    cust_names = dict(session.execute(select(m.Customer.customer_id, m.Customer.name_ar)).all())
    vend_names = dict(session.execute(select(m.Vendor.vendor_id, m.Vendor.name_ar)).all())
    branch_names = dict(session.execute(select(m.Branch.branch_id, m.Branch.name_ar)).all())

    groups: dict[str, dict] = {}
    for acc in tb["accounts"].values():
        atype = acc["type"]
        g = groups.setdefault(
            atype,
            {
                "type": atype,
                "label": _ACCOUNT_TYPE_LABELS.get(atype, atype),
                "debit": 0.0,
                "credit": 0.0,
                "balance": 0.0,
                "accounts": [],
            },
        )
        ref = acc["ref"]
        name = None
        if ref is not None:
            if atype == "customer":
                name = cust_names.get(ref)
            elif atype == "vendor":
                name = vend_names.get(ref)
            elif atype == "branch":
                name = branch_names.get(ref)
        g["accounts"].append({**acc, "name": name or (f"#{ref}" if ref else g["label"])})
        g["debit"] += acc["debit"]
        g["credit"] += acc["credit"]
        g["balance"] += acc["balance"]

    ordered = [groups[k] for k in _ACCOUNT_TYPE_LABELS if k in groups]
    ordered += [g for k, g in groups.items() if k not in _ACCOUNT_TYPE_LABELS]
    for g in ordered:
        g["accounts"].sort(key=lambda a: abs(a["balance"]), reverse=True)
    return {
        "groups": ordered,
        "total_debit": tb["total_debit"],
        "total_credit": tb["total_credit"],
        "balanced": abs(tb["total_debit"] - tb["total_credit"]) < 0.01,
    }


def account_balance(session: Session, account_type: str, account_ref: int | None = None) -> dict:
    q = select(
        func.sum(m.LedgerEntry.debit).label("total_debit"),
        func.sum(m.LedgerEntry.credit).label("total_credit"),
    ).where(m.LedgerEntry.account_type == account_type)

    if account_ref is not None:
        q = q.where(m.LedgerEntry.account_ref == account_ref)

    row = session.execute(q).one_or_none()
    if not row:
        return {"account_type": account_type, "account_ref": account_ref, "debit": 0, "credit": 0, "balance": 0}

    total_debit, total_credit = row
    total_debit = float(total_debit or 0)
    total_credit = float(total_credit or 0)

    return {
        "account_type": account_type,
        "account_ref": account_ref,
        "debit": total_debit,
        "credit": total_credit,
        "balance": total_debit - total_credit,
    }


def profit_loss(session: Session, branch_id: int | None = None, days: int = 30) -> dict:
    """Gross P&L over a period — eStock's profit rule re-implemented cleanly:
    gross_profit = Σ total_sell − Σ(amount × buy_price) at the LINE level
    (cost captured at sale time, not current product cost), with return
    invoices reversing both revenue and cost."""
    cutoff = datetime.now() - timedelta(days=days)

    def _lines_totals(is_return: bool) -> tuple[float, float]:
        q = (
            select(
                func.coalesce(func.sum(m.SaleLine.total_sell), 0),
                func.coalesce(func.sum(m.SaleLine.amount * m.SaleLine.buy_price), 0),
            )
            .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
            .where(m.Sale.is_return == is_return, m.Sale.sale_date >= cutoff)
        )
        if branch_id:
            q = q.where(m.Sale.branch_id == branch_id)
        revenue, cogs = session.execute(q).one()
        return float(revenue or 0), float(cogs or 0)

    revenue, cogs = _lines_totals(is_return=False)
    returns_refund, returns_cogs = _lines_totals(is_return=True)

    net_revenue = round(revenue - returns_refund, 2)
    net_cogs = round(cogs - returns_cogs, 2)
    gross_profit = round(net_revenue - net_cogs, 2)
    return {
        "period_days": days,
        "branch_id": branch_id,
        "revenue": round(revenue, 2),
        "returns_refund": round(returns_refund, 2),
        "net_revenue": net_revenue,
        "cogs": net_cogs,
        "gross_profit": gross_profit,
        "margin_pct": round(gross_profit / net_revenue * 100, 1) if net_revenue else 0.0,
    }


def sales_summary(session: Session, branch_id: int | None = None, days: int = 30) -> dict:
    cutoff = datetime.now() - timedelta(days=days)

    base_sales = select(func.sum(m.Sale.total_net)).where(
        m.Sale.is_return == False,  # noqa: E712
        m.Sale.sale_date >= cutoff,
    )
    base_returns = select(func.sum(m.Sale.total_net)).where(
        m.Sale.is_return == True,  # noqa: E712
        m.Sale.sale_date >= cutoff,
    )
    base_count = select(func.count()).select_from(m.Sale).where(
        m.Sale.is_return == False,  # noqa: E712
        m.Sale.sale_date >= cutoff,
    )

    # Paid amounts by payment type over the same non-return window. Cash
    # received nets out any change handed back (change_given is 0 for POS
    # sales but populated on ETL-imported sales).
    base_paid = select(
        func.coalesce(func.sum(m.Sale.cash_paid - m.Sale.change_given), 0),
        func.coalesce(func.sum(m.Sale.card_paid), 0),
    ).where(
        m.Sale.is_return == False,  # noqa: E712
        m.Sale.sale_date >= cutoff,
    )
    base_credit = select(func.coalesce(func.sum(m.Sale.total_net), 0)).where(
        m.Sale.is_return == False,  # noqa: E712
        m.Sale.is_credit == True,  # noqa: E712
        m.Sale.sale_date >= cutoff,
    )
    # Cash paid back out on returns. Return invoices don't carry cash_paid,
    # so we treat non-credit (cash-settled) returns as cash out of the
    # drawer; credit returns adjust the customer balance, not the till.
    base_cash_refunds = select(func.coalesce(func.sum(m.Sale.total_net), 0)).where(
        m.Sale.is_return == True,  # noqa: E712
        m.Sale.is_credit == False,  # noqa: E712
        m.Sale.sale_date >= cutoff,
    )

    if branch_id:
        base_sales = base_sales.where(m.Sale.branch_id == branch_id)
        base_returns = base_returns.where(m.Sale.branch_id == branch_id)
        base_count = base_count.where(m.Sale.branch_id == branch_id)
        base_paid = base_paid.where(m.Sale.branch_id == branch_id)
        base_credit = base_credit.where(m.Sale.branch_id == branch_id)
        base_cash_refunds = base_cash_refunds.where(m.Sale.branch_id == branch_id)

    total_sales = float(session.scalar(base_sales) or 0)
    total_returns = float(session.scalar(base_returns) or 0)
    num_sales = int(session.scalar(base_count) or 0)
    cash_paid_row, card_paid_row = session.execute(base_paid).one()
    cash_paid = round(float(cash_paid_row or 0), 2)
    card_paid = round(float(card_paid_row or 0), 2)
    credit_sales = round(float(session.scalar(base_credit) or 0), 2)
    cash_refunds = round(float(session.scalar(base_cash_refunds) or 0), 2)

    return {
        "period_days": days,
        "total_sales_net": total_sales,
        "total_returns_net": total_returns,
        "num_sales": num_sales,
        "net_revenue": total_sales - total_returns,
        "avg_sale_value": round(total_sales / num_sales, 2) if num_sales else 0.0,
        "cash_paid": cash_paid,
        "card_paid": card_paid,
        "total_paid": round(cash_paid + card_paid, 2),
        "credit_sales": credit_sales,
        "cash_refunds": cash_refunds,
        "net_cash": round(cash_paid - cash_refunds, 2),
    }


def create_journal_entry(
    session: Session,
    branch_id: int,
    account_type: str,
    *,
    debit: float = 0.0,
    credit: float = 0.0,
    account_ref: int | None = None,
    note: str | None = None,
    reason_code: str | None = None,
) -> dict:
    """Manual journal entry (eStock's Tuning_accounts — manual adjustments).
    One-sided by design, matching the source system.

    When ``reason_code`` is given it must be a known Tuning reason; the entry is
    then tagged as an *adjustment* (``ref_type='adjust'``) and the code is stored
    so the adjustments report can group by it. Without a reason it stays a plain
    ``ref_type='manual'`` posting (backwards-compatible)."""
    from app.services.pos import POSError

    # Must match the CK_ledger_account check constraint on ledger_entries.
    if account_type not in _ACCOUNT_TYPES:
        raise POSError("bad_account_type", "نوع حساب غير صالح / invalid account type")
    if (debit <= 0 and credit <= 0) or (debit > 0 and credit > 0):
        raise POSError("bad_amounts", "أدخل مديناً أو دائناً (وليس كليهما) / enter debit OR credit")
    if reason_code is not None and reason_code not in _REASON_BY_CODE:
        raise POSError("bad_reason", "سبب تسوية غير صالح / invalid adjustment reason")

    is_adjust = reason_code is not None
    entry = m.LedgerEntry(
        branch_id=branch_id,
        account_type=account_type,
        account_ref=account_ref,
        ref_type="adjust" if is_adjust else "manual",
        reason_code=reason_code,
        debit=float(debit),
        credit=float(credit),
        note=note or ("تسوية / adjustment" if is_adjust else "قيد يدوي / manual journal entry"),
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return {
        "entry_id": entry.entry_id,
        "account_type": account_type,
        "account_ref": account_ref,
        "ref_type": entry.ref_type,
        "reason_code": reason_code,
        "debit": float(debit),
        "credit": float(credit),
    }


def account_statement(
    session: Session,
    account_type: str,
    account_ref: int | None = None,
    days: int = 90,
    branch_id: int | None = None,
) -> dict:
    """كشف حساب — a single account's running-balance statement over a window.

    Opening balance is every prior movement's net (debit − credit); each row in
    the window then carries the balance after it, closing with the final
    balance. This is the everyday eStock account report (customer/vendor
    كشف حساب, treasury/bank ledger) the flat ledger view couldn't give."""
    from app.services.pos import POSError

    if account_type not in _ACCOUNT_TYPES:
        raise POSError("bad_account_type", "نوع حساب غير صالح / invalid account type")

    cutoff = datetime.now() - timedelta(days=days)

    def _scoped(q):
        q = q.where(m.LedgerEntry.account_type == account_type)
        if account_ref is not None:
            q = q.where(m.LedgerEntry.account_ref == account_ref)
        if branch_id:
            q = q.where(m.LedgerEntry.branch_id == branch_id)
        return q

    # Opening balance = net of everything strictly before the window.
    opening_row = session.execute(
        _scoped(
            select(
                func.coalesce(func.sum(m.LedgerEntry.debit), 0),
                func.coalesce(func.sum(m.LedgerEntry.credit), 0),
            ).where(m.LedgerEntry.entry_date < cutoff)
        )
    ).one()
    opening_balance = float(opening_row[0] or 0) - float(opening_row[1] or 0)

    rows = session.scalars(
        _scoped(select(m.LedgerEntry).where(m.LedgerEntry.entry_date >= cutoff))
        .order_by(m.LedgerEntry.entry_date.asc(), m.LedgerEntry.entry_id.asc())
    ).all()

    running = opening_balance
    total_debit = total_credit = 0.0
    lines = []
    for e in rows:
        debit = float(e.debit or 0)
        credit = float(e.credit or 0)
        running += debit - credit
        total_debit += debit
        total_credit += credit
        reason = _REASON_BY_CODE.get(e.reason_code) if e.reason_code else None
        lines.append({
            "entry_id": e.entry_id,
            "entry_date": e.entry_date.isoformat() if e.entry_date else None,
            "ref_type": e.ref_type,
            "ref_id": e.ref_id,
            "reason_code": e.reason_code,
            "reason_ar": reason["ar"] if reason else None,
            "reason_en": reason["en"] if reason else None,
            "debit": round(debit, 2),
            "credit": round(credit, 2),
            "balance": round(running, 2),
            "note": e.note,
        })

    return {
        "account_type": account_type,
        "account_ref": account_ref,
        "period_days": days,
        "opening_balance": round(opening_balance, 2),
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "closing_balance": round(running, 2),
        "lines": lines,
    }


def adjustments_report(session: Session, branch_id: int | None = None, days: int = 90) -> dict:
    """تقرير التسويات — manual adjustments (ref_type='adjust') grouped by their
    Tuning reason, with per-reason debit/credit/net totals and a grand total."""
    cutoff = datetime.now() - timedelta(days=days)
    q = select(
        m.LedgerEntry.reason_code,
        func.count(m.LedgerEntry.entry_id),
        func.coalesce(func.sum(m.LedgerEntry.debit), 0),
        func.coalesce(func.sum(m.LedgerEntry.credit), 0),
    ).where(
        m.LedgerEntry.ref_type == "adjust",
        m.LedgerEntry.entry_date >= cutoff,
    ).group_by(m.LedgerEntry.reason_code)
    if branch_id:
        q = q.where(m.LedgerEntry.branch_id == branch_id)

    groups = []
    grand_debit = grand_credit = 0.0
    for code, count, debit, credit in session.execute(q):
        debit = float(debit or 0)
        credit = float(credit or 0)
        reason = _REASON_BY_CODE.get(code)
        groups.append({
            "reason_code": code,
            "reason_ar": reason["ar"] if reason else (code or "—"),
            "reason_en": reason["en"] if reason else (code or "—"),
            "count": int(count),
            "debit": round(debit, 2),
            "credit": round(credit, 2),
            "net": round(debit - credit, 2),
        })
        grand_debit += debit
        grand_credit += credit
    groups.sort(key=lambda g: abs(g["net"]), reverse=True)
    return {
        "period_days": days,
        "groups": groups,
        "total_debit": round(grand_debit, 2),
        "total_credit": round(grand_credit, 2),
        "total_net": round(grand_debit - grand_credit, 2),
    }


def sales_by_customer(session: Session, branch_id: int | None = None, days: int = 30, limit: int = 20) -> list[dict]:
    """Sales-by-customer report (an eStock report ProCare lacked): revenue and
    invoice count per named customer over the period, returns excluded."""
    cutoff = datetime.now() - timedelta(days=days)
    q = (
        select(
            m.Customer.customer_id,
            m.Customer.name_ar,
            m.Customer.name_en,
            func.count(m.Sale.sale_id),
            func.coalesce(func.sum(m.Sale.total_net), 0),
        )
        .join(m.Sale, m.Sale.customer_id == m.Customer.customer_id)
        .where(m.Sale.is_return == False, m.Sale.sale_date >= cutoff)  # noqa: E712
        .group_by(m.Customer.customer_id, m.Customer.name_ar, m.Customer.name_en)
        .order_by(func.coalesce(func.sum(m.Sale.total_net), 0).desc())
        .limit(limit)
    )
    if branch_id:
        q = q.where(m.Sale.branch_id == branch_id)
    return [
        {
            "customer_id": cid,
            "name_ar": name_ar,
            "name_en": name_en,
            "invoices": int(n),
            "revenue": round(float(total or 0), 2),
        }
        for cid, name_ar, name_en, n, total in session.execute(q)
    ]


def gl_accounts(session: Session) -> list[dict]:
    """eStock's real, historical chart of accounts (Account_Tree mirror,
    read-only) — a SEPARATE tree from ProCare's own synthetic ``chart_of_accounts``
    above (which is built from ProCare's own transactions). ``parent_source_id``
    is eStock's own account_id, not a ProCare PK."""
    rows = session.scalars(select(m.GlAccount).order_by(m.GlAccount.code)).all()
    return [
        {
            "gl_account_id": a.gl_account_id,
            "source_id": a.source_id,
            "code": a.code,
            "name_ar": a.name_ar,
            "name_en": a.name_en,
            "parent_source_id": a.parent_source_id,
            "start_money": float(a.start_money or 0),
        }
        for a in rows
    ]


def gl_journal(session: Session, limit: int = 500) -> list[dict]:
    """eStock's central GL journal (Gedo_Financial mirror, read-only, most
    recent first). ``from_type``/``to_type`` are eStock's own opaque party-type
    codes — NOT ProCare's ``LedgerEntry.account_type`` vocabulary."""
    rows = session.scalars(
        select(m.GlJournalEntry).order_by(m.GlJournalEntry.gl_entry_id.desc()).limit(limit)
    ).all()
    return [
        {
            "gl_entry_id": e.gl_entry_id,
            "source_id": e.source_id,
            "code": e.code,
            "gedo_type": e.gedo_type,
            "value": float(e.value or 0),
            "from_type": e.from_type,
            "from_id": e.from_id,
            "to_type": e.to_type,
            "to_id": e.to_id,
            "form_type": e.form_type,
            "notes": e.notes,
            "computer_name": e.computer_name,
            "actual_cashier": e.actual_cashier,
        }
        for e in rows
    ]


def gl_adjustments(session: Session, limit: int = 500) -> list[dict]:
    """eStock's manual GL adjustments (Tuning_accounts mirror, تسويات,
    read-only, most recent first). DISTINCT from ProCare's own forward-looking
    ``ADJUSTMENT_REASONS`` catalogue above — this is eStock's historical
    adjustment log. ``who_class``/``reason_source_id`` are eStock's own opaque
    codes, not translated."""
    rows = session.scalars(
        select(m.GlAdjustment).order_by(m.GlAdjustment.gl_adjustment_id.desc()).limit(limit)
    ).all()
    return [
        {
            "gl_adjustment_id": a.gl_adjustment_id,
            "source_id": a.source_id,
            "class_code": a.class_code,
            "who_class": a.who_class,
            "who_id": a.who_id,
            "reason_source_id": a.reason_source_id,
            "amount": float(a.amount or 0),
            "notes": a.notes,
        }
        for a in rows
    ]


def gl_subledgers(session: Session, party_type: str | None = None, limit: int = 500) -> list[dict]:
    """eStock's per-party GL sub-ledger balances (Gedo_customers/Gedo_Vendors/
    Gedo_branches/Gedo_employee/Gedo_installment mirror, read-only, most
    recent first). ``party_source_id`` is the RAW eStock party id — NOT
    resolved to a ProCare customer/vendor/branch/employee PK (see
    GlSubledgerBalance's docstring for why branch specifically can't be)."""
    q = select(m.GlSubledgerBalance).order_by(m.GlSubledgerBalance.gl_subledger_id.desc())
    if party_type:
        q = q.where(m.GlSubledgerBalance.party_type == party_type)
    rows = session.scalars(q.limit(limit)).all()
    return [
        {
            "gl_subledger_id": b.gl_subledger_id,
            "party_type": b.party_type,
            "source_id": b.source_id,
            "gf_ref": b.gf_ref,
            "flag": b.flag,
            "type_code": b.type_code,
            "party_source_id": b.party_source_id,
            "for_him": float(b.for_him or 0),
            "for_me": float(b.for_me or 0),
            "total": float(b.total or 0),
            "notes": b.notes,
        }
        for b in rows
    ]
