"""Clinical advisory tests.

Cover the four advisory capabilities (interactions incl. duplicate therapy,
in-stock substitutions, age-band dosing, the drug card) and — critically — that
the advisory NEVER blocks a sale (the locked guardrail): a basket with a major
interaction still completes at the POS.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.db import models as m
from app.services import ai, clinical, pos
from app.services.common import today


def _by_en(session, name_en: str) -> m.Product:
    return session.scalar(select(m.Product).where(m.Product.name_en == name_en))


def _fresh_product(session, name_ar, sci, branch_id=None, qty=0.0, price=10.0):
    """Create a product, optionally with sellable stock at a branch."""
    p = m.Product(name_ar=name_ar, name_en=name_ar, scientific_name=sci, sell_price=price, buy_price=5, min_stock=0)
    session.add(p)
    session.flush()
    if branch_id and qty > 0:
        session.add(
            m.StockBatch(product_id=p.product_id, branch_id=branch_id, amount=qty,
                         sell_price=price, buy_price=5, exp_date=today() + timedelta(days=200))
        )
        session.flush()
    return p


# --- status -----------------------------------------------------------------
def test_status_is_offline_curated_by_default():
    st = clinical.status()
    assert st["titan_source_configured"] is False
    assert "curated" in st["mode"]
    assert st["coverage"]["interaction_pairs"] >= 5


# --- ingredient normalisation ----------------------------------------------
def test_combo_ingredient_parsing():
    assert clinical.ingredients_of("Paracetamol/Chlorphenamine") == {"paracetamol", "chlorphenamine"}
    assert clinical.ingredients_of("Diclofenac Potassium") == {"diclofenac"}
    assert clinical.ingredients_of(None) == set()


# --- interactions -----------------------------------------------------------
def test_two_nsaids_flag_major_interaction(session):
    aspirin = _by_en(session, "Rivo")          # Aspirin
    ibuprofen = _by_en(session, "Brufen")       # Ibuprofen
    rows = clinical.interactions_for_basket(session, [aspirin.product_id, ibuprofen.product_id])
    assert len(rows) == 1
    assert rows[0]["severity"] == "major"
    assert rows[0]["type"] == "interaction"
    assert rows[0]["advisory"] is True


def test_duplicate_active_ingredient_detected(session):
    panadol = _by_en(session, "Panadol")        # Paracetamol
    congestal = _by_en(session, "Congestal")    # Paracetamol/Chlorphenamine
    rows = clinical.interactions_for_basket(session, [panadol.product_id, congestal.product_id])
    assert any(r["type"] == "duplicate_ingredient" for r in rows)


def test_same_class_two_ppis(session):
    nexium = _by_en(session, "Nexium")          # Esomeprazole
    omez = _by_en(session, "Omez")              # Omeprazole
    rows = clinical.interactions_for_basket(session, [nexium.product_id, omez.product_id])
    assert any(r["type"] == "duplicate_class" for r in rows)


def test_min_severity_filters_out_moderate(session):
    concor = _by_en(session, "Concor")          # Bisoprolol
    farcolin = _by_en(session, "Farcolin")      # Salbutamol
    moderate = clinical.interactions_for_basket(session, [concor.product_id, farcolin.product_id])
    assert any(r["severity"] == "moderate" for r in moderate)
    filtered = clinical.interactions_for_basket(
        session, [concor.product_id, farcolin.product_id], min_severity="major"
    )
    assert filtered == []


def test_no_interaction_returns_empty(session):
    vitc = _by_en(session, "Vitamin C")
    rows = clinical.interactions_for_basket(session, [vitc.product_id])
    assert rows == []


# --- substitutions (in-stock filter) ----------------------------------------
def test_substitutions_only_returns_in_stock_same_ingredient(session):
    target = _fresh_product(session, "هدف باراسيتامول", "Paracetamol")
    in_stock = _fresh_product(session, "بديل متوفر", "Paracetamol", branch_id=1, qty=50)
    _no_stock = _fresh_product(session, "بديل غير متوفر", "Paracetamol")  # no stock
    _other = _fresh_product(session, "صنف مختلف", "Loratadine", branch_id=1, qty=50)
    session.commit()

    subs = clinical.substitutions(session, target.product_id, branch_id=1)
    ids = {s["product_id"] for s in subs}
    assert in_stock.product_id in ids
    assert _no_stock.product_id not in ids   # filtered: not in stock
    assert _other.product_id not in ids      # filtered: different ingredient
    assert target.product_id not in ids      # never suggests itself


# --- dosing -----------------------------------------------------------------
def test_dose_picks_age_band(session):
    panadol = _by_en(session, "Panadol")        # Paracetamol
    child = clinical.dose(session, panadol.product_id, 5)
    adult = clinical.dose(session, panadol.product_id, 30)
    assert child is not None and adult is not None
    assert child["weight_based"] is True       # pediatric paracetamol is mg/kg
    assert child["dose"] != adult["dose"]


def test_dose_unknown_drug_returns_none(session):
    primolut = _by_en(session, "Primolut")      # Norethisterone — no dosing rule
    assert clinical.dose(session, primolut.product_id, 30) is None


# --- drug card --------------------------------------------------------------
def test_drug_info_lists_class_and_ingredients(session):
    brufen = _by_en(session, "Brufen")          # Ibuprofen (NSAID)
    info = clinical.drug_info(session, brufen.product_id, branch_id=1)
    assert "ibuprofen" in info["active_ingredients"]
    assert "NSAID" in info["classes"]
    assert info["has_dosing"] is True


# --- the locked guardrail: advisory never blocks a sale ---------------------
def test_interacting_basket_still_sells(session):
    """A basket with a major interaction is advised on, NOT blocked."""
    a = _fresh_product(session, "أسبرين اختبار", "Aspirin", branch_id=1, qty=20)
    b = _fresh_product(session, "ايبوبروفين اختبار", "Ibuprofen", branch_id=1, qty=20)
    session.commit()

    # The advisory fires...
    rows = clinical.interactions_for_basket(session, [a.product_id, b.product_id])
    assert rows and rows[0]["severity"] == "major"

    # ...but the sale still goes through (clinical is decoupled from POS).
    sale = pos.create_sale(
        session, branch_id=1,
        lines=[pos.SaleLineInput(a.product_id, 1), pos.SaleLineInput(b.product_id, 1)],
    )
    assert sale.sale_id is not None


# --- API smoke --------------------------------------------------------------
def test_clinical_api_interactions_and_card(client, session):
    aspirin = _by_en(session, "Rivo")
    ibuprofen = _by_en(session, "Brufen")
    r = client.post(
        "/api/clinical/interactions",
        json={"product_ids": [aspirin.product_id, ibuprofen.product_id], "branch_id": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["advisory"] is True
    assert body["count"] >= 1
    assert body["max_severity"] == "major"

    card = client.get(f"/api/clinical/products/{ibuprofen.product_id}?branch_id=1")
    assert card.status_code == 200
    assert card.json()["drug"]["active_ingredients"] == ["ibuprofen"]

    st = client.get("/api/clinical/status")
    assert st.status_code == 200 and st.json()["titan_source_configured"] is False


# --- AI assistant integration ----------------------------------------------
def test_assistant_routes_drug_question(session):
    res = ai.chat(session, "ايه بديل بانادول؟", branch_id=1, lang="ar")
    assert res["intent"] == "drug_advice"
    assert "بانادول" in res["answer"]


def test_assistant_drug_advice_english(session):
    res = ai.chat(session, "show me the dose for Brufen", branch_id=1, lang="en")
    assert res["intent"] == "drug_advice"
    assert "Brufen" in res["answer"]
