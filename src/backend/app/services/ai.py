"""PharmacyAI — the Arabic-first assistant (`chat`).

Safe by construction (docs/04 §4.3): the assistant never emits free-form SQL
against base tables. Instead a natural-language question is mapped to ONE of a
small whitelist of curated, read-only *intents*, each backed by a tested query
in the service layer. The worst case of a bad classification is an empty read.

Two routing paths:
  * If a Claude API key is configured (``ai.api_key_env``), Claude classifies the
    Arabic/English question into an intent + parameters via tool-use, then we
    execute the curated query and let Claude phrase the answer in Arabic.
  * With no key, a deterministic keyword router (Arabic + English) picks the
    intent and we format a clear Arabic/English answer locally.

Either way, only curated read queries run — no writes are reachable from chat.
"""
from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.services import alerts, dashboard, parties
from app.services.common import TODAY, money

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
    return "help"


def _execute(session: Session, intent: str, branch_id: int | None, lang: str) -> dict:
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

    # help
    text = (
        "أقدر أجاوبك عن: مبيعات اليوم/الشهر، الأصناف الأكثر مبيعاً، الأصناف قرب انتهاء الصلاحية، "
        "النواقص ومسودة طلب الشراء، العملاء المدينين، وأرباح الشهر."
        if ar
        else "I can answer: today's/this month's sales, top sellers, items near expiry, "
        "low stock and a draft purchase order, debtors, and this month's profit."
    )
    return {"intent": "help", "data": {"intents": list(INTENTS)}, "answer": text}


def _classify_with_claude(query: str, branch_id: int | None) -> tuple[str, int | None] | None:
    """Use Claude tool-use to pick an intent + branch. Returns None on any error
    so the caller falls back to the keyword router."""
    api_key = settings.ai_api_key()
    if not api_key:
        return None
    try:
        import httpx

        tools = [
            {
                "name": "answer_with_intent",
                "description": "Pick the single best intent to answer the pharmacy question.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string", "enum": list(INTENTS)},
                        "branch_id": {
                            "type": "integer",
                            "description": "1=Main, 2=Elsanta, 0=all branches",
                        },
                    },
                    "required": ["intent"],
                },
            }
        ]
        system = (
            "You route an Arabic/English pharmacy-manager question to exactly one read-only intent. "
            "Intents: " + json.dumps(INTENTS) + ". Always call the answer_with_intent tool."
        )
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.ai_model,
                "max_tokens": 256,
                "system": system,
                "tools": tools,
                "tool_choice": {"type": "tool", "name": "answer_with_intent"},
                "messages": [{"role": "user", "content": query}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        for block in resp.json().get("content", []):
            if block.get("type") == "tool_use":
                inp = block["input"]
                intent = inp.get("intent", "help")
                if intent not in INTENTS:
                    intent = "help"
                b = inp.get("branch_id", branch_id)
                return intent, (b if b else branch_id)
        return None
    except Exception:
        return None


def chat(session: Session, query: str, branch_id: int | None = None, lang: str = "ar") -> dict:
    """Answer a natural-language question, read-only. Returns intent + data + text."""
    query = (query or "").strip()
    if not query:
        return {"intent": "help", "answer": _execute(session, "help", branch_id, lang)["answer"], "data": {}}

    routed = _classify_with_claude(query, branch_id)
    if routed is not None:
        intent, branch_id = routed
        engine = "claude"
    else:
        intent = _route_keywords(query)
        engine = "rule-based"

    result = _execute(session, intent, branch_id, lang)
    result["engine"] = engine
    result["branch_id"] = branch_id or 0
    return result
