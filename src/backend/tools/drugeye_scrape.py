"""Drug-Eye online enrichment: scientific names, uses/indications, substitution.

The local Titan file gives identity but no indications and only partial
scientific coverage. The vendor's own web app (the same Drug-Eye product this
pharmacy licenses) exposes all three, so this fetches them into a STAGING
table. Nothing here touches eStock, and nothing is applied to `products` —
the catalogue review flow (services/catalogue.py) decides what to accept.

Being a good citizen is a hard requirement, not a nicety:
  * every response is CACHED on disk; a re-run costs zero requests
  * one request at a time, with a configurable delay (default 2.5s)
  * query by MOLECULE, not per product — one `geno`/`alto` call returns the
    whole substitution set (~200 drugs), so a 53k catalogue needs a few
    thousand requests, not a hundred thousand
  * resumable: interrupt any time, re-run continues where it stopped

Usage (from src/backend):
    python tools/drugeye_scrape.py --probe                  # 3 terms, prove it works
    python tools/drugeye_scrape.py --from-db --limit 200    # molecules needing data
    python tools/drugeye_scrape.py --terms ESOMEPRAZOLE,METFORMIN
Flags: --delay SECONDS, --no-monograph, --dry-run
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

BASE = "https://www.drugeye.pharorg.com/drugeyeapp/android-search/"
SEARCH = BASE + "drugeye-android-live-go.aspx"
MONOGRAPH = BASE + "apiforus/gi.aspx?passed="
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "drugeye_cache"

# Their TLS chain is incomplete; the host is correct but unverifiable. Scoped
# to this opener only — nothing else in ProCare relaxes verification.
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
_opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=_CTX),
    urllib.request.HTTPCookieProcessor(CookieJar()),
)
_opener.addheaders = [("User-Agent", "Mozilla/5.0 (ProCare pharmacy catalogue sync)"),
                      ("Referer", SEARCH)]

_last_call = [0.0]

# Monograph section headings, matched case-insensitively at the start of a
# caret-delimited part. Kept broad: an unrecognised heading only means its text
# lands in the previous section, never that data is lost.
# NB the trailing \w* (not \b): headings are usually PLURAL ("Indications for
# X"), and `indication\b` cannot match "Indications" because \b will not sit
# between "n" and "s".
_HEADING_RE = re.compile(
    r"(?i)^(about|mechanism|indication|contra-?indication|side ?effect|adverse|"
    r"dose|dosage|precaution|warning|interaction|pregnan|lactation|storage|"
    r"overdose|pharmacokinetic|pharmacodynamic|description|composition)\w*"
)


def _throttle(delay: float) -> None:
    wait = delay - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()


def _cache_path(key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", key)[:120]
    return CACHE_DIR / f"{safe}.html"


def _fetch(url: str, key: str, delay: float, data: dict | None = None) -> str:
    """GET/POST with an on-disk cache. Cached hits cost no request."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cp = _cache_path(key)
    if cp.exists():
        return cp.read_text(encoding="utf-8")
    _throttle(delay)
    if data is None:
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(
            url, data=urllib.parse.urlencode(data).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"})
    with _opener.open(req, timeout=45) as r:
        body = r.read().decode("utf-8", "replace")
    cp.write_text(body, encoding="utf-8")
    return body


def _txt(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", fragment))).strip()


def parse_results(page: str) -> list[dict]:
    """Drug-Eye renders five <tr> per drug, distinguished by inline colour:
    Blue = trade name + Red price, Black = scientific, Green = use,
    BlueViolet = manufacturer, and an options row carrying the drug id.

    NB: the colour test must reject 'BlueViolet' when looking for 'Blue',
    otherwise every manufacturer row starts a phantom drug.
    """
    out: list[dict] = []
    cur: dict = {}
    for tr in re.findall(r"(?is)<tr.*?</tr>", page):
        if "color:Blue;" in tr:
            if cur.get("trade_name"):
                out.append(cur)
            cur = {}
            tds = re.findall(r"(?is)<td.*?</td>", tr)
            if tds:
                cur["trade_name"] = _txt(tds[0])
            if len(tds) > 1:
                cur["price"] = _txt(tds[1])
        elif "color:Black;" in tr:
            cur["scientific_name"] = _txt(tr)
        elif "color:Green;" in tr:
            cur["use_category"] = _txt(tr)
        elif "color:BlueViolet;" in tr:
            cur["manufacturer"] = _txt(tr)
        elif "alto grado" in tr:
            m = re.search(r"class='lox alto grado' title='(\d+)'", tr)
            if m:
                cur["drug_id"] = m.group(1)
    if cur.get("trade_name"):
        out.append(cur)
    return out


def _viewstate(page: str) -> dict:
    out = {}
    for n in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        m = re.search(rf'id="{n}" value="([^"]*)"', page)
        if m:
            out[n] = html.unescape(m.group(1))
    return out


def search(term: str, delay: float) -> list[dict]:
    """Free-text search (trade name or molecule) via the WebForms postback."""
    shell = _fetch(SEARCH, "shell", delay)
    data = _viewstate(shell)
    data["ttt"] = term
    data["b1"] = "search"
    return parse_results(_fetch(SEARCH, f"search__{term}", delay, data=data))


def substitutes(drug_id: str, kind: str, delay: float) -> list[dict]:
    """kind='geno' -> same molecule (generic substitution);
       kind='alto' -> same therapeutic class (alternatives)."""
    url = f"{SEARCH}?gname={drug_id}{kind}"
    return parse_results(_fetch(url, f"{kind}__{drug_id}", delay))


def monograph(trade_name: str, delay: float) -> dict:
    """Clinical monograph: About / Mechanism / Indications, '^'-delimited."""
    page = _fetch(MONOGRAPH + urllib.parse.quote(trade_name),
                  f"mono__{trade_name}", delay)
    body = None
    for tr in re.findall(r"(?is)<tr.*?</tr>", page):
        if "color:Black;" in tr:
            body = _txt(tr)
            break
    if not body:
        return {}
    # Monograph layout is NOT consistent across drugs: some use '^^' between
    # sections (Esomeprazole), some only single '^' (Metformin), some open with
    # body text and no heading (Augmentin). Single carets ALSO separate numbered
    # list items ("1.Gastric ulcer ^2.GERD"). So don't trust separators —
    # split on every caret and recognise HEADINGS by shape; anything else is
    # body text appended to the section in progress.
    sections: dict[str, list[str]] = {}
    current = "notes"
    for part in (p.strip() for p in body.replace("^^", "^").split("^")):
        if not part:
            continue
        if _HEADING_RE.match(part) and len(part) < 80:
            current = part
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(part)
    joined = {k: " ".join(v).strip() for k, v in sections.items() if v}
    indications = next((v for k, v in joined.items() if "indication" in k.lower()), "")
    return {"sections": joined, "indications": indications, "raw": body}


def _terms_from_db(limit: int) -> list[str]:
    """Molecules worth fetching: those on products the pharmacy actually sells,
    heaviest sellers first, so a partial run still covers what matters."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sqlalchemy import text as sql

    from app.db.base import SessionLocal

    with SessionLocal() as s:
        rows = s.execute(sql(
            "SELECT TOP (:n) p.scientific_name, SUM(l.amount) qty "
            "FROM products p JOIN sale_lines l ON l.product_id = p.product_id "
            "JOIN sales sa ON sa.sale_id = l.sale_id AND sa.is_return = 0 "
            "WHERE p.is_deleted = 0 AND p.scientific_name IS NOT NULL "
            "AND p.scientific_name <> '' "
            "GROUP BY p.scientific_name ORDER BY SUM(l.amount) DESC"
        ), {"n": limit}).all()
    return [r[0] for r in rows if r[0]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--terms", help="comma-separated search terms")
    ap.add_argument("--from-db", action="store_true", help="top-selling molecules from ProCare")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--delay", type=float, default=float(os.environ.get("DRUGEYE_DELAY", 2.5)))
    ap.add_argument("--probe", action="store_true", help="3 terms, print what came back")
    ap.add_argument("--no-monograph", action="store_true")
    ap.add_argument("--out", default=str(CACHE_DIR.parent / "drugeye_harvest.jsonl"))
    args = ap.parse_args()

    if args.probe:
        terms = ["ESOMEPRAZOLE", "METFORMIN", "AUGMENTIN"]
    elif args.terms:
        terms = [t.strip() for t in args.terms.split(",") if t.strip()]
    elif args.from_db:
        terms = _terms_from_db(args.limit)
    else:
        ap.error("pass --terms, --from-db or --probe")

    print(f"{len(terms)} term(s) | delay {args.delay}s | cache {CACHE_DIR}")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen_ids: set[str] = set()
    written = 0
    with out_path.open("a", encoding="utf-8") as fh:
        for i, term in enumerate(terms, 1):
            try:
                hits = search(term, args.delay)
            except Exception as e:  # noqa: BLE001 — one bad term must not stop the run
                print(f"  [{i}/{len(terms)}] {term}: ERROR {type(e).__name__} {str(e)[:90]}")
                continue
            rec = {"term": term, "results": hits}
            if hits and hits[0].get("drug_id"):
                did = hits[0]["drug_id"]
                if did not in seen_ids:
                    seen_ids.add(did)
                    try:
                        rec["generics"] = substitutes(did, "geno", args.delay)
                        rec["alternatives"] = substitutes(did, "alto", args.delay)
                    except Exception as e:  # noqa: BLE001
                        print(f"      substitution failed: {str(e)[:70]}")
                if not args.no_monograph:
                    try:
                        rec["monograph"] = monograph(hits[0]["trade_name"], args.delay)
                    except Exception as e:  # noqa: BLE001
                        print(f"      monograph failed: {str(e)[:70]}")
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
            g, a = len(rec.get("generics", [])), len(rec.get("alternatives", []))
            ind = (rec.get("monograph") or {}).get("indications", "")
            print(f"  [{i}/{len(terms)}] {term}: {len(hits)} hits, "
                  f"{g} generics, {a} alternatives"
                  f"{', indications ✓' if ind else ''}")
            if args.probe and rec.get("monograph"):
                print("      indications:", (ind or "")[:160])

    print(f"\nwrote {written} record(s) -> {out_path}")
    print("Nothing was applied to products — feed this into the catalogue review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
