// GS1 payload parsing in the browser — a deliberate mirror of the Python
// services/gs1.py, needed so a scan still resolves when there is no network.
//
// Duplicated logic is a real cost. The anti-drift mechanism is the SHARED
// golden-vector fixture at src/backend/app/tests/fixtures/gs1_vectors.json,
// read by both the pytest suite and `npm test` (app/lib/__tests__/gs1.test.mjs).
// Change one parser and the other's tests fail on the same vectors.
//
// Keep behaviour identical to the Python version, including its quirks:
// day 00 = end of month, the +/-50 century window, and the guard that stops a
// bare EAN-13 (which starts "40", a valid AI prefix) being read as element
// strings.

export const GS = "\x1d";

const SYMBOLOGY_PREFIXES = ["]d2", "]C1", "]e0", "]e1", "]Q3", "]d1"];

export const FIXED_LENGTH_AIS = {
  "00": 18, "01": 14, "02": 14,
  11: 6, 12: 6, 13: 6, 15: 6, 16: 6, 17: 6,
  20: 2,
  410: 13, 411: 13, 412: 13, 413: 13, 414: 13, 415: 13, 416: 13,
};

export const KNOWN_VARIABLE_AIS = new Set([
  "10", "21", "22", "240", "241", "30", "37",
  "90", "91", "92", "93", "94", "95", "96", "97", "98", "99",
  "710", "711", "712", "713", "714",
]);

export function gtinCheckDigit(body) {
  let total = 0;
  const rev = String(body).split("").reverse();
  for (let i = 0; i < rev.length; i += 1) {
    total += Number(rev[i]) * (i % 2 === 0 ? 3 : 1);
  }
  return String((10 - (total % 10)) % 10);
}

export function normalizeGtin(raw) {
  if (raw === null || raw === undefined) return null;
  const s = String(raw).trim();
  if (!/^\d+$/.test(s)) return null;
  if (![8, 12, 13, 14].includes(s.length)) return null;
  if (gtinCheckDigit(s.slice(0, -1)) !== s.slice(-1)) return null;
  return s.padStart(14, "0");
}

export function gtinVariants(gtin14) {
  if (!gtin14) return [];
  const out = [];
  const seen = new Set();
  for (const candidate of [gtin14, gtin14.replace(/^0+/, "")]) {
    for (const c of [candidate, candidate.padStart(13, "0"), candidate.padStart(12, "0"), candidate.padStart(8, "0")]) {
      if (c && c.length >= 8 && !seen.has(c)) {
        seen.add(c);
        out.push(c);
      }
    }
  }
  return out;
}

function daysInMonth(year, month) {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/** GS1 YYMMDD -> "YYYY-MM-DD", or null. `anchor` is a Date (defaults to now). */
export function yymmddToDate(s, anchor) {
  if (!s || s.length !== 6 || !/^\d{6}$/.test(s)) return null;
  const yy = Number(s.slice(0, 2));
  const mm = Number(s.slice(2, 4));
  let dd = Number(s.slice(4, 6));
  if (mm < 1 || mm > 12) return null;

  const base = (anchor || new Date()).getFullYear();
  const century = Math.floor((base - 50) / 100) * 100;
  let year = century + yy;
  if (year < base - 50) year += 100;
  else if (year > base + 49) year -= 100;

  const maxDay = daysInMonth(year, mm);
  if (dd === 0) dd = maxDay; // GS1: day 00 means end of month
  else if (dd > maxDay) return null;

  const p = (n) => String(n).padStart(2, "0");
  return `${year}-${p(mm)}-${p(dd)}`;
}

function findAiSplit(s, start) {
  for (let idx = start + 1; idx < s.length; idx += 1) {
    for (const width of [2, 3, 4]) {
      const ai = s.slice(idx, idx + width);
      if (ai.length < width) continue;
      if (Object.prototype.hasOwnProperty.call(FIXED_LENGTH_AIS, ai)) {
        if (s.length - (idx + width) >= FIXED_LENGTH_AIS[ai]) return idx;
      } else if (KNOWN_VARIABLE_AIS.has(ai) && idx + width < s.length) {
        return idx;
      }
    }
  }
  return null;
}

const EMPTY = {
  is_gs1: false, gtin: null, expiry: null, expiry_raw: null,
  lot: null, serial: null, ais: {}, unparsed: null, heuristic_split: false,
};

/** Parse a scanned payload. Never throws — camera noise must not break the UI. */
export function parseGs1(payload, anchor) {
  if (!payload || typeof payload !== "string") return { ...EMPTY };

  let s = payload.trim();
  for (const prefix of SYMBOLOGY_PREFIXES) {
    if (s.startsWith(prefix)) {
      s = s.slice(prefix.length);
      break;
    }
  }
  while (s.startsWith(GS)) s = s.slice(1);
  if (!s) return { ...EMPTY };

  // A bare GTIN is not element-string data.
  if (normalizeGtin(s)) return { ...EMPTY };

  const ais = {};
  let unparsed = null;
  let heuristic = false;
  let i = 0;
  while (i < s.length) {
    if (s[i] === GS) {
      i += 1;
      continue;
    }
    let ai = null;
    for (const width of [2, 3, 4]) {
      const candidate = s.slice(i, i + width);
      if (candidate.length < width) break;
      if (Object.prototype.hasOwnProperty.call(FIXED_LENGTH_AIS, candidate) || KNOWN_VARIABLE_AIS.has(candidate)) {
        ai = candidate;
        break;
      }
    }
    if (ai === null) {
      unparsed = s.slice(i);
      break;
    }
    i += ai.length;

    let value;
    if (Object.prototype.hasOwnProperty.call(FIXED_LENGTH_AIS, ai)) {
      const length = FIXED_LENGTH_AIS[ai];
      value = s.slice(i, i + length);
      i += length;
    } else {
      const end = s.indexOf(GS, i);
      if (end === -1) {
        const split = findAiSplit(s, i);
        if (split === null) {
          value = s.slice(i);
          i = s.length;
        } else {
          value = s.slice(i, split);
          i = split;
          heuristic = true;
        }
      } else {
        value = s.slice(i, end);
        i = end + 1;
      }
    }
    if (value && ais[ai] === undefined) ais[ai] = value;
  }

  // Short internal codes can look like element strings ("100" -> AI 10 "0").
  // A real pack always carries a GTIN; anything else needs a separator.
  const looksStructural = ais["01"] !== undefined || ais["02"] !== undefined || payload.includes(GS);
  if (!Object.keys(ais).length || !looksStructural) return { ...EMPTY };

  const expiryRaw = ais["17"] || null;
  return {
    is_gs1: true,
    gtin: normalizeGtin(ais["01"]),
    expiry: expiryRaw ? yymmddToDate(expiryRaw, anchor) : null,
    expiry_raw: expiryRaw,
    lot: ais["10"] || null,
    serial: ais["21"] || null,
    ais,
    unparsed,
    heuristic_split: heuristic,
  };
}

/**
 * Resolve a scanned payload against a cached scan index — the offline twin of
 * the server's scan_lookup, returning the same shape so the UI needs no branch.
 */
export function resolveOffline(index, code, anchor) {
  const raw = (code || "").trim();
  const parsed = parseGs1(raw, anchor);
  const scan = {
    kind: parsed.is_gs1 ? "gs1" : "plain",
    gtin: parsed.gtin,
    expiry: parsed.expiry,
    lot: parsed.lot,
    serial: parsed.serial,
  };
  if (!raw) return { result: "unknown", code: raw, scan };

  // Match on the GTIN (and its de-padded forms) or on the raw code.
  const wanted = new Set(parsed.gtin ? gtinVariants(parsed.gtin) : []);
  if (parsed.gtin) wanted.add(parsed.gtin);
  if (!parsed.is_gs1) {
    wanted.add(raw);
    const asGtin = normalizeGtin(raw);
    if (asGtin) gtinVariants(asGtin).forEach((v) => wanted.add(v));
  }

  const item = (index?.items || []).find((it) => (it.codes || []).some((c) => wanted.has(c)));
  if (!item) return { result: "unknown", code: raw, scan };

  const product = {
    product_id: item.product_id,
    code: item.codes?.[0] ?? null,
    fast_code: null,
    name_ar: item.name_ar,
    name_en: item.name_en,
    shelf_location: item.shelf_location,
    unit_big: item.unit_big,
    unit_small: null,
  };
  if (!item.lines?.length) return { result: "not_in_count", code: raw, scan, product };

  let matchedLineId = null;
  const lines = item.lines.map((l) => {
    const batchMatch = Boolean(parsed.expiry && l.exp_date && l.exp_date === parsed.expiry);
    if (batchMatch && matchedLineId === null) matchedLineId = l.line_id;
    return { ...l, batch_match: batchMatch };
  });

  return {
    result: "found",
    code: raw,
    scan,
    product,
    lines,
    matched_line_id: matchedLineId,
    expiry_mismatch: Boolean(parsed.expiry && matchedLineId === null),
  };
}
