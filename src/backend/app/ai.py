"""PharmacyAI — the Arabic-first, read-only assistant (constrained text-to-SQL).

The assistant turns an Arabic question into a single, validated ``SELECT`` over
a **whitelist of curated views** and answers in Arabic. It is read-only *by
construction* (docs/04 §4.3):

  1. Intent + entities      — parse the Arabic question.
  2. Constrained generation — emit SQL against the view whitelist only.
  3. Static validation      — single SELECT; no INSERT/UPDATE/DELETE/DDL/EXEC,
                              no ``;``-stacking, no object outside the whitelist;
                              enforce a row cap.
  4. Execution              — runs through the normal read path (the production
                              login is itself read-only, defence in depth).
  5. Answer                 — results summarised back in Arabic.

Two engines, same guardrail:
  * **llm**  — when ``ANTHROPIC_API_KEY`` is set and ``anthropic`` is importable,
               Claude writes the SQL and the Arabic summary (model from config,
               default ``claude-opus-4-8``).
  * **rules**— otherwise, a deterministic Arabic intent router maps common
               questions to prebuilt whitelisted queries. Always available, no
               network, fully offline — the system never goes dark.

The user's free text NEVER reaches the database: only the structured SELECT the
engine produces does, and the validator constrains that to the whitelist.
"""
from __future__ import annotations

import os
import re
from datetime import date, timedelta

from app.config import settings
from app.db import get_db
from app.queries import _resolve_branch_id

# Only these objects may appear after FROM / JOIN.
AI_VIEW_WHITELIST = {
    "vw_branches",
    "vw_daily_sales",
    "vw_sale_line_profit",
    "vw_top_products",
    "vw_stock_on_hand",
    "vw_low_stock",
    "vw_expiry_risk",
    "vw_customer_debtors",
    "vw_vendor_payables",
    "vw_cashier_performance",
}

ROW_CAP = 200

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|replace|truncate|"
    r"exec|execute|attach|detach|pragma|grant|revoke|vacuum|reindex|"
    r"into|values)\b",
    re.IGNORECASE,
)

# Schema doc handed to the LLM so it writes correct, whitelisted SQL.
VIEW_DOC = """\
You may ONLY read these views (never base tables). All money is EGP. Dates are
ISO 'YYYY-MM-DD'. Use date('now') for today, date('now','-1 day') for yesterday,
date('now','start of month') for the first of this month. Returns are already
excluded from sales views.

vw_branches(branch_id, code, name_ar, name_en, is_pilot, is_active)
vw_daily_sales(branch_id, branch_name_ar, branch_name_en, sale_day, bills_count,
               revenue, cash_collected, card_collected)
vw_top_products(branch_id, product_id, product_name_ar, product_name_en,
                units_sold, revenue, profit)
vw_sale_line_profit(branch_id, sale_day, product_id, product_name_ar,
                    product_name_en, units, revenue, cost, profit)
vw_stock_on_hand(branch_id, product_id, product_name_ar, product_name_en,
                 min_stock, qty_on_hand, stock_value)
vw_low_stock(branch_id, product_id, product_name_ar, product_name_en,
             qty_on_hand, min_stock)
vw_expiry_risk(branch_id, batch_id, product_id, product_name_ar,
               product_name_en, exp_date, qty_remaining, expected_loss,
               days_to_expiry)   -- days_to_expiry<0 means already expired
vw_customer_debtors(customer_id, customer_name_ar, customer_name_en, mobile,
                    credit_limit, balance, over_limit_by, over_limit)
vw_vendor_payables(vendor_id, vendor_name_ar, vendor_name_en, amount_owed)
vw_cashier_performance(branch_id, sale_day, cashier_id, cashier_name_ar,
                       cashier_name_en, bills, revenue)
"""


# ---------------------------------------------------------------------------
# Static validation — the security boundary
# ---------------------------------------------------------------------------
def validate_sql(sql: str) -> tuple[bool, str, str]:
    """Return (ok, reason, cleaned_sql). Rejects anything not a safe SELECT."""
    if not sql or not sql.strip():
        return False, "empty query", ""
    cleaned = sql.strip().rstrip(";").strip()

    # No statement stacking.
    if ";" in cleaned:
        return False, "multiple statements are not allowed", cleaned
    # Strip SQL comments so they can't smuggle keywords.
    no_comments = re.sub(r"--.*?$|/\*.*?\*/", " ", cleaned, flags=re.S | re.M)
    if not re.match(r"^\s*select\b", no_comments, re.IGNORECASE):
        return False, "only SELECT statements are allowed", cleaned
    if _FORBIDDEN.search(no_comments):
        return False, "contains a forbidden keyword (writes/DDL are not allowed)", cleaned

    # Every FROM/JOIN target must be a whitelisted view.
    targets = re.findall(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", no_comments, re.IGNORECASE)
    for t in targets:
        if t.lower() not in AI_VIEW_WHITELIST:
            return False, f"table '{t}' is not on the read whitelist", cleaned
    if not targets:
        return False, "query must read from a whitelisted view", cleaned
    return True, "ok", cleaned


def _enforce_limit(sql: str, cap: int = ROW_CAP) -> str:
    if re.search(r"\blimit\b", sql, re.IGNORECASE):
        return sql
    return f"{sql}\nLIMIT {cap}"


def run_whitelisted_sql(sql: str) -> list[dict]:
    """Validate then execute. Raises ValueError if the SQL is not allowed."""
    ok, reason, cleaned = validate_sql(sql)
    if not ok:
        raise ValueError(reason)
    return get_db().query(_enforce_limit(cleaned))


# ---------------------------------------------------------------------------
# Deterministic Arabic intent router (offline fallback — always available)
# ---------------------------------------------------------------------------
def _branch_pred(branch, col="branch_id") -> str:
    bid = _resolve_branch_id(branch)
    return f" AND {col} = {bid}" if bid is not None else ""


def _has(text: str, *words) -> bool:
    return any(w in text for w in words)


def _rule_based(query: str, branch="ALL"):
    """Map a common Arabic question to (sql, arabic_answer_builder) or None."""
    t = query.strip()
    bp = _branch_pred(branch)

    # Sales — yesterday
    if _has(t, "امبارح", "إمبارح", "أمس", "yesterday"):
        sql = (f"SELECT ROUND(SUM(revenue),2) AS revenue, SUM(bills_count) AS bills "
               f"FROM vw_daily_sales WHERE sale_day = date('now','-1 day'){bp}")
        return sql, lambda r: (
            f"مبيعات أمس: {_money(r[0]['revenue'])} من {_int(r[0]['bills'])} فاتورة."
            if r and r[0]['revenue'] else "لا توجد مبيعات مسجلة لأمس.")

    # Sales — today
    if _has(t, "النهاردة", "اليوم", "النهارده", "today"):
        sql = (f"SELECT ROUND(SUM(revenue),2) AS revenue, SUM(bills_count) AS bills "
               f"FROM vw_daily_sales WHERE sale_day = date('now'){bp}")
        return sql, lambda r: (
            f"مبيعات اليوم: {_money(r[0]['revenue'])} من {_int(r[0]['bills'])} فاتورة."
            if r and r[0]['revenue'] else "لا توجد مبيعات مسجلة لليوم حتى الآن.")

    # Expiry — soon / next week
    if _has(t, "تخلص", "هتخلص", "الصلاحية", "تنتهي", "منتهي", "expire", "expiry"):
        horizon = 7 if _has(t, "الأسبوع", "اسبوع", "week", "7", "٧") else 30
        sql = (f"SELECT product_name_ar, exp_date, qty_remaining, days_to_expiry "
               f"FROM vw_expiry_risk WHERE days_to_expiry BETWEEN 0 AND {horizon}{bp} "
               f"ORDER BY days_to_expiry ASC LIMIT 50")
        return sql, lambda r: (
            f"يوجد {_int(len(r))} صنف ستنتهي صلاحيته خلال {horizon} يوم"
            + (f"، أقربها: {r[0]['product_name_ar']} (خلال {_int(r[0]['days_to_expiry'])} يوم)." if r else ".")
            if r else f"لا توجد أصناف ستنتهي صلاحيتها خلال {horizon} يوم.")

    # Low stock / reorder
    if _has(t, "ناقص", "الناقصة", "نقص", "الحد الأدنى", "طلب شراء", "اطلب", "اعملي طلب", "low stock", "reorder"):
        sql = (f"SELECT product_name_ar, qty_on_hand, min_stock FROM vw_low_stock "
               f"WHERE 1=1{bp} ORDER BY qty_on_hand ASC LIMIT 50")
        return sql, lambda r: (
            f"يوجد {_int(len(r))} صنف عند/تحت الحد الأدنى — يُقترح إعداد طلب شراء (مسودة): "
            + "، ".join(f"{x['product_name_ar']} ({_int(x['qty_on_hand'])})" for x in r[:5]) + "."
            if r else "لا توجد أصناف ناقصة حالياً.")

    # Top products
    if _has(t, "أكثر صنف", "اكثر صنف", "الأكثر مبيع", "أعلى مبيع", "top product", "best seller", "أكثر الأصناف"):
        sql = (f"SELECT product_name_ar, units_sold, revenue FROM vw_top_products "
               f"WHERE 1=1{bp} ORDER BY revenue DESC LIMIT 10")
        return sql, lambda r: (
            "أكثر الأصناف مبيعاً: " + "، ".join(
                f"{x['product_name_ar']} ({_money(x['revenue'])})" for x in r[:5]) + "."
            if r else "لا توجد بيانات مبيعات.")

    # Debtors / over credit limit
    if _has(t, "مديون", "ديون", "تجاوز", "الحد الائتماني", "آجل", "عميل", "العملاء", "debtor", "credit"):
        sql = ("SELECT customer_name_ar, balance, over_limit_by FROM vw_customer_debtors "
               "WHERE over_limit = 1 ORDER BY over_limit_by DESC LIMIT 20")
        return sql, lambda r: (
            f"يوجد {_int(len(r))} عميل تجاوزوا الحد الائتماني، أعلاهم {r[0]['customer_name_ar']} "
            f"بزيادة {_money(r[0]['over_limit_by'])}." if r else "لا يوجد عملاء تجاوزوا حدهم الائتماني.")

    # Vendor payables
    if _has(t, "موردين", "المورد", "مستحقات", "علينا", "نوردي", "payable", "vendor", "supplier"):
        sql = ("SELECT vendor_name_ar, amount_owed FROM vw_vendor_payables "
               "ORDER BY amount_owed DESC LIMIT 20")
        return sql, lambda r: (
            f"إجمالي المستحق للموردين من أعلى {_int(len(r))}: "
            + "، ".join(f"{x['vendor_name_ar']} ({_money(x['amount_owed'])})" for x in r[:5]) + "."
            if r else "لا توجد مستحقات للموردين.")

    # Sales — this month (generic period; checked last so specific intents win)
    if _has(t, "الشهر", "شهر", "month"):
        sql = (f"SELECT ROUND(SUM(revenue),2) AS revenue, SUM(bills_count) AS bills "
               f"FROM vw_daily_sales WHERE sale_day >= date('now','start of month'){bp}")
        return sql, lambda r: (
            f"مبيعات هذا الشهر: {_money(r[0]['revenue'])} من {_int(r[0]['bills'])} فاتورة."
            if r and r[0]['revenue'] else "لا توجد مبيعات لهذا الشهر.")

    return None


def _money(v) -> str:
    try:
        return f"{float(v):,.2f} ج.م"
    except (TypeError, ValueError):
        return str(v)


def _int(v) -> str:
    try:
        return f"{int(round(float(v)))}"
    except (TypeError, ValueError):
        return str(v)


# ---------------------------------------------------------------------------
# LLM engine (Claude) — optional
# ---------------------------------------------------------------------------
def _ai_enabled() -> bool:
    cfg = settings.ai_config()
    key_env = cfg.get("api_key_env", "ANTHROPIC_API_KEY")
    if not os.environ.get(key_env):
        return False
    try:
        import anthropic  # noqa: F401
    except Exception:
        return False
    return True


def _model() -> str:
    cfg = settings.ai_config()
    m = (cfg.get("model") or "").strip()
    # Config may carry a placeholder; default to the current flagship model.
    if not m or "TBD" in m or "REPLACE" in m:
        return "claude-opus-4-8"
    return m


def _client():
    import anthropic

    cfg = settings.ai_config()
    return anthropic.Anthropic(api_key=os.environ[cfg.get("api_key_env", "ANTHROPIC_API_KEY")])


_SYSTEM = (
    "You are PharmacyAI, the read-only analytics assistant for ProCare OS, a "
    "pharmacy management system for two branches (Main / Elsanta). You translate "
    "an Arabic question into ONE safe SQL SELECT over a fixed whitelist of views, "
    "then explain the result in clear, concise Arabic (Egyptian-friendly).\n\n"
    "HARD RULES:\n"
    "- Output a SINGLE SELECT statement only. Never INSERT/UPDATE/DELETE/DDL/EXEC.\n"
    "- Read ONLY from the whitelisted views below. Never reference base tables.\n"
    "- No semicolons, no comments, no multiple statements.\n"
    "- Always add a LIMIT (<= 200).\n"
    f"{VIEW_DOC}\n"
    "Respond ONLY with a JSON object: {\"sql\": \"<the SELECT>\"}. No prose, no code fences."
)


def _llm_sql(query: str, branch="ALL") -> str:
    import json

    bid = _resolve_branch_id(branch)
    branch_note = (
        f"\nScope results to branch_id = {bid} (filter views that have a branch_id column)."
        if bid is not None else "\nResults span all branches (do not filter by branch_id)."
    )
    client = _client()
    msg = client.messages.create(
        model=_model(),
        max_tokens=600,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"السؤال: {query}{branch_note}"}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    # tolerate accidental code fences
    text = re.sub(r"^```(?:json|sql)?|```$", "", text, flags=re.IGNORECASE | re.M).strip()
    try:
        return json.loads(text)["sql"]
    except Exception:
        # the model may have returned raw SQL — use it as-is and let the validator judge
        return text


def _llm_answer(query: str, rows: list[dict], sql: str) -> str:
    client = _client()
    import json

    sample = rows[:25]
    msg = client.messages.create(
        model=_model(),
        max_tokens=400,
        system=("You are PharmacyAI. Answer the user's Arabic question in concise Arabic "
                "using ONLY the provided query result rows. Use Egyptian pharmacy context. "
                "Money is EGP (ج.م). If the result is empty, say so politely."),
        messages=[{
            "role": "user",
            "content": (f"السؤال: {query}\n\nنتيجة الاستعلام (JSON):\n"
                        f"{json.dumps(sample, ensure_ascii=False)}\n\nأجب بإيجاز بالعربية."),
        }],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def chat(query: str, branch="ALL") -> dict:
    """Answer an Arabic question, read-only. Returns answer + the SQL + rows."""
    query = (query or "").strip()
    if not query:
        return {"engine": "none", "answer": "من فضلك اكتب سؤالك.", "sql": None, "rows": []}

    engine = "llm" if _ai_enabled() else "rules"

    if engine == "llm":
        try:
            sql = _llm_sql(query, branch)
            ok, reason, cleaned = validate_sql(sql)
            if not ok:
                # The validator is the boundary — fall back to the safe router.
                raise ValueError(reason)
            rows = get_db().query(_enforce_limit(cleaned))
            try:
                answer = _llm_answer(query, rows, cleaned)
            except Exception:
                answer = _fallback_summary(rows)
            return {"engine": "llm", "model": _model(), "branch": str(branch).upper(),
                    "answer": answer, "sql": cleaned, "row_count": len(rows),
                    "rows": rows[:50]}
        except Exception as exc:  # fall through to the rules engine
            fallback = _rules_response(query, branch)
            if fallback:
                fallback["engine"] = "rules_fallback"
                fallback["note"] = f"AI engine unavailable ({exc.__class__.__name__}); used the rule router."
                return fallback
            return {"engine": "llm_error", "branch": str(branch).upper(),
                    "answer": "تعذّر فهم السؤال بدقة. جرّب صياغة أوضح، مثل: "
                              "«مبيعات النهاردة» أو «الأصناف اللي هتخلص الأسبوع الجاي».",
                    "sql": None, "rows": []}

    resp = _rules_response(query, branch)
    if resp:
        return resp
    return {
        "engine": "rules",
        "branch": str(branch).upper(),
        "answer": ("لم أتعرّف على السؤال. جرّب أحد هذه: «مبيعات النهاردة»، «مبيعات امبارح»، "
                   "«الأصناف اللي هتخلص الأسبوع الجاي»، «الأصناف الناقصة»، «أكثر صنف مبيعاً»، "
                   "«العملاء اللي تجاوزوا الحد»، «مستحقات الموردين»."),
        "sql": None,
        "rows": [],
        "suggestions": [
            "مبيعات النهاردة", "مبيعات امبارح", "مبيعات الشهر",
            "الأصناف اللي هتخلص الأسبوع الجاي", "الأصناف الناقصة",
            "أكثر صنف مبيعاً", "العملاء اللي تجاوزوا الحد", "مستحقات الموردين",
        ],
    }


def _rules_response(query: str, branch="ALL") -> dict | None:
    hit = _rule_based(query, branch)
    if not hit:
        return None
    sql, answer_fn = hit
    ok, reason, cleaned = validate_sql(sql)
    if not ok:  # should never happen for built-ins, but stay safe
        return None
    rows = get_db().query(_enforce_limit(cleaned))
    return {
        "engine": "rules",
        "branch": str(branch).upper(),
        "answer": answer_fn(rows),
        "sql": cleaned,
        "row_count": len(rows),
        "rows": rows[:50],
    }


def _fallback_summary(rows: list[dict]) -> str:
    if not rows:
        return "لا توجد بيانات مطابقة."
    return f"تم العثور على {len(rows)} صف. أول النتائج: " + ", ".join(
        f"{k}={v}" for k, v in list(rows[0].items())[:4])


def engine_status() -> dict:
    return {
        "engine": "llm" if _ai_enabled() else "rules",
        "model": _model() if _ai_enabled() else None,
        "read_only": True,
        "view_whitelist": sorted(AI_VIEW_WHITELIST),
        "row_cap": ROW_CAP,
    }
