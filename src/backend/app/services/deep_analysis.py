"""Whole-pharmacy deep analysis — every aspect, in one call.

A management-grade diagnostic that pulls together sales growth, profitability,
product movement (incl. dead stock), inventory health & turnover, customers &
retention, purchasing & **supplier concentration**, the cash position,
branch-by-branch comparison and operating rhythm — then distils it into
severity-scored **findings** and **recommendations**, and an executive
**narrative**.

Honesty rule (same as the AI assistant, docs/04): the numbers are all computed
here from ProCare's own tables and are reproducible. The AI layer only *phrases*
those facts into prose — it never invents a figure. With no API key configured
a deterministic narrative is composed from the same findings, so the endpoint is
fully functional offline.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models as m
from app.services import alerts, llm, performance
from app.services.common import available_stock_filter, branch_filter, money, today


def _pct(n, d):
    return round(100 * n / d, 1) if d else None


# --- component analyses -----------------------------------------------------
def _dead_stock(session: Session, branch_id, days: int = 180) -> dict:
    """Products holding stock but with no sale in the last ``days`` — cash frozen
    on the shelf. Value at cost."""
    cutoff = datetime.combine(today() - timedelta(days=days), datetime.min.time())
    sold_recently = (
        select(func.distinct(m.SaleLine.product_id))
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(m.Sale.is_return == False, m.Sale.sale_date >= cutoff)  # noqa: E712
    )
    rows = session.execute(
        select(
            m.Product.product_id, m.Product.name_ar, m.Product.name_en,
            func.sum(m.StockBatch.amount).label("qty"),
            func.sum(m.StockBatch.amount * m.StockBatch.buy_price).label("value"),
        )
        .join(m.StockBatch, m.StockBatch.product_id == m.Product.product_id)
        .where(
            available_stock_filter(), branch_filter(m.StockBatch, branch_id),
            m.Product.is_active == True,  # noqa: E712
            m.Product.product_id.not_in(sold_recently),
        )
        .group_by(m.Product.product_id, m.Product.name_ar, m.Product.name_en)
        .order_by(func.sum(m.StockBatch.amount * m.StockBatch.buy_price).desc())
    ).all()
    total_value = sum(float(r.value or 0) for r in rows)
    return {
        "window_days": days,
        "count": len(rows),
        "value_at_cost": money(total_value),
        "items": [
            {"name_ar": r.name_ar, "name_en": r.name_en, "qty": money(r.qty), "value": money(r.value)}
            for r in rows[:15]
        ],
    }


def _inventory_turnover(session: Session, branch_id, snapshot: dict) -> dict:
    """Days-of-stock cover = current stock value ÷ average daily COGS (90 days)."""
    since = datetime.combine(today() - timedelta(days=89), datetime.min.time())
    cogs_90 = session.scalar(
        select(func.coalesce(func.sum(m.SaleLine.amount * m.SaleLine.buy_price), 0))
        .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
        .where(m.Sale.is_return == False, branch_filter(m.Sale, branch_id), m.Sale.sale_date >= since)  # noqa: E712
    ) or 0
    daily_cogs = float(cogs_90) / 90
    stock_cost = snapshot["stock_value_at_cost"]
    days_cover = round(stock_cost / daily_cogs, 0) if daily_cogs else None
    annual_turns = round(365 / days_cover, 1) if days_cover else None
    return {
        "avg_daily_cogs": money(daily_cogs),
        "stock_value_at_cost": stock_cost,
        "days_of_stock_cover": days_cover,
        "annual_inventory_turns": annual_turns,
    }


def _customers(session: Session, branch_id, window_start: datetime) -> dict:
    """Retention picture: registered, active (90d), lapsed (>365d), top spenders."""
    registered = session.scalar(
        select(func.count()).select_from(m.Customer).where(m.Customer.is_deleted == False)  # noqa: E712
    ) or 0

    # Last purchase per customer (non-return, in window).
    last_seen = dict(
        session.execute(
            select(m.Sale.customer_id, func.max(m.Sale.sale_date))
            .where(
                m.Sale.is_return == False, m.Sale.customer_id != None,  # noqa: E711,E712
                branch_filter(m.Sale, branch_id),
            )
            .group_by(m.Sale.customer_id)
        ).all()
    )
    active_90 = sum(1 for d in last_seen.values() if d and d >= datetime.combine(today() - timedelta(days=90), datetime.min.time()))
    lapsed = sum(1 for d in last_seen.values() if d and d < datetime.combine(today() - timedelta(days=365), datetime.min.time()))

    spend = session.execute(
        select(
            m.Customer.name_ar, m.Customer.name_en,
            func.coalesce(func.sum(m.Sale.total_net), 0).label("spend"),
            func.count(m.Sale.sale_id).label("bills"),
        )
        .join(m.Sale, m.Sale.customer_id == m.Customer.customer_id)
        .where(m.Sale.is_return == False, branch_filter(m.Sale, branch_id), m.Sale.sale_date >= window_start)  # noqa: E712
        .group_by(m.Customer.customer_id, m.Customer.name_ar, m.Customer.name_en)
        .order_by(func.sum(m.Sale.total_net).desc())
        .limit(10)
    ).all()

    receivables = session.scalar(
        select(func.coalesce(func.sum(m.Customer.current_balance), 0)).where(m.Customer.current_balance > 0)
    ) or 0
    over_limit = session.scalar(
        select(func.count()).select_from(m.Customer).where(
            m.Customer.credit_limit > 0, m.Customer.current_balance > m.Customer.credit_limit)
    ) or 0

    return {
        "registered": int(registered),
        "with_purchase_history": len(last_seen),
        "active_90d": active_90,
        "lapsed_365d": lapsed,
        "receivables": money(receivables),
        "over_limit": int(over_limit),
        "top_spenders": [
            {"name_ar": r.name_ar, "name_en": r.name_en, "spend": money(r.spend), "bills": int(r.bills)}
            for r in spend
        ],
    }


def _suppliers(session: Session, branch_id, window_start) -> dict:
    """Supplier concentration: top-vendor share + Herfindahl index (0–1)."""
    rows = session.execute(
        select(
            m.Vendor.name_ar, m.Vendor.name_en,
            func.coalesce(func.sum(m.Purchase.total_gross - m.Purchase.total_discount), 0).label("spend"),
        )
        .join(m.Purchase, m.Purchase.vendor_id == m.Vendor.vendor_id)
        .where(m.Purchase.is_return == False, branch_filter(m.Purchase, branch_id), m.Purchase.bill_date >= window_start.date())  # noqa: E712
        .group_by(m.Vendor.vendor_id, m.Vendor.name_ar, m.Vendor.name_en)
        .order_by(func.sum(m.Purchase.total_gross - m.Purchase.total_discount).desc())
    ).all()
    total = sum(float(r.spend) for r in rows) or 0.0
    shares = [float(r.spend) / total for r in rows] if total else []
    hhi = round(sum(s * s for s in shares), 3) if shares else 0
    payables = session.scalar(
        select(func.coalesce(func.sum(m.Vendor.current_balance), 0)).where(m.Vendor.current_balance > 0)
    ) or 0
    return {
        "total_spend": money(total),
        "top_vendor": (rows[0].name_en or rows[0].name_ar) if rows else None,
        "top_vendor_share_pct": _pct(float(rows[0].spend), total) if rows else None,
        "herfindahl_index": hhi,
        "vendor_count": len(rows),
        "payables": money(payables),
        "ranking": [
            {"name_ar": r.name_ar, "name_en": r.name_en, "spend": money(r.spend), "share_pct": _pct(float(r.spend), total)}
            for r in rows
        ],
    }


# --- findings + recommendations engine --------------------------------------
def _finding(area, severity, title_en, title_ar, detail_en, detail_ar, metric=None):
    return {
        "area": area, "severity": severity,
        "title_en": title_en, "title_ar": title_ar,
        "detail_en": detail_en, "detail_ar": detail_ar, "metric": metric,
    }


def _build_findings(ov, audit, dead, turnover, cust, sup) -> list[dict]:
    F = []
    yearly = ov["yearly"]
    snap = ov["snapshot"]

    # Growth trend (use full years; 2026 is partial so compare 2024→2025).
    full = [y for y in yearly if y["year"] < today().year]
    if len(full) >= 2:
        first, last = full[0], full[-1]
        n = last["year"] - first["year"]
        cagr = (pow(last["revenue"] / first["revenue"], 1 / n) - 1) * 100 if first["revenue"] and n else None
        if cagr is not None:
            sev = "positive" if cagr >= 8 else ("low" if cagr >= 0 else "high")
            F.append(_finding(
                "growth", sev,
                f"Revenue CAGR {cagr:.0f}% ({first['year']}→{last['year']})",
                f"نمو الإيرادات السنوي المركّب {cagr:.0f}% ({first['year']}→{last['year']})",
                f"Full-year revenue moved {money(first['revenue'])} → {money(last['revenue'])} EGP.",
                f"إيرادات السنة الكاملة تحرّكت من {money(first['revenue'])} إلى {money(last['revenue'])} جنيه.",
                round(cagr, 1)))

    # Margin trend.
    margins = [y["margin_pct"] for y in full if y["margin_pct"] is not None]
    if len(margins) >= 2:
        drop = margins[0] - margins[-1]
        if drop >= 2:
            F.append(_finding("profitability", "medium",
                "Gross margin is slipping",
                "هامش الربح في تراجع",
                f"Margin fell from {margins[0]}% to {margins[-1]}% — review buy prices, discounts and pricing.",
                f"الهامش انخفض من {margins[0]}% إلى {margins[-1]}% — راجع أسعار الشراء والخصومات والتسعير.",
                round(drop, 1)))
        else:
            F.append(_finding("profitability", "positive",
                f"Gross margin steady (~{margins[-1]}%)",
                f"هامش ربح مستقر (~{margins[-1]}%)",
                "Margin held across the period.", "الهامش ثابت عبر الفترة.", margins[-1]))

    # Supplier concentration.
    if sup["top_vendor_share_pct"] is not None and sup["top_vendor_share_pct"] >= 40:
        F.append(_finding("purchasing", "high",
            f"Supplier concentration: {sup['top_vendor']} = {sup['top_vendor_share_pct']}% of spend",
            f"تركّز الموردين: {sup['top_vendor']} = {sup['top_vendor_share_pct']}% من المشتريات",
            f"HHI {sup['herfindahl_index']}. One distributor dominates — a price change or supply gap hits hard. "
            "Negotiate on the volume, and qualify a second source for key lines.",
            f"مؤشر التركّز {sup['herfindahl_index']}. مورد واحد مسيطر — أي تغيّر سعر أو نقص يؤثر بقوة. "
            "تفاوض على الحجم، وجهّز مورداً بديلاً للأصناف الأساسية.",
            sup["top_vendor_share_pct"]))

    # Expiry waste.
    exp_val = snap["expired_in_stock_value"]
    if exp_val > 0:
        F.append(_finding("inventory", "high" if exp_val > 20000 else "medium",
            f"Expired stock on hand worth {money(exp_val)} EGP",
            f"مخزون منتهي الصلاحية بقيمة {money(exp_val)} جنيه",
            f"{money(snap['expired_in_stock_units'])} units past expiry are still in stock — quarantine, "
            "claim supplier credit, and tighten the FEFO expiry sweep.",
            f"{money(snap['expired_in_stock_units'])} وحدة منتهية ما زالت بالمخزون — اعزلها، "
            "طالب المورد بالمرتجع، وشدّد جرد الصلاحية.",
            exp_val))

    # Dead stock.
    if dead["count"] > 0:
        F.append(_finding("inventory", "medium",
            f"{dead['count']} products not sold in {dead['window_days']}d ({money(dead['value_at_cost'])} EGP frozen)",
            f"{dead['count']} صنف لم يُبع منذ {dead['window_days']} يوم ({money(dead['value_at_cost'])} جنيه مجمّدة)",
            "Cash tied up in non-moving stock — run a clearance, bundle, or transfer to the busier branch.",
            "كاش مجمّد في مخزون راكد — اعمل تصفية أو عروض أو حوّله للفرع الأنشط.",
            dead["value_at_cost"]))

    # Inventory turnover.
    if turnover["days_of_stock_cover"] is not None:
        d = turnover["days_of_stock_cover"]
        if d > 150:
            F.append(_finding("inventory", "medium",
                f"High stock cover: {d:.0f} days (~{turnover['annual_inventory_turns']} turns/yr)",
                f"تغطية مخزون مرتفعة: {d:.0f} يوم (~{turnover['annual_inventory_turns']} دورة/سنة)",
                "You are holding a lot of stock relative to sales — free the cash by trimming slow lines.",
                "تحتفظ بمخزون كبير مقارنة بالمبيعات — حرّر الكاش بتقليل الأصناف البطيئة.", d))
        else:
            F.append(_finding("inventory", "positive",
                f"Healthy stock cover: {d:.0f} days (~{turnover['annual_inventory_turns']} turns/yr)",
                f"تغطية مخزون صحية: {d:.0f} يوم (~{turnover['annual_inventory_turns']} دورة/سنة)",
                "Stock is well matched to sales velocity.", "المخزون متوازن مع سرعة البيع.", d))

    # Customer retention.
    if cust["with_purchase_history"]:
        lapsed_pct = _pct(cust["lapsed_365d"], cust["with_purchase_history"])
        if lapsed_pct and lapsed_pct >= 25:
            F.append(_finding("customers", "medium",
                f"{cust['lapsed_365d']} customers lapsed (>12 months, {lapsed_pct}%)",
                f"{cust['lapsed_365d']} عميل متوقف (أكثر من ١٢ شهر، {lapsed_pct}%)",
                "Win-back opportunity — a WhatsApp campaign to the inactive audience is already built in.",
                "فرصة استرجاع — حملة واتساب للعملاء غير النشطين متاحة في النظام.", lapsed_pct))

    # Receivables control.
    if cust["over_limit"] > 0:
        F.append(_finding("cash", "medium",
            f"{cust['over_limit']} customers over their credit limit ({money(cust['receivables'])} EGP receivable)",
            f"{cust['over_limit']} عميل تجاوز حد الائتمان ({money(cust['receivables'])} جنيه مستحقات)",
            "Chase the over-limit balances and freeze further credit until settled.",
            "حصّل الأرصدة المتجاوزة وأوقف الآجل حتى السداد.",
            cust["receivables"]))

    # Walk-in / CRM reach.
    walk = next((c for c in audit["checks"] if c["key"] == "walk_in_share"), None)
    if walk and walk["value"] and walk["value"] >= 50:
        F.append(_finding("customers", "low",
            f"{walk['value']}% of invoices are walk-ins (no customer record)",
            f"{walk['value']}% من الفواتير بدون عميل مسجّل",
            "Capturing phone numbers at the till unlocks loyalty and win-back marketing.",
            "تسجيل رقم الموبايل عند الكاشير يفعّل الولاء والتسويق.", walk["value"]))

    # Cash position.
    net = snap["receivables_from_customers"] - snap["payables_to_vendors"]
    F.append(_finding("cash", "low" if net < 0 else "positive",
        f"Net trade position {money(net)} EGP (receivables − payables)",
        f"صافي المركز التجاري {money(net)} جنيه (مستحقات − التزامات)",
        f"Owed to suppliers {money(snap['payables_to_vendors'])}, owed by customers {money(snap['receivables_from_customers'])}. "
        f"Stock at cost adds {money(snap['stock_value_at_cost'])} of working capital.",
        f"مستحق للموردين {money(snap['payables_to_vendors'])}، ومستحق من العملاء {money(snap['receivables_from_customers'])}. "
        f"المخزون بالتكلفة يمثّل {money(snap['stock_value_at_cost'])} رأس مال عامل.",
        money(net)))

    order = {"high": 0, "medium": 1, "low": 2, "positive": 3}
    F.sort(key=lambda f: order.get(f["severity"], 9))
    return F


def _recommendations(findings) -> list[dict]:
    recs = []
    for f in findings:
        if f["severity"] in ("high", "medium"):
            recs.append({"area": f["area"], "action_en": f["detail_en"], "action_ar": f["detail_ar"]})
    return recs[:8]


# --- AI narrative (facts → prose; deterministic fallback offline) -----------
def _ai_narrative(summary: dict, lang: str) -> tuple[str, str]:
    """Return (narrative, engine). Uses the configured provider to *phrase* the
    computed findings; falls back to a deterministic executive summary offline."""
    fallback = _fallback_narrative(summary, lang)
    if not llm.is_configured():
        return fallback, "rule-based"
    facts = json.dumps({
        "as_of": summary["as_of"], "years": summary["period"]["years"],
        "totals": summary["sales"]["totals"], "snapshot": summary["inventory"]["snapshot"],
        "findings": [{"area": f["area"], "severity": f["severity"], "title": f["title_en"]} for f in summary["findings"]],
    }, ensure_ascii=False)
    system = (
        "You are a pharmacy business analyst. Using ONLY the JSON facts provided, write a concise "
        "executive summary (6-9 sentences) for the owner: overall health, the biggest risks, and the "
        "top priorities. Do not invent any number not in the facts. "
        + ("Write in Arabic." if lang != "en" else "Write in English.")
    )
    text = llm.complete(facts, system=system, max_tokens=700)
    if text:
        return text, settings.ai_provider
    return fallback, "rule-based"


def _fallback_narrative(summary: dict, lang: str) -> str:
    ar = lang != "en"
    t = summary["sales"]["totals"]
    snap = summary["inventory"]["snapshot"]
    highs = [f for f in summary["findings"] if f["severity"] == "high"]
    pos = [f for f in summary["findings"] if f["severity"] == "positive"]
    key = "؛ ".join(f["title_ar"] for f in (highs or summary["findings"])[:3]) if ar else "; ".join(
        f["title_en"] for f in (highs or summary["findings"])[:3])
    good = (pos[0]["title_ar"] if ar else pos[0]["title_en"]) if pos else None
    if ar:
        s = (f"على مدى {summary['period']['years']} سنوات حققت الصيدلية إيرادات {money(t['revenue'])} جنيه "
             f"بمجمل ربح {money(t['gross_profit'])} عبر {t['invoices']} فاتورة. "
             f"المخزون الحالي بالتكلفة {money(snap['stock_value_at_cost'])} جنيه، "
             f"والمستحقات على العملاء {money(snap['receivables_from_customers'])} مقابل التزامات للموردين "
             f"{money(snap['payables_to_vendors'])}. ")
        s += f"أهم ما يحتاج انتباه: {key}. " if key else ""
        s += f"نقطة قوة: {good}." if good else ""
        return s
    s = (f"Over {summary['period']['years']} years the pharmacy generated {money(t['revenue'])} EGP revenue "
         f"and {money(t['gross_profit'])} gross profit across {t['invoices']} invoices. "
         f"Stock at cost stands at {money(snap['stock_value_at_cost'])} EGP, with {money(snap['receivables_from_customers'])} "
         f"owed by customers against {money(snap['payables_to_vendors'])} owed to suppliers. ")
    s += f"Top priorities: {key}. " if key else ""
    s += f"Strength: {good}." if good else ""
    return s


# --- entry point ------------------------------------------------------------
def deep_analysis(session: Session, years: int = 5, branch_id: int | None = None, lang: str = "en") -> dict:
    """The whole-pharmacy diagnostic across every aspect + findings + narrative."""
    ov = performance.overview(session, years=years, branch_id=branch_id)
    audit = performance.audit(session, branch_id=branch_id)
    window_start = datetime(ov["year_range"][0], 1, 1)

    dead = _dead_stock(session, branch_id)
    turnover = _inventory_turnover(session, branch_id, ov["snapshot"])
    cust = _customers(session, branch_id, window_start)
    sup = _suppliers(session, branch_id, window_start)

    findings = _build_findings(ov, audit, dead, turnover, cust, sup)
    recommendations = _recommendations(findings)

    summary = {
        "as_of": today().isoformat(),
        "branch_id": branch_id or 0,
        "period": {"years": years, "range": ov["year_range"]},
        "sales": {"yearly": ov["yearly"], "monthly": ov["monthly"], "totals": ov["totals"]},
        "inventory": {"snapshot": ov["snapshot"], "turnover": turnover, "dead_stock": dead},
        "customers": cust,
        "suppliers": sup,
        "by_branch": ov.get("by_branch", []),
        "audit": {"overall": audit["overall"], "checks": audit["checks"], "data_span": audit["data_span"]},
        "findings": findings,
        "recommendations": recommendations,
        "scorecard": {
            "high_risks": sum(1 for f in findings if f["severity"] == "high"),
            "medium_risks": sum(1 for f in findings if f["severity"] == "medium"),
            "strengths": sum(1 for f in findings if f["severity"] == "positive"),
        },
    }
    narrative, engine = _ai_narrative(summary, lang)
    summary["narrative"] = narrative
    summary["narrative_engine"] = engine
    return summary


if __name__ == "__main__":
    from app.db.base import SessionLocal
    with SessionLocal() as s:
        print(json.dumps(deep_analysis(s), ensure_ascii=False, indent=2, default=str))
