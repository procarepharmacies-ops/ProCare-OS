"""PharmacyAI — the Arabic-first assistant (`chat`).

Safe by construction (docs/04 §4.3): the assistant never emits free-form SQL
against base tables. Instead a natural-language question is mapped to ONE of a
small whitelist of curated, read-only *intents*, each backed by a tested query
in the service layer. The worst case of a bad classification is an empty read.

Two routing paths:
  * If an API key is configured for the active provider (``settings.ai_provider``
    — Anthropic/Claude or Google/Gemini), that provider classifies the
    Arabic/English question into an intent + parameters via tool-use /
    function-calling, then we execute the curated query and phrase the answer.
  * With no key, a deterministic keyword router (Arabic + English) picks the
    intent and we format a clear Arabic/English answer locally.

Either way, only curated read queries run — no writes are reachable from chat.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from sqlalchemy import select

from app.config import settings
from app.db import models as m
from app.services import alerts, clinical, dashboard, llm, parties
from app.services.common import money
from app.services import decisions as decisions_svc
from app.services import reorder as reorder_svc

# The whitelist of intents the assistant is allowed to invoke.
INTENTS = {
    "sales_today": "Revenue and bill count for today.",
    "sales_month": "Revenue this month vs last month.",
    "top_products": "Best-selling products over a recent period.",
    "expiring_soon": "Products/batches expiring soon (7/30/90 days).",
    "low_stock": "Products below their minimum stock level.",
    "reorder_draft": "Draft a purchase order for items that need reordering.",
    "debtors": "Customers over their credit limit / with outstanding balance.",
    "profit": "Gross profit (revenue - cost) for the current month.",
    "drug_advice": "Clinical advice for a named drug: active ingredient, alternatives in stock, dosing.",
    "forecast_risk": "Which products are at risk of running out of stock in the next 30 days.",
    "decisions": "Today's actionable decision cards from forecasts (القرارات اليومية).",
    "help": "Explain what the assistant can do.",
}


def _route_keywords(query: str) -> str:
    """Deterministic fallback router. Arabic + Egyptian-dialect + English cues."""
    q = query.lower()

    def has(*words):
        return any(w in q for w in words)

    if has("امبارح", "النهارده", "اليوم", "مبيعات اليوم", "باعت", "today", "sold today"):
        if has("الشهر", "month", "شهر"):
            return "sales_month"
        return "sales_today"
    if has("الشهر", "this month", "شهري", "month"):
        return "sales_month"
    if has("تخلص", "هتخلص", "الصلاحية", "منتهي", "expire", "expiry", "expiring"):
        return "expiring_soon"
    if has("ناقص", "نقص", "تحت الحد", "اطلب", "طلب شراء", "اعملي طلب", "reorder", "purchase order", "restock"):
        return "reorder_draft"
    if has("مخزون", "كمية", "قليل", "منخفض", "low stock", "stock"):
        return "low_stock"
    if has("اكتر", "أكثر", "أعلى", "أفضل", "top", "best seller", "best-selling", "اكثر مبيع"):
        return "top_products"
    if has("مدين", "ديون", "تجاوز", "حد الائتمان", "debt", "debtor", "over limit", "credit"):
        return "debtors"
    if has("ربح", "أرباح", "مكسب", "profit", "margin"):
        return "profit"
    if has("تفاعل", "بديل", "بدائل", "جرعة", "الماده الفعاله", "المادة الفعالة", "دواء",
           "interaction", "alternative", "substitut", "dose", "dosage", "drug"):
        return "drug_advice"
    if has("خطر", "خطره", "انقطاع", "ينقطع", "سيقطع", "نخلص", "رمز", "forecast", "stockout risk", "at risk"):
        return "forecast_risk"
    if has("قرار", "قرارات", "عاجل", "حرج", "تنفيذ", "تنبيه", "decisions", "briefing", "actionable"):
        return "decisions"
    return "help"


def _find_drug(session: Session, query: str) -> m.Product | None:
    """Best-effort match of a catalogue drug named in the question (substring,
    longest name first so 'Panadol Extra' beats 'Panadol')."""
    q = (query or "").lower()
    products = session.scalars(
        select(m.Product).where(
            m.Product.is_active == True,  # noqa: E712
            m.Product.is_deleted == False,  # noqa: E712
        )
    ).all()
    best = None
    for p in products:
        for name in (p.name_ar, p.name_en, p.scientific_name):
            if name and name.lower() in q and (best is None or len(name) > best[1]):
                best = (p, len(name))
    return best[0] if best else None


def _execute(session: Session, intent: str, branch_id: int | None, lang: str, query: str = "") -> dict:
    """Run the curated query for an intent and return structured data + an
    Arabic/English summary line."""
    ar = lang != "en"

    if intent == "sales_today":
        s = dashboard.summary(session, branch_id)["kpis"]
        text = (
            f"مبيعات اليوم {money(s['sales_today'])} جنيه من {s['bills_today']} فاتورة."
            if ar
            else f"Today's sales: {money(s['sales_today'])} EGP across {s['bills_today']} bills."
        )
        return {"intent": intent, "data": s, "answer": text}

    if intent == "sales_month":
        s = dashboard.summary(session, branch_id)["kpis"]
        delta = s["sales_month"] - s["sales_prev_month"]
        sign = "+" if delta >= 0 else ""
        text = (
            f"مبيعات الشهر {money(s['sales_month'])} جنيه (الشهر الماضي {money(s['sales_prev_month'])}، "
            f"الفرق {sign}{money(delta)})."
            if ar
            else f"This month: {money(s['sales_month'])} EGP (last month {money(s['sales_prev_month'])}, "
            f"change {sign}{money(delta)})."
        )
        return {"intent": intent, "data": s, "answer": text}

    if intent == "top_products":
        rows = dashboard.top_products(session, branch_id, days=30, limit=5)
        names = "، ".join(r["name_ar"] for r in rows) if ar else ", ".join(r["name_en"] or r["name_ar"] for r in rows)
        text = (f"أكثر ٥ أصناف مبيعاً خلال ٣٠ يوم: {names}." if ar else f"Top 5 sellers (30 days): {names}.")
        return {"intent": intent, "data": rows, "answer": text}

    if intent == "expiring_soon":
        risk = alerts.expiry_risk(session, branch_id, horizon_days=30)
        c = risk["counts"]
        text = (
            f"خلال ٣٠ يوم: {c['d7']} صنف خلال أسبوع، {c['d30']} خلال شهر. "
            f"الخسارة المتوقعة {money(risk['expected_loss_within_horizon'])} جنيه. "
            f"({c['expired']} صنف منتهي بالفعل ومقفول للبيع)"
            if ar
            else f"Within 30 days: {c['d7']} in a week, {c['d30']} in a month. "
            f"Expected loss {money(risk['expected_loss_within_horizon'])} EGP. "
            f"({c['expired']} already expired and locked from sale)"
        )
        return {"intent": intent, "data": risk, "answer": text}

    if intent == "low_stock":
        rows = alerts.low_stock(session, branch_id, limit=10)
        text = (
            f"يوجد {len(rows)} صنف تحت الحد الأدنى للمخزون."
            if ar
            else f"{len(rows)} products are below their minimum stock level."
        )
        return {"intent": intent, "data": rows, "answer": text}

    if intent == "reorder_draft":
        rows = alerts.smart_reorder(session, branch_id)
        units = sum(r["suggested_qty"] for r in rows)
        text = (
            f"مسودة طلب شراء: {len(rows)} صنف بإجمالي {money(units)} وحدة مقترحة (تحتاج موافقة المدير)."
            if ar
            else f"Draft PO: {len(rows)} products, {money(units)} suggested units (needs manager approval)."
        )
        return {"intent": intent, "data": rows, "answer": text}

    if intent == "debtors":
        rows = [c for c in parties.list_customers(session, only_debtors=True, limit=10)]
        over = [c for c in rows if c["over_limit"]]
        text = (
            f"أعلى المدينين: {len(rows)} عميل برصيد قائم، منهم {len(over)} تجاوزوا حد الائتمان."
            if ar
            else f"Top debtors: {len(rows)} customers with balances, {len(over)} over their credit limit."
        )
        return {"intent": intent, "data": rows, "answer": text}

    if intent == "profit":
        s = dashboard.summary(session, branch_id)["kpis"]
        text = (
            f"ربح الشهر التقديري (إيراد - تكلفة): {money(s['profit_month'])} جنيه."
            if ar
            else f"Estimated gross profit this month: {money(s['profit_month'])} EGP."
        )
        return {"intent": intent, "data": {"profit_month": s["profit_month"]}, "answer": text}

    if intent == "drug_advice":
        product = _find_drug(session, query)
        if product is None:
            text = (
                "اذكر اسم الدواء لأعرض لك المادة الفعّالة والبدائل المتوفرة والجرعة الاسترشادية."
                if ar
                else "Name the drug and I'll show its active ingredient, in-stock alternatives, and an advisory dose."
            )
            return {"intent": intent, "data": {}, "answer": text}
        info = clinical.drug_info(session, product.product_id, branch_id, lang)
        subs = info["substitutions"]
        sub_names = "، ".join(s["name"] for s in subs[:3]) if ar else ", ".join(s["name"] for s in subs[:3])
        ingredients = "، ".join(info["active_ingredients"]) if ar else ", ".join(info["active_ingredients"])
        if ar:
            text = f"{info['name']}: المادة الفعّالة {ingredients or 'غير محددة'}. "
            text += f"بدائل متوفرة بالمخزون: {sub_names}. " if subs else "لا توجد بدائل متوفرة بالمخزون. "
            text += "يوجد جرعة استرشادية (حسب العمر)." if info["has_dosing"] else "لا توجد قاعدة جرعة لهذا الدواء."
            text += " (إرشادي — لا يمنع البيع)"
        else:
            text = f"{info['name']}: active ingredient {ingredients or 'n/a'}. "
            text += f"In-stock alternatives: {sub_names}. " if subs else "No alternatives in stock. "
            text += "Advisory dosing available (by age)." if info["has_dosing"] else "No dosing rule for this drug."
            text += " (advisory — does not block a sale)"
        return {"intent": intent, "data": info, "answer": text}

    if intent == "forecast_risk":
        rows = reorder_svc.generate_reorder_suggestions(session, branch_id) if branch_id else []
        critical = [r for r in rows if r["priority"] == "critical"]
        urgent = [r for r in rows if r["priority"] == "urgent"]
        if ar:
            text = f"أصناف قيد الخطر (نقص متوقع خلال ٣٠ يوم): {len(rows)} صنف إجمالاً. "
            text += f"{len(critical)} حرج (ينقطع خلال ٣ أيام)، {len(urgent)} عاجل (خلال أسبوع). "
            text += "راجع لوحة التحكم للتفاصيل والعروض البديلة."
        else:
            text = f"At-risk products (shortage expected within 30 days): {len(rows)} total. "
            text += f"{len(critical)} critical (out in ≤3 days), {len(urgent)} urgent (within a week). "
            text += "Check the dashboard for details and transfer options."
        return {"intent": intent, "data": {"total": len(rows), "critical": len(critical), "urgent": len(urgent), "items": rows}, "answer": text}

    if intent == "decisions":
        cards = decisions_svc.get_open_decision_cards(session, branch_id) if branch_id else []
        critical = [c for c in cards if c["severity"] == "critical"]
        warning = [c for c in cards if c["severity"] == "warning"]
        if ar:
            text = f"القرارات اليومية (تصرفات مقترحة من التنبؤات والمخزون): {len(cards)} قرار مفتوح. "
            text += f"{len(critical)} حرج (أحمر)، {len(warning)} تحذير (أصفر). "
            text += "الموافقة على أي منها تسجل التنفيذ. التجاهل يرفع القرار دون تنفيذ."
        else:
            text = f"Daily decisions (actionable insights from forecasts & inventory): {len(cards)} open. "
            text += f"{len(critical)} critical (red), {len(warning)} warning (yellow). "
            text += "Approve any to mark actioned. Dismiss to skip without action."
        return {"intent": intent, "data": {"total": len(cards), "critical": len(critical), "warning": len(warning), "cards": cards}, "answer": text}

    # help
    text = (
        "أقدر أجاوبك عن: مبيعات اليوم/الشهر، الأصناف الأكثر مبيعاً، الأصناف قرب انتهاء الصلاحية، "
        "النواقص ومسودة طلب الشراء، العملاء المدينين، أرباح الشهر، أصناف قيد الخطر (توقع النقص)، "
        "القرارات اليومية، ونصائح الأدوية (التفاعلات/البدائل/الجرعات)."
        if ar
        else "I can answer: today's/this month's sales, top sellers, items near expiry, "
        "low stock and a draft purchase order, debtors, this month's profit, at-risk products (forecast), "
        "daily decisions, and drug advice (interactions/alternatives/dosing)."
    )
    return {"intent": "help", "data": {"intents": list(INTENTS)}, "answer": text}


def _classify(query: str, branch_id: int | None) -> tuple[str, int | None, str] | None:
    """Classify via the active provider (see services.llm) into one whitelisted
    intent. Returns (intent, branch_id, engine_name) or None to fall back to the
    deterministic keyword router."""
    routed = llm.classify(query, INTENTS, branch_id)
    if routed is None:
        return None
    return routed[0], routed[1], settings.ai_provider


def chat(session: Session, query: str, branch_id: int | None = None, lang: str = "ar") -> dict:
    """Answer a natural-language question, read-only. Returns intent + data + text."""
    query = (query or "").strip()
    if not query:
        return {"intent": "help", "answer": _execute(session, "help", branch_id, lang)["answer"], "data": {}}

    routed = _classify(query, branch_id)
    if routed is not None:
        intent, branch_id, engine = routed
    else:
        intent = _route_keywords(query)
        engine = "rule-based"

    result = _execute(session, intent, branch_id, lang, query)
    result["engine"] = engine
    result["branch_id"] = branch_id or 0
    return result
