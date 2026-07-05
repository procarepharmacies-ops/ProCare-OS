"""Clinical drug-advisory service — the Titan / Drug-Eye intelligence layer.

This is ProCare's headline differentiator from eStock: it lets operational data
(what's on the counter, what's in stock) talk to clinical drug knowledge
(interactions, generic alternatives, dosing). It backs ``PharmacyAI`` and the POS
advisory banner described in ``docs/03-titan-drugeye-integration.md`` §5–6.

GUARDRAILS (locked, docs/01):
  * Output is **ADVISORY**. It is shown to a pharmacist and **never silently
    blocks a sale** — ``app.services.pos.create_sale`` is intentionally not
    coupled to this module.
  * In-stock checks hit ProCare's OWN clean ``stock_batches`` (FEFO, non-expired)
    — never eStock at runtime.

Live vs offline (mirrors the ``app.services.etl`` gated-adapter pattern):
  * The real Titan / Drug-Eye database at ``D:\\Labirdo`` has **not been audited**
    yet — its engine, schema, and table names are TBD (docs/03 §3). So the live
    query path can't be written truthfully today.
  * Until that audit lands, the advisory runs from a **curated rule set** keyed by
    the drug's *active ingredient* (``products.scientific_name``), which the
    seeded catalogue and the eStock mirror both populate. This is clinically
    real, fully offline, and the exact shape Titan will later replace — the
    public functions here are the stable contract (``products.titan_drug_id`` is
    the production join once the schema is known).

Everything resolves **ProCare** ``product_id``s, so callers never deal with
ingredients directly.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models as m
from app.services.common import available_stock_filter, money

# --- severity model (docs/03 §5) --------------------------------------------
SEVERITY_RANK = {"minor": 0, "moderate": 1, "major": 2, "critical": 3}


# --- active-ingredient normalisation ----------------------------------------
# Map brand/scientific spellings onto a canonical ingredient token. A combo drug
# (``Paracetamol/Chlorphenamine``) normalises to a SET of ingredients, so a combo
# correctly triggers duplicate-ingredient and interaction checks on each part.
_SYNONYMS = {
    "diclofenac potassium": "diclofenac",
    "diclofenac sodium": "diclofenac",
    "acetylsalicylic acid": "aspirin",
    "asa": "aspirin",
    "paracetamol": "paracetamol",
    "acetaminophen": "paracetamol",
    "amoxicillin/clavulanate": "amoxicillin",  # clavulanate handled below
    "ascorbic acid": "vitamin c",
}

# Therapeutic classes used for class-level duplicate-therapy warnings.
NSAIDS = {"aspirin", "ibuprofen", "diclofenac", "naproxen", "ketorolac", "indomethacin"}
PPIS = {"omeprazole", "esomeprazole", "lansoprazole", "pantoprazole"}
QT_PROLONGING = {"azithromycin", "ciprofloxacin", "domperidone", "clarithromycin", "erythromycin"}


def _canon(token: str) -> str:
    t = token.strip().lower()
    return _SYNONYMS.get(t, t)


def ingredients_of(scientific_name: str | None) -> set[str]:
    """Canonical active-ingredient set for a drug (combo-aware)."""
    if not scientific_name:
        return set()
    out: set[str] = set()
    for part in scientific_name.replace("+", "/").split("/"):
        c = _canon(part)
        if c:
            out.add(c)
    return out


# --- curated interaction matrix (unordered ingredient pairs) -----------------
# severity + bilingual effect/recommendation. Clinically conventional advisories
# for the ingredients in the catalogue; Titan replaces/extends this once audited.
def _i(severity, eff_ar, eff_en, rec_ar, rec_en):
    return {
        "severity": severity,
        "effect_ar": eff_ar,
        "effect_en": eff_en,
        "recommendation_ar": rec_ar,
        "recommendation_en": rec_en,
    }


INTERACTIONS: dict[frozenset, dict] = {
    frozenset({"aspirin", "ibuprofen"}): _i(
        "major",
        "الإيبوبروفين يقلل تأثير الأسبرين الواقي للقلب ويزيد خطر نزيف المعدة.",
        "Ibuprofen blunts aspirin's cardioprotection and raises GI-bleed risk.",
        "افصل الجرعات أو استشر الطبيب؛ يفضّل بديل مسكّن.",
        "Separate doses or consult the physician; prefer an alternative analgesic.",
    ),
    frozenset({"aspirin", "diclofenac"}): _i(
        "major",
        "تناول مضادين للالتهاب معاً يزيد خطر نزيف وقرحة المعدة.",
        "Two NSAIDs together sharply increase GI bleeding/ulcer risk.",
        "تجنّب الجمع؛ استخدم مسكّناً واحداً وأضف واقياً للمعدة عند اللزوم.",
        "Avoid combining; use a single NSAID and add gastric protection if needed.",
    ),
    frozenset({"warfarin", "aspirin"}): _i(
        "critical",
        "زيادة كبيرة في خطر النزيف مع مميّع الدم.",
        "Greatly increased bleeding risk with the anticoagulant.",
        "يتطلب إشراف طبي ومتابعة INR.",
        "Requires physician oversight and INR monitoring.",
    ),
    frozenset({"ciprofloxacin", "domperidone"}): _i(
        "major",
        "كلاهما قد يطيل فترة QT ويزيد خطر اضطراب نظم القلب.",
        "Both can prolong the QT interval, raising arrhythmia risk.",
        "تجنّب الجمع خاصة مع أمراض القلب.",
        "Avoid combining, especially with cardiac history.",
    ),
    frozenset({"azithromycin", "domperidone"}): _i(
        "major",
        "خطر إطالة QT واضطراب نظم القلب عند الجمع.",
        "Risk of QT prolongation and arrhythmia when combined.",
        "تجنّب الجمع أو راقب القلب.",
        "Avoid combining or monitor cardiac status.",
    ),
    frozenset({"bisoprolol", "salbutamol"}): _i(
        "moderate",
        "حاصر بيتا (بيزوبرولول) قد يقلل فعالية موسّع الشعب (سالبوتامول).",
        "The beta-blocker (bisoprolol) can reduce the bronchodilator's effect.",
        "انتبه لمرضى الربو؛ راجع الطبيب لبديل انتقائي.",
        "Caution in asthma; consider a more selective alternative with the physician.",
    ),
    frozenset({"metformin", "furosemide"}): _i(
        "moderate",
        "قد يتأثر سكر الدم ووظائف الكلى عند الجمع.",
        "Blood glucose and renal function may shift when combined.",
        "راقب السكر ووظائف الكلى.",
        "Monitor glucose and renal function.",
    ),
    frozenset({"furosemide", "diclofenac"}): _i(
        "moderate",
        "مضادات الالتهاب تقلل تأثير مدرّ البول وقد تؤثر على الكلى.",
        "NSAIDs reduce the diuretic effect and may affect the kidneys.",
        "راقب الضغط ووظائف الكلى.",
        "Monitor blood pressure and renal function.",
    ),
    frozenset({"furosemide", "ibuprofen"}): _i(
        "moderate",
        "مضادات الالتهاب تقلل تأثير مدرّ البول وقد تؤثر على الكلى.",
        "NSAIDs reduce the diuretic effect and may affect the kidneys.",
        "راقب الضغط ووظائف الكلى.",
        "Monitor blood pressure and renal function.",
    ),
}


# --- curated dosing bands (by ingredient, advisory) --------------------------
def _dose(age_min, age_max, dose_ar, dose_en, freq_ar, freq_en, max_daily, weight_based=False):
    return {
        "age_min_years": age_min,
        "age_max_years": age_max,
        "dose_ar": dose_ar,
        "dose_en": dose_en,
        "frequency_ar": freq_ar,
        "frequency_en": freq_en,
        "max_daily_ar": max_daily[0],
        "max_daily_en": max_daily[1],
        "weight_based": weight_based,
    }


DOSING: dict[str, list[dict]] = {
    "paracetamol": [
        _dose(0, 12, "10–15 مجم/كجم للجرعة", "10–15 mg/kg per dose",
              "كل 4–6 ساعات", "every 4–6 h", ("60 مجم/كجم يومياً", "60 mg/kg/day"), weight_based=True),
        _dose(12, 120, "500–1000 مجم", "500–1000 mg",
              "كل 4–6 ساعات", "every 4–6 h", ("4 جم يومياً", "4 g/day")),
    ],
    "ibuprofen": [
        _dose(0.5, 12, "5–10 مجم/كجم للجرعة", "5–10 mg/kg per dose",
              "كل 6–8 ساعات", "every 6–8 h", ("40 مجم/كجم يومياً", "40 mg/kg/day"), weight_based=True),
        _dose(12, 120, "200–400 مجم", "200–400 mg",
              "كل 6–8 ساعات", "every 6–8 h", ("1.2 جم يومياً (بدون وصفة)", "1.2 g/day (OTC)")),
    ],
    "amoxicillin": [
        _dose(0, 12, "20–40 مجم/كجم يومياً مقسّمة", "20–40 mg/kg/day divided",
              "كل 8 ساعات", "every 8 h", ("لا تتجاوز جرعة البالغين", "do not exceed adult dose"), weight_based=True),
        _dose(12, 120, "500–875 مجم", "500–875 mg",
              "كل 8–12 ساعة", "every 8–12 h", ("1.75 جم يومياً", "1.75 g/day")),
    ],
    "azithromycin": [
        _dose(0, 12, "10 مجم/كجم في اليوم الأول ثم 5 مجم/كجم", "10 mg/kg day 1 then 5 mg/kg",
              "مرة يومياً", "once daily", ("حسب الوزن", "weight-based"), weight_based=True),
        _dose(12, 120, "500 مجم في اليوم الأول ثم 250 مجم", "500 mg day 1 then 250 mg",
              "مرة يومياً لمدة 5 أيام", "once daily for 5 days", ("500 مجم يومياً", "500 mg/day")),
    ],
    "cetirizine": [
        _dose(2, 6, "2.5 مجم", "2.5 mg", "مرة يومياً", "once daily", ("5 مجم يومياً", "5 mg/day")),
        _dose(6, 120, "10 مجم", "10 mg", "مرة يومياً", "once daily", ("10 مجم يومياً", "10 mg/day")),
    ],
}


# --- status (gated adapter) -------------------------------------------------
def is_live() -> bool:
    """True only when a real read-only Titan/Drug-Eye login is configured."""
    return settings.titan_sqlalchemy_url() is not None


def status() -> dict:
    """Report the advisory engine mode and the data the rule set covers."""
    live = is_live()
    return {
        "titan_source_configured": live,
        "mode": (
            "live read-only Titan/Drug-Eye (schema mapping pending audit — "
            "curated rules used as fallback)"
            if live
            else "offline curated advisory rules (active-ingredient based)"
        ),
        "guardrails": [
            "Clinical output is ADVISORY — it never blocks a sale.",
            "In-stock checks hit ProCare's own stock_batches (FEFO, non-expired).",
            "ProCare never writes to Titan/Drug-Eye (read-only when configured).",
        ],
        "coverage": {
            "interaction_pairs": len(INTERACTIONS),
            "dosing_ingredients": len(DOSING),
            "duplicate_therapy_classes": ["NSAID", "PPI", "same active ingredient"],
        },
        "tbd": [
            "Titan/Drug-Eye engine + schema audit at D:\\Labirdo (docs/03 §3)",
            "products.titan_drug_id mapping job (docs/03 §4)",
        ],
    }


# --- resolution helpers ------------------------------------------------------
def _product(session: Session, product_id: int) -> m.Product | None:
    return session.get(m.Product, product_id)


def _name(p: m.Product, ar: bool) -> str:
    return p.name_ar if ar else (p.name_en or p.name_ar)


# --- interactions -----------------------------------------------------------
def interactions_for_basket(
    session: Session, product_ids: list[int], *, min_severity: str = "moderate", lang: str = "ar"
) -> list[dict]:
    """All advisory interactions among the products in a basket.

    Covers (1) curated pairwise ingredient interactions and (2) automatic
    duplicate-therapy detection — the same active ingredient, or two drugs of the
    same NSAID/PPI class, appearing twice. Filtered to ``>= min_severity``.
    Advisory only.
    """
    ar = lang != "en"
    floor = SEVERITY_RANK.get(min_severity, 1)
    # De-dupe product ids but keep the catalogue rows for naming.
    products = []
    seen = set()
    for pid in product_ids:
        if pid in seen:
            continue
        seen.add(pid)
        p = _product(session, pid)
        if p is not None:
            products.append(p)

    out: list[dict] = []
    for i in range(len(products)):
        for j in range(i + 1, len(products)):
            a, b = products[i], products[j]
            ing_a, ing_b = ingredients_of(a.scientific_name), ingredients_of(b.scientific_name)
            advisory = _pair_advisory(ing_a, ing_b, ar)
            if advisory is None:
                continue
            if SEVERITY_RANK.get(advisory["severity"], 0) < floor:
                continue
            out.append(
                {
                    "product_a": {"product_id": a.product_id, "name": _name(a, ar)},
                    "product_b": {"product_id": b.product_id, "name": _name(b, ar)},
                    "severity": advisory["severity"],
                    "type": advisory["type"],
                    "effect": advisory["effect_ar"] if ar else advisory["effect_en"],
                    "recommendation": advisory["recommendation_ar"] if ar else advisory["recommendation_en"],
                    "advisory": True,
                }
            )
    out.sort(key=lambda r: SEVERITY_RANK.get(r["severity"], 0), reverse=True)
    return out


def _pair_advisory(ing_a: set[str], ing_b: set[str], ar: bool) -> dict | None:
    """Decide the strongest advisory between two ingredient sets, or None."""
    # 1) Exact curated pairwise interaction (across combo ingredients).
    best = None
    for x in ing_a:
        for y in ing_b:
            hit = INTERACTIONS.get(frozenset({x, y}))
            if hit and (best is None or SEVERITY_RANK[hit["severity"]] > SEVERITY_RANK[best["severity"]]):
                best = {**hit, "type": "interaction"}
    if best is not None:
        return best

    # 2) Duplicate active ingredient (e.g. Panadol + Congestal both = paracetamol).
    shared = ing_a & ing_b
    if shared:
        ing = sorted(shared)[0]
        return {
            "severity": "major",
            "type": "duplicate_ingredient",
            "effect_ar": f"تكرار نفس المادة الفعّالة ({ing}) قد يؤدي لتجاوز الجرعة القصوى.",
            "effect_en": f"Same active ingredient ({ing}) repeated — risk of exceeding the max dose.",
            "recommendation_ar": "اختر صنفاً واحداً يحتوي المادة لتفادي الجرعة الزائدة.",
            "recommendation_en": "Keep only one product with this ingredient to avoid overdose.",
        }

    # 3) Same therapeutic class (two different NSAIDs / two PPIs).
    for cls, label_ar, label_en in (
        (NSAIDS, "مضادات الالتهاب", "NSAIDs"),
        (PPIS, "مثبطات مضخة البروتون", "proton-pump inhibitors"),
    ):
        if (ing_a & cls) and (ing_b & cls) and not (ing_a & ing_b):
            return {
                "severity": "moderate",
                "type": "duplicate_class",
                "effect_ar": f"صنفان من نفس المجموعة ({label_ar}) — فائدة محدودة وزيادة في الأعراض الجانبية.",
                "effect_en": f"Two drugs of the same class ({label_en}) — little added benefit, more side effects.",
                "recommendation_ar": "اكتفِ بصنف واحد من المجموعة.",
                "recommendation_en": "Use only one drug from this class.",
            }
    return None


# --- substitutions (in-stock generic equivalents) ---------------------------
def substitutions(session: Session, product_id: int, branch_id: int | None = None, lang: str = "ar") -> list[dict]:
    """Therapeutic alternatives for a drug that are ACTUALLY IN STOCK now.

    Alternatives are other products sharing the same active ingredient(s) —
    generic/brand equivalents — with sellable stock (``amount > 0``, not
    expired) at ANY branch, so the counter can offer "available at the other
    branch" with the expiry detail. ``available_qty`` is the consolidated
    total; the ``branches`` breakdown carries per-branch qty + soonest expiry.
    Ordered cheapest first. Advisory.
    """
    ar = lang != "en"
    target = _product(session, product_id)
    if target is None:
        return []
    ings = ingredients_of(target.scientific_name)
    if not ings:
        return []

    on_hand = (
        select(
            m.StockBatch.product_id.label("pid"),
            func.sum(m.StockBatch.amount).label("qty"),
        )
        .where(available_stock_filter())
        .group_by(m.StockBatch.product_id)
        .subquery()
    )
    rows = session.execute(
        select(m.Product, on_hand.c.qty)
        .join(on_hand, on_hand.c.pid == m.Product.product_id)
        .where(
            m.Product.product_id != product_id,
            m.Product.is_active == True,  # noqa: E712
            m.Product.is_deleted == False,  # noqa: E712
            on_hand.c.qty > 0,
        )
        .order_by(m.Product.sell_price.asc())
    ).all()

    matches = [(p, qty) for p, qty in rows if ingredients_of(p.scientific_name) & ings]

    # Per-branch availability + soonest expiry for each alternative, so the
    # POS can say "متوفر في السنطة، ينتهي 2026-11" and offer a transfer.
    branch_names = {b.branch_id: b.name_ar for b in session.scalars(select(m.Branch)).all()}
    detail: dict[int, dict[int, dict]] = {}
    if matches:
        pids = [p.product_id for p, _ in matches]
        batch_rows = session.execute(
            select(
                m.StockBatch.product_id,
                m.StockBatch.branch_id,
                func.sum(m.StockBatch.amount),
                func.min(m.StockBatch.exp_date),
            )
            .where(available_stock_filter(), m.StockBatch.product_id.in_(pids))
            .group_by(m.StockBatch.product_id, m.StockBatch.branch_id)
        ).all()
        for pid, bid, qty, exp in batch_rows:
            detail.setdefault(pid, {})[bid] = {
                "branch_id": bid,
                "branch_name": branch_names.get(bid, str(bid)),
                "qty": money(qty),
                "nearest_expiry": exp.isoformat() if exp else None,
            }

    out = []
    for p, qty in matches:
        out.append(
            {
                "product_id": p.product_id,
                "name": _name(p, ar),
                "scientific_name": p.scientific_name,
                "sell_price": money(p.sell_price),
                "available_qty": money(qty),
                "branches": sorted(detail.get(p.product_id, {}).values(), key=lambda r: r["branch_id"]),
                "advisory": True,
            }
        )
    return out


# --- dosing -----------------------------------------------------------------
def dose(session: Session, product_id: int, patient_age_years: float, lang: str = "ar") -> dict | None:
    """Advisory dose for a patient's age, the most specific matching band.

    Returns None when the rule set has no dosing for the drug/age (honest gap,
    not a guess). Weight-based bands flag that a weight is needed.
    """
    ar = lang != "en"
    p = _product(session, product_id)
    if p is None:
        return None
    bands = None
    for ing in ingredients_of(p.scientific_name):
        if ing in DOSING:
            bands = DOSING[ing]
            chosen_ing = ing
            break
    if not bands:
        return None
    match = None
    for band in bands:
        if band["age_min_years"] <= patient_age_years <= band["age_max_years"]:
            # Keep the most specific (narrowest) matching band.
            if match is None or (band["age_max_years"] - band["age_min_years"]) < (
                match["age_max_years"] - match["age_min_years"]
            ):
                match = band
    if match is None:
        return None
    return {
        "product_id": product_id,
        "name": _name(p, ar),
        "ingredient": chosen_ing,
        "age_years": patient_age_years,
        "dose": match["dose_ar"] if ar else match["dose_en"],
        "frequency": match["frequency_ar"] if ar else match["frequency_en"],
        "max_daily": match["max_daily_ar"] if ar else match["max_daily_en"],
        "weight_based": match["weight_based"],
        "advisory": True,
    }


# --- product enrichment (drug card) -----------------------------------------
def drug_info(session: Session, product_id: int, branch_id: int | None = None, lang: str = "ar") -> dict | None:
    """A drug card: scientific name, active ingredients, in-stock generic
    alternatives, dosing bands, and any class flags. Advisory."""
    ar = lang != "en"
    p = _product(session, product_id)
    if p is None:
        return None
    ings = sorted(ingredients_of(p.scientific_name))
    classes = []
    ing_set = set(ings)
    if ing_set & NSAIDS:
        classes.append("NSAID")
    if ing_set & PPIS:
        classes.append("PPI")
    if ing_set & QT_PROLONGING:
        classes.append("QT-prolonging")
    return {
        "product_id": p.product_id,
        "name": _name(p, ar),
        "name_ar": p.name_ar,
        "name_en": p.name_en,
        "scientific_name": p.scientific_name,
        "active_ingredients": ings,
        "is_controlled": p.is_controlled,
        "classes": classes,
        "substitutions": substitutions(session, product_id, branch_id, lang),
        "has_dosing": any(i in DOSING for i in ings),
        "advisory": True,
    }
