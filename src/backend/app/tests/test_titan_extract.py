"""Titan extractor unit tests — parsing, normalisation, match tiers.

Pure-function tests over synthetic 856-byte records; no Titan installation or
DB needed, so they run in CI like every other suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.titan_extract import (  # noqa: E402
    RECORD_SIZE,
    build_match_index,
    match_product,
    norm,
    norm_no_pack,
    norm_token_sorted,
    parse_record,
)


def make_record(
    name_en: str = "",
    name_ar: bytes = b"",
    manufacturer: str = "",
    scientific: str = "",
    category: str = "",
) -> bytes:
    rec = bytearray(b" " * RECORD_SIZE)
    rec[0:40] = name_en.encode("cp1256").ljust(40)[:40]
    rec[40:70] = name_ar.ljust(30)[:30]
    rec[70:90] = manufacturer.encode("cp1256").ljust(20)[:20]
    rec[90:130] = scientific.encode("cp1256").ljust(40)[:40]
    rec[792:856] = category.encode("cp1256").ljust(64)[:64]
    return bytes(rec)


def test_parse_record_extracts_all_fields():
    rec = make_record(
        name_en="AUGMENTIN 1GM 14 TAB",
        name_ar="أوجمنتين".encode("cp1256"),
        manufacturer="GSK",
        scientific="AMOXICILLIN+CLAVULANIC ACID",
        category="ANTIBIOTIC",
    )
    row = parse_record(4, rec)
    assert row is not None
    assert row["titan_drug_id"] == 5  # 1-based slot
    assert row["name_en"] == "AUGMENTIN 1GM 14 TAB"
    assert row["name_ar"] == "أوجمنتين"
    assert row["manufacturer"] == "GSK"
    assert row["scientific_name"] == "AMOXICILLIN+CLAVULANIC ACID"
    assert row["category"] == "ANTIBIOTIC"
    assert row["sci_norm"] == "AMOXICILLIN CLAVULANIC ACID"


def test_parse_record_skips_blank_slot():
    assert parse_record(0, b" " * RECORD_SIZE) is None
    assert parse_record(0, b"\x00" * RECORD_SIZE) is None


def test_parse_record_corrupted_arabic_becomes_null():
    # Some Titan exports contain literal UTF-8 replacement bytes where the
    # Arabic name was: the field must degrade to NULL, never mojibake.
    rec = make_record(name_en="PANADOL EXTRA", name_ar=b"\xef\xbf\xbd" * 8)
    row = parse_record(0, rec)
    assert row is not None
    assert row["name_ar"] is None
    assert row["name_en"] == "PANADOL EXTRA"


def test_norm_and_pack_stripping():
    # Digit/letter boundaries split so "1gm" and "1 GM" agree.
    assert norm("Augmentin-1gm  (14) tab.") == "AUGMENTIN 1 GM 14 TAB"
    assert norm("AUGMENTIN 1 GM 14 TAB") == "AUGMENTIN 1 GM 14 TAB"
    # Decimal strengths survive: 7.5 MG must never equal 75 MG.
    assert norm("MOBIC 7.5MG") == "MOBIC 7.5 MG"
    assert norm("MOBIC 7.5MG") != norm("MOBIC 75MG")
    # Box count folds away; strength does NOT.
    assert norm_no_pack("AUGMENTIN 1GM 14 TAB") == "AUGMENTIN 1 GM TAB"
    assert norm_no_pack("AUGMENTIN 1 GM 20 TAB") == "AUGMENTIN 1 GM TAB"
    assert norm_no_pack("MOBIC 15 MG 10 TAB") != norm_no_pack("MOBIC 7.5 MG 10 TAB")
    # Token order is free in the sorted key.
    assert norm_token_sorted("OTRIVIN SPRAY NASAL") == norm_token_sorted("OTRIVIN NASAL SPRAY")


def _titan_fixture() -> list[dict]:
    recs = [
        make_record(name_en="AUGMENTIN 1GM 14 TAB", scientific="AMOXICILLIN+CLAVULANIC ACID"),
        make_record(name_en="PANADOL EXTRA 24 TAB", scientific="PARACETAMOL+CAFFEINE"),
        # Two Titan rows sharing one normalised name -> ambiguous, unmatchable.
        make_record(name_en="DUPLICATE BRAND", scientific="A"),
        make_record(name_en="DUPLICATE  BRAND", scientific="B"),
    ]
    return [parse_record(i, r) for i, r in enumerate(recs)]


def test_match_tiers_and_ambiguity():
    tiers = build_match_index(_titan_fixture())

    hit = match_product("AUGMENTIN 1GM 14 TAB", tiers)
    assert hit is not None and hit[1] == "exact_name" and hit[2] == 100

    # Different box count -> Tier 2 (pack-stripped), same drug.
    hit = match_product("AUGMENTIN 1GM 20 TAB", tiers)
    assert hit is not None and hit[1] == "name_no_pack" and hit[2] == 90
    assert hit[0]["scientific_name"] == "AMOXICILLIN+CLAVULANIC ACID"

    # Token order differs -> Tier 3 (sorted tokens), same drug.
    hit = match_product("EXTRA PANADOL 24 TAB", tiers)
    assert hit is not None and hit[1] == "name_tokens" and hit[2] == 85
    assert hit[0]["scientific_name"] == "PARACETAMOL+CAFFEINE"

    # Ambiguous Titan name never matches; wrong clinical link is worse than none.
    assert match_product("DUPLICATE BRAND", tiers) is None
    # Unknown and empty names never match.
    assert match_product("NO SUCH PRODUCT 5 ML", tiers) is None
    assert match_product(None, tiers) is None
    assert match_product("", tiers) is None
