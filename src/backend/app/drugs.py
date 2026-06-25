"""Clinical drug intelligence (advisory) — Titan / Drug-Eye stand-in.

The real Titan / Drug-Eye schema at ``D:\\Labirdo`` is not yet audited (docs/03,
status TBD), so this module reads a small local interaction table seeded into
ProCare's own DB. When the Titan source is connected, ``check_basket`` swaps to
it without changing the API.

CLINICAL GUARDRAIL (docs/01, docs/04 §4.6): output is ALWAYS advisory and shown
to a pharmacist. It NEVER blocks or silently changes a sale.
"""
from __future__ import annotations

from app.config import settings
from app.db import get_db

ADVISORY_DISCLAIMER_AR = (
    "تنبيه استشاري للصيدلي فقط — لا يمنع البيع ولا يغيّره. "
    "بيانات التداخلات الكاملة تأتي من Titan/Drug-Eye بعد ربطها."
)
ADVISORY_DISCLAIMER_EN = (
    "Advisory to the pharmacist only — never blocks or alters a sale. "
    "Full interaction data comes from Titan/Drug-Eye once connected."
)


def _resolve_products(product_ids: list[int]) -> list[dict]:
    if not product_ids:
        return []
    placeholders = ",".join("?" for _ in product_ids)
    return get_db().query(
        f"""SELECT product_id, name_ar, name_en, scientific_name, is_controlled
            FROM products WHERE product_id IN ({placeholders})""",
        tuple(product_ids),
    )


def check_basket(product_ids: list[int]) -> dict:
    """Pairwise interaction check for a basket of products (advisory)."""
    products = _resolve_products(product_ids)
    ingredients = {p["scientific_name"]: p for p in products if p.get("scientific_name")}
    warnings = []
    controlled = [p for p in products if p.get("is_controlled")]

    ing_list = list(ingredients.keys())
    for i in range(len(ing_list)):
        for j in range(i + 1, len(ing_list)):
            a, b = ing_list[i], ing_list[j]
            hits = get_db().query(
                """SELECT severity, note_ar, note_en FROM drug_interactions
                   WHERE (ingredient_a = ? AND ingredient_b = ?)
                      OR (ingredient_a = ? AND ingredient_b = ?)""",
                (a, b, b, a),
            )
            for h in hits:
                warnings.append({
                    "product_a": ingredients[a]["name_ar"],
                    "product_b": ingredients[b]["name_ar"],
                    "ingredient_a": a,
                    "ingredient_b": b,
                    "severity": h["severity"],
                    "note_ar": h["note_ar"],
                    "note_en": h["note_en"],
                })
    severity_order = {"severe": 0, "moderate": 1, "minor": 2}
    warnings.sort(key=lambda w: severity_order.get(w["severity"], 9))
    return {
        "advisory": True,
        "source": "titan" if settings.titan_configured else "local_demo",
        "products": [{"product_id": p["product_id"], "name_ar": p["name_ar"],
                      "name_en": p["name_en"], "scientific_name": p["scientific_name"],
                      "is_controlled": bool(p["is_controlled"])} for p in products],
        "controlled_count": len(controlled),
        "warnings": warnings,
        "max_severity": warnings[0]["severity"] if warnings else None,
        "disclaimer_ar": ADVISORY_DISCLAIMER_AR,
        "disclaimer_en": ADVISORY_DISCLAIMER_EN,
    }


def interactions_for_product(product_id: int) -> dict:
    """All known interactions touching one product's active ingredient."""
    rows = _resolve_products([product_id])
    if not rows:
        return {"advisory": True, "found": False, "interactions": []}
    p = rows[0]
    sci = p.get("scientific_name")
    inter = get_db().query(
        """SELECT ingredient_a, ingredient_b, severity, note_ar, note_en
           FROM drug_interactions WHERE ingredient_a = ? OR ingredient_b = ?
           ORDER BY CASE severity WHEN 'severe' THEN 0 WHEN 'moderate' THEN 1 ELSE 2 END""",
        (sci, sci),
    )
    return {
        "advisory": True,
        "found": True,
        "product": {"product_id": p["product_id"], "name_ar": p["name_ar"],
                    "name_en": p["name_en"], "scientific_name": sci,
                    "is_controlled": bool(p["is_controlled"])},
        "interactions": inter,
        "dosing": "Dosing guidance pending Titan/Drug-Eye audit (docs/03 — TBD).",
        "disclaimer_ar": ADVISORY_DISCLAIMER_AR,
        "disclaimer_en": ADVISORY_DISCLAIMER_EN,
    }


def status() -> dict:
    return {
        "titan_configured": settings.titan_configured,
        "source": "titan" if settings.titan_configured else "local_demo",
        "note": "Titan/Drug-Eye schema is TBD (docs/03). Using local advisory table until connected.",
        "interaction_pairs": get_db().query_one(
            "SELECT COUNT(*) AS n FROM drug_interactions")["n"],
    }
