// Anti-drift guard for the duplicated GS1 parser.
//
// Reads the SAME golden vectors as the Python suite
// (src/backend/app/tests/fixtures/gs1_vectors.json), so changing one parser
// without the other fails here on identical inputs.
//
// Uses node:test — built into Node 18+, so this adds no dependency to a repo
// that deliberately has almost none. Run with `npm test`.

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { parseGs1, normalizeGtin, gtinVariants, yymmddToDate, resolveOffline, GS } from "../gs1.js";

const here = dirname(fileURLToPath(import.meta.url));
const fixture = resolve(here, "../../../../backend/app/tests/fixtures/gs1_vectors.json");
const { vectors } = JSON.parse(readFileSync(fixture, "utf8"));

// The vectors are anchored on the frozen DEMO_TODAY so century resolution is
// deterministic in both languages.
const ANCHOR = new Date(Date.UTC(2026, 5, 26));

test("golden vectors match the Python parser", () => {
  assert.ok(vectors.length >= 10, "fixture should carry the full vector set");
  for (const vec of vectors) {
    const got = parseGs1(vec.payload, ANCHOR);
    for (const [key, expected] of Object.entries(vec.expect)) {
      assert.deepEqual(got[key], expected, `${vec.name}: ${key}`);
    }
  }
});

test("day 00 means end of month", () => {
  assert.equal(yymmddToDate("260800", ANCHOR), "2026-08-31");
  assert.equal(yymmddToDate("260200", ANCHOR), "2026-02-28");
});

test("invalid dates return null instead of throwing", () => {
  assert.equal(yymmddToDate("260231", ANCHOR), null);
  assert.equal(yymmddToDate("261301", ANCHOR), null);
  assert.equal(yymmddToDate("2601AB", ANCHOR), null);
  assert.equal(yymmddToDate("26013", ANCHOR), null);
});

test("leap day is accepted", () => {
  assert.equal(yymmddToDate("240229", ANCHOR), "2024-02-29");
});

test("century window is anchored, not wall-clock", () => {
  assert.equal(yymmddToDate("270101", ANCHOR), "2027-01-01");
  assert.equal(yymmddToDate("990101", ANCHOR), "1999-01-01");
  assert.equal(yymmddToDate("750101", ANCHOR), "2075-01-01");
});

test("GTIN normalization matches Python", () => {
  assert.equal(normalizeGtin("4006358001238"), "04006358001238");
  assert.equal(normalizeGtin("04006358001238"), "04006358001238");
  assert.equal(normalizeGtin("4006358001239"), null); // bad check digit
  assert.equal(normalizeGtin("P1000"), null);
  assert.equal(normalizeGtin("100"), null);
  assert.equal(normalizeGtin(null), null);
  assert.ok(gtinVariants("04006358001238").includes("4006358001238"));
});

test("parsing never throws on random input", () => {
  const alphabet = "0123456789ABCXYZ]|-" + GS;
  let seed = 20260726;
  const rand = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };
  for (let n = 0; n < 200; n += 1) {
    let s = "";
    const len = Math.floor(rand() * 40);
    for (let i = 0; i < len; i += 1) s += alphabet[Math.floor(rand() * alphabet.length)];
    const out = parseGs1(s, ANCHOR);
    assert.equal(typeof out, "object");
    assert.ok("is_gs1" in out && "gtin" in out && "expiry" in out);
  }
});

// ---- offline resolution --------------------------------------------------

const INDEX = {
  count_id: 1,
  status: "open",
  items: [
    {
      product_id: 5,
      name_ar: "بانادول",
      name_en: "Panadol",
      shelf_location: "A3",
      unit_big: "علبة",
      codes: ["P1042", "04006358001238"],
      lines: [
        { line_id: 11, batch_id: 101, exp_date: "2027-03-31", expected_qty: 12, counted_qty: null },
        { line_id: 12, batch_id: 102, exp_date: "2028-01-31", expected_qty: 4, counted_qty: null },
      ],
    },
  ],
};

test("offline resolve pins the batch by GS1 expiry", () => {
  const payload = "01" + "04006358001238" + "17" + "270331" + "10" + "LOT1";
  const r = resolveOffline(INDEX, payload, ANCHOR);
  assert.equal(r.result, "found");
  assert.equal(r.scan.kind, "gs1");
  assert.equal(r.matched_line_id, 11);
  assert.equal(r.expiry_mismatch, false);
  assert.deepEqual(r.lines.filter((l) => l.batch_match).map((l) => l.line_id), [11]);
});

test("offline resolve flags an unbooked batch but still finds the product", () => {
  const payload = "01" + "04006358001238" + "17" + "301231";
  const r = resolveOffline(INDEX, payload, ANCHOR);
  assert.equal(r.result, "found");
  assert.equal(r.matched_line_id, null);
  assert.equal(r.expiry_mismatch, true);
});

test("offline resolve matches a plain internal code", () => {
  const r = resolveOffline(INDEX, "P1042", ANCHOR);
  assert.equal(r.result, "found");
  assert.equal(r.scan.kind, "plain");
  assert.equal(r.matched_line_id, null);
});

test("offline resolve reports unknown codes", () => {
  assert.equal(resolveOffline(INDEX, "NOPE-123", ANCHOR).result, "unknown");
  assert.equal(resolveOffline(INDEX, "", ANCHOR).result, "unknown");
});
