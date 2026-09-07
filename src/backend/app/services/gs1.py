"""GS1 DataMatrix / barcode payload parsing (pure — no DB, no I/O).

Egypt's EDA track-and-trace mandate (ePTTS) requires a GS1 DataMatrix on every
saleable pharmaceutical pack: imported finished products from 2026-02-01, local
production from 2026-08-01. The code carries, as Application Identifiers:

    (01) GTIN          (17) expiry YYMMDD     (10) batch/lot     (21) serial

That is worth far more than a plain EAN for الجرد: the expiry pins the exact
**batch**, and count lines are per-batch — so a scan lands on one row instead of
"this product has four batches, which one is in your hand?".

Everything here is total: ``parse_gs1`` never raises, on any input. A scanner
feeding us camera noise must degrade to "unknown code", never to a 500.
"""
from __future__ import annotations

import calendar
from datetime import date

from app.services.common import today

# Separator emitted for FNC1 by most scanners/decoders.
GS = "\x1d"

# Symbology identifiers some decoders prepend (]d2 = DataMatrix/GS1, ]C1 =
# GS1-128, ]e0 = GS1 DataBar, ]Q3 = GS1 QR).
_SYMBOLOGY_PREFIXES = ("]d2", "]C1", "]e0", "]e1", "]Q3", "]d1")

# AIs whose value length is fixed by the spec — no separator follows them, so
# they can be parsed unambiguously even when a decoder strips the GS bytes.
FIXED_LENGTH_AIS: dict[str, int] = {
    "00": 18, "01": 14, "02": 14,
    "11": 6, "12": 6, "13": 6, "15": 6, "16": 6, "17": 6,
    "20": 2,
    "410": 13, "411": 13, "412": 13, "413": 13, "414": 13, "415": 13, "416": 13,
}

# Variable-length AIs we care about (value runs to the next GS or end of data).
KNOWN_VARIABLE_AIS: frozenset[str] = frozenset(
    {"10", "21", "22", "240", "241", "30", "37", "90", "91", "92", "93", "94", "95",
     "96", "97", "98", "99", "710", "711", "712", "713", "714"}
)


def gtin_check_digit(body: str) -> str:
    """Mod-10 check digit for a GTIN *without* its final digit."""
    total = 0
    # Weights alternate 3,1,3,1… reading right-to-left from the check position.
    for i, ch in enumerate(reversed(body)):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return str((10 - (total % 10)) % 10)


def normalize_gtin(raw: str | None) -> str | None:
    """Digits-only GTIN-8/12/13/14 -> zero-padded GTIN-14, else ``None``.

    Validates the check digit, so arbitrary product codes ("P1000") and short
    internal codes ("100") are rejected rather than silently treated as GTINs.
    """
    if not raw:
        return None
    s = str(raw).strip()
    if not s.isdigit() or len(s) not in (8, 12, 13, 14):
        return None
    if gtin_check_digit(s[:-1]) != s[-1]:
        return None
    return s.zfill(14)


def gtin_variants(gtin14: str | None) -> list[str]:
    """Every de-padded form of a GTIN-14, longest first.

    ``Product.code`` mirrors whatever eStock holds, which may be the EAN-13 or a
    shorter form. Matching against all variants keeps resolution tolerant.
    """
    if not gtin14:
        return []
    out, seen = [], set()
    for candidate in (gtin14, gtin14.lstrip("0")):
        for c in (candidate, candidate.zfill(13), candidate.zfill(12), candidate.zfill(8)):
            if c and c not in seen and len(c) >= 8:
                seen.add(c)
                out.append(c)
    return out


def yymmdd_to_date(s: str, *, anchor: date | None = None) -> date | None:
    """GS1 YYMMDD (AI 11/12/13/15/16/17) -> date. ``None`` when unparseable.

    Two spec details that matter in practice:
    * ``DD == "00"`` means "end of that month" — extremely common on medicine
      packs, which are dated to the month.
    * The century comes from GS1's sliding window: the year is taken to be
      within ``[anchor-50, anchor+49]``. ``anchor`` defaults to ``common.today``
      so tests are deterministic under the frozen DEMO_TODAY rather than
      quietly changing behaviour in 2077.
    """
    if not s or len(s) != 6 or not s.isdigit():
        return None
    yy, mm, dd = int(s[0:2]), int(s[2:4]), int(s[4:6])
    if not 1 <= mm <= 12:
        return None

    base = (anchor or today()).year
    # Pick the century that lands the year inside the -50/+49 window.
    century = (base - 50) // 100 * 100
    year = century + yy
    if year < base - 50:
        year += 100
    elif year > base + 49:
        year -= 100

    if dd == 0:
        dd = calendar.monthrange(year, mm)[1]
    try:
        return date(year, mm, dd)
    except ValueError:  # e.g. 260231
        return None


def _looks_like_plain_gtin(payload: str) -> bool:
    """True for a bare EAN/UPC that merely *starts* with digits resembling an AI.

    A plain EAN-13 like ``4006358001234`` begins with "40", a valid AI prefix,
    so without this guard it would be mis-parsed as GS1 element strings.
    """
    return normalize_gtin(payload) is not None


def parse_gs1(payload: str) -> dict:
    """Parse a scanned payload. Never raises.

    Returns ``{is_gs1, gtin, expiry, expiry_raw, lot, serial, ais, unparsed,
    heuristic_split}``; a non-GS1 payload comes back with ``is_gs1=False`` and
    everything else empty, so callers can always read the same shape.
    """
    empty = {
        "is_gs1": False, "gtin": None, "expiry": None, "expiry_raw": None,
        "lot": None, "serial": None, "ais": {}, "unparsed": None,
        "heuristic_split": False,
    }
    if not payload or not isinstance(payload, str):
        return empty

    s = payload.strip()
    for prefix in _SYMBOLOGY_PREFIXES:
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    s = s.lstrip(GS)  # leading FNC1
    if not s:
        return empty

    # A bare GTIN is not GS1 element-string data — check before AI parsing.
    if _looks_like_plain_gtin(s):
        return empty

    ais: dict[str, str] = {}
    unparsed: str | None = None
    heuristic = False
    i = 0
    while i < len(s):
        if s[i] == GS:
            i += 1
            continue
        ai = None
        for width in (2, 3, 4):
            candidate = s[i:i + width]
            if len(candidate) < width:
                break
            if candidate in FIXED_LENGTH_AIS or candidate in KNOWN_VARIABLE_AIS:
                ai = candidate
                break
        if ai is None:
            unparsed = s[i:]
            break
        i += len(ai)

        if ai in FIXED_LENGTH_AIS:
            length = FIXED_LENGTH_AIS[ai]
            value = s[i:i + length]
            i += length
        else:
            end = s.find(GS, i)
            if end == -1:
                # No separator. Either the value runs to the end, or a decoder
                # stripped the GS bytes and another AI is concatenated. Look for
                # a split where the remainder parses cleanly; otherwise take all.
                split = _find_ai_split(s, i)
                if split is None:
                    value = s[i:]
                    i = len(s)
                else:
                    value = s[i:split]
                    i = split
                    heuristic = True
            else:
                value = s[i:end]
                i = end + 1
        if value:
            ais.setdefault(ai, value)

    # Structural guard. Short internal codes can accidentally look like element
    # strings — "100" would otherwise parse as AI 10 with value "0". A real pack
    # code always carries a GTIN (AI 01/02); anything else must at least contain
    # a separator to be credible as GS1.
    looks_structural = "01" in ais or "02" in ais or GS in s
    if not ais or not looks_structural:
        return empty

    expiry_raw = ais.get("17")
    return {
        "is_gs1": True,
        "gtin": normalize_gtin(ais.get("01")),
        "expiry": yymmdd_to_date(expiry_raw) if expiry_raw else None,
        "expiry_raw": expiry_raw,
        "lot": ais.get("10"),
        "serial": ais.get("21"),
        "ais": ais,
        "unparsed": unparsed,
        "heuristic_split": heuristic,
    }


def _find_ai_split(s: str, start: int) -> int | None:
    """Index >= start+1 where a known AI begins and the rest parses to the end.

    Best-effort recovery for decoders that drop FNC1/GS separators. Returns
    ``None`` when no clean split exists (then the value runs to the end).
    """
    for idx in range(start + 1, len(s)):
        for width in (2, 3, 4):
            ai = s[idx:idx + width]
            if len(ai) < width:
                continue
            if ai in FIXED_LENGTH_AIS:
                # A fixed-length AI must have exactly its length available.
                if len(s) - (idx + width) >= FIXED_LENGTH_AIS[ai]:
                    return idx
            elif ai in KNOWN_VARIABLE_AIS and idx + width < len(s):
                return idx
    return None
