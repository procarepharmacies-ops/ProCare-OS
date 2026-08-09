"""GS1 payload parsing — pure functions, no DB, no fixtures.

Vectors live in fixtures/gs1_vectors.json and are shared with the JS mirror
(src/frontend/app/lib/__tests__/gs1.test.mjs) so the two parsers cannot drift.
"""
from __future__ import annotations

import json
import random
import string
from datetime import date
from pathlib import Path

import pytest

from app.services import gs1

_VECTORS = json.loads(
    (Path(__file__).parent / "fixtures" / "gs1_vectors.json").read_text(encoding="utf-8")
)["vectors"]


@pytest.mark.parametrize("vec", _VECTORS, ids=[v["name"] for v in _VECTORS])
def test_golden_vectors(vec):
    got = gs1.parse_gs1(vec["payload"])
    for key, expected in vec["expect"].items():
        assert got[key] == expected, f"{vec['name']}: {key}"


# ---- yymmdd_to_date ------------------------------------------------------

def test_day_zero_means_end_of_month():
    # Medicine packs are routinely dated to the month; GS1 encodes that as DD=00.
    assert gs1.yymmdd_to_date("260800", anchor=date(2026, 6, 26)) == date(2026, 8, 31)
    assert gs1.yymmdd_to_date("260200", anchor=date(2026, 6, 26)) == date(2026, 2, 28)


def test_leap_year_and_invalid_dates():
    assert gs1.yymmdd_to_date("240229", anchor=date(2026, 6, 26)) == date(2024, 2, 29)
    assert gs1.yymmdd_to_date("260231", anchor=date(2026, 6, 26)) is None  # must not raise
    assert gs1.yymmdd_to_date("261301", anchor=date(2026, 6, 26)) is None  # month 13
    assert gs1.yymmdd_to_date("26013", anchor=date(2026, 6, 26)) is None   # too short
    assert gs1.yymmdd_to_date("2601AB", anchor=date(2026, 6, 26)) is None  # non-numeric


def test_century_sliding_window_is_anchored():
    """Century resolution must follow the anchor, not the wall clock.

    Anchored explicitly so this test states the rule rather than quietly
    changing meaning decades from now.
    """
    anchor = date(2026, 6, 26)
    assert gs1.yymmdd_to_date("270101", anchor=anchor) == date(2027, 1, 1)
    assert gs1.yymmdd_to_date("990101", anchor=anchor) == date(1999, 1, 1)  # -50 .. +49
    assert gs1.yymmdd_to_date("750101", anchor=anchor) == date(2075, 1, 1)


# ---- GTIN normalization --------------------------------------------------

def test_normalize_gtin_pads_and_validates():
    assert gs1.normalize_gtin("4006358001238") == "04006358001238"
    assert gs1.normalize_gtin("04006358001238") == "04006358001238"


def test_normalize_gtin_rejects_non_gtins():
    # These are the shapes the dev seed actually uses — proof that Product.code
    # is not automatically a GTIN and must not be treated as one.
    assert gs1.normalize_gtin("P1000") is None
    assert gs1.normalize_gtin("100") is None
    assert gs1.normalize_gtin("4006358001239") is None  # mutated check digit
    assert gs1.normalize_gtin(None) is None
    assert gs1.normalize_gtin("") is None


def test_gtin_variants_include_ean13():
    variants = gs1.gtin_variants("04006358001238")
    assert "04006358001238" in variants
    assert "4006358001238" in variants


# ---- Totality ------------------------------------------------------------

def test_parse_never_raises_on_random_input():
    """A camera feeding noise must degrade to 'unknown', never to a 500."""
    alphabet = string.printable + gs1.GS
    rng = random.Random(20260726)  # seeded: a failure is reproducible
    keys = {"is_gs1", "gtin", "expiry", "expiry_raw", "lot", "serial", "ais",
            "unparsed", "heuristic_split"}
    for _ in range(200):
        payload = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        out = gs1.parse_gs1(payload)
        assert isinstance(out, dict)
        assert keys <= set(out)


def test_parse_handles_non_string_input():
    for bad in (None, 12345, [], {}):
        assert gs1.parse_gs1(bad)["is_gs1"] is False
