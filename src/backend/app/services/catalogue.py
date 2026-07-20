"""Catalogue quality: duplicate detection + Titan enrichment proposals.

Two jobs, both READ-ONLY against eStock (ProCare never writes to the source;
any correction is exported later as an explicitly-approved, reviewed step):

  * ``duplicate_groups`` — products that are the same real item entered more
    than once. Each group carries the EVIDENCE needed to pick a survivor
    safely: stock on hand, lifetime sales, last sale date, price. Rows are
    never auto-merged or deleted — sale/purchase history points at them.
  * ``enrichment_proposals`` — per-product field diffs (current eStock value vs
    the Titan value) for scientific name / names / medicine flag / origin /
    category, staged for human approval.

Matching a duplicate is deliberately conservative: an over-eager merge in a
pharmacy loses stock or history. Tiers, strongest first:
  1. ``code``       — identical non-empty barcode/code (near-certain)
  2. ``exact_name`` — identical normalised Arabic or English name
  3. ``name_pack``  — identical name once the pack-count token is dropped
                      (SAME strength required — never merges 500mg with 1g)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.services.common import money

# Reuse the extractor's normalisation rules so ProCare and the Titan tool agree.
_PACK_WORDS = (r"TAB|TABS|TABLET|TABLETS|CAP|CAPS|CAPSULE|CAPSULES|AMP|AMPS|"
               r"VIAL|VIALS|SACHET|SACHETS|SACH|SUPP|SUPPS|ML|GM")
_PACK_RE = re.compile(rf"\b\d+\s*({_PACK_WORDS})\b")
_NORM_RE = re.compile(r"[^A-Z0-9؀-ۿ.]+")
_DIGIT_ALPHA_RE = re.compile(r"(?<=[0-9])(?=[A-Z])|(?<=[A-Z])(?=[0-9])")
# Strength tokens must survive normalisation — 500 MG and 1 GM are NOT the same
# product, and merging them would be a dispensing error.
_STRENGTH_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:MG|MCG|GM|G|ML|IU|%)\b")


def _norm(s: str | None) -> str:
    if not s:
        return ""
    up = _NORM_RE.sub(" ", s.upper())
    up = _DIGIT_ALPHA_RE.sub(" ", up)
    return " ".join(up.split()).strip(".")


def _norm_no_pack(s: str | None) -> str:
    """Name with the box-count dropped but every strength token kept."""
    n = _norm(s)
    strengths = " ".join(sorted(_STRENGTH_RE.findall(n)))
    stripped = " ".join(_PACK_RE.sub(r"\1", n).split())
    return f"{stripped}|{strengths}"


def duplicate_groups(
    session: Session,
    branch_id: int | None = None,
    limit: int = 500,
    min_group: int = 2,
) -> dict:
    """Suspected duplicate products, grouped, with survivor-choice evidence.

    Returns groups sorted by risk: the ones holding real stock or recent sales
    matter most, because those are the ones actively splitting the pharmacy's
    inventory across two records.
    """
    products = session.execute(
        select(
            m.Product.product_id, m.Product.code, m.Product.name_ar, m.Product.name_en,
            m.Product.sell_price, m.Product.buy_price, m.Product.scientific_name,
            m.Product.is_active,
        ).where(m.Product.is_deleted == False)  # noqa: E712
    ).all()

    # Evidence: on-hand per product, lifetime units sold, last sale date.
    stock = dict(session.execute(
        select(m.StockBatch.product_id, func.coalesce(func.sum(m.StockBatch.amount), 0))
        .where(*( [m.StockBatch.branch_id == branch_id] if branch_id else [] ))
        .group_by(m.StockBatch.product_id)
    ).all())
    sales = {
        pid: (float(qty or 0), last)
        for pid, qty, last in session.execute(
            select(
                m.SaleLine.product_id,
                func.coalesce(func.sum(m.SaleLine.amount), 0),
                func.max(m.Sale.sale_date),
            )
            .join(m.Sale, m.Sale.sale_id == m.SaleLine.sale_id)
            .where(m.Sale.is_return == False)  # noqa: E712
            .group_by(m.SaleLine.product_id)
        ).all()
    }

    # Build candidate groups per tier; a product joins the STRONGEST tier only.
    buckets: dict[tuple[str, str], list] = defaultdict(list)
    for p in products:
        code = (p.code or "").strip()
        if code:
            buckets[("code", code.upper())].append(p)
    grouped_ids = {p.product_id for k, v in buckets.items() if len(v) >= min_group for p in v}

    for p in products:
        if p.product_id in grouped_ids:
            continue
        for key in filter(None, (_norm(p.name_en), _norm(p.name_ar))):
            buckets[("exact_name", key)].append(p)
            break
    grouped_ids |= {p.product_id for (t, _), v in buckets.items()
                    if t == "exact_name" and len(v) >= min_group for p in v}

    for p in products:
        if p.product_id in grouped_ids:
            continue
        key = _norm_no_pack(p.name_en) or _norm_no_pack(p.name_ar)
        if key and key.strip("|"):
            buckets[("name_pack", key)].append(p)

    out = []
    for (tier, key), members in buckets.items():
        if len(members) < min_group:
            continue
        rows = []
        for p in members:
            qty, last = sales.get(p.product_id, (0.0, None))
            rows.append({
                "product_id": p.product_id,
                "code": p.code,
                "name_ar": p.name_ar,
                "name_en": p.name_en,
                "scientific_name": p.scientific_name,
                "sell_price": money(p.sell_price),
                "buy_price": money(p.buy_price),
                "on_hand": money(stock.get(p.product_id, 0)),
                "units_sold": money(qty),
                "last_sale": last.isoformat() if last else None,
                "is_active": bool(p.is_active),
            })
        # Suggested survivor: most sold, then most stock, then lowest id
        # (oldest record). Only ever a SUGGESTION — a human confirms.
        rows.sort(key=lambda r: (-r["units_sold"], -r["on_hand"], r["product_id"]))
        suggested = rows[0]["product_id"]
        live = sum(1 for r in rows if r["on_hand"] > 0)
        # Confidence that this really is ONE item entered twice — distinct from
        # `risk` (how much it currently costs). ``name_pack`` ignores the box
        # count, so it also catches LEGITIMATE pack variants (3 TAB vs 5 TAB
        # are separate sellable SKUs): those must be eyeballed, never bulk-merged.
        confidence = {"code": "high", "exact_name": "high"}.get(tier, "review")
        out.append({
            "tier": tier,
            "confidence": confidence,
            "key": key,
            "size": len(rows),
            "suggested_survivor": suggested,
            "copies_holding_stock": live,
            # Splitting live stock across copies is the costly case.
            "risk": "high" if live > 1 else ("medium" if live == 1 else "low"),
            "members": rows,
        })

    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda g: (order[g["risk"]], -sum(r["units_sold"] for r in g["members"])))
    total = len(out)
    out = out[:limit]
    return {
        "group_count": total,
        "shown": len(out),
        "affected_products": sum(g["size"] for g in out),
        "high_risk": sum(1 for g in out if g["risk"] == "high"),
        # Only high-confidence groups are safe to action in bulk; "review"
        # groups (pack-size variants) need a human on every one.
        "high_confidence": sum(1 for g in out if g["confidence"] == "high"),
        "needs_review": sum(1 for g in out if g["confidence"] == "review"),
        "groups": out,
    }


# Fields the enrichment can propose. eStock columns are the write-back target;
# ProCare mirrors them, so a proposal is expressed in ProCare terms.
PROPOSABLE = ("scientific_name", "name_en", "name_ar", "is_medicine", "origin",
              "category", "uses")

# Where the Drug-Eye harvester writes its JSONL (tools/drugeye_scrape.py).
_HARVEST = Path(__file__).resolve().parents[2] / "data" / "drugeye_harvest.jsonl"


@lru_cache(maxsize=1)
def _drugeye_index(mtime: float) -> dict[str, dict]:
    """{normalised trade name -> {scientific_name, use_category, uses,
    manufacturer}} from the harvest file.

    Keyed on the file's mtime so the cache invalidates itself when a new
    harvest lands, without a restart. A missing or partially-written file is
    not an error: Drug-Eye enrichment is additive, and Titan alone must still
    work (the harvest is a long background run, so partial reads are normal).
    """
    idx: dict[str, dict] = {}
    if not _HARVEST.exists():
        return idx
    with _HARVEST.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            indications = (rec.get("monograph") or {}).get("indications") or ""
            # The term's own hits plus every generic/alternative it returned —
            # one molecule query enriches ~200 trade names.
            for bucket in ("results", "generics", "alternatives"):
                for d in rec.get(bucket) or []:
                    name = _norm(d.get("trade_name"))
                    if not name:
                        continue
                    entry = idx.setdefault(name, {})
                    for src, dst in (("scientific_name", "scientific_name"),
                                     ("use_category", "category"),
                                     ("manufacturer", "manufacturer")):
                        if d.get(src) and not entry.get(dst):
                            entry[dst] = d[src]
                    # Indications belong to the queried drug, not its whole
                    # substitution set — only attach to the term's own hits.
                    if bucket == "results" and indications and not entry.get("uses"):
                        entry["uses"] = indications[:300]
    return idx


def drugeye_lookup() -> dict[str, dict]:
    """Harvest index, auto-refreshed when the file changes."""
    try:
        return _drugeye_index(_HARVEST.stat().st_mtime)
    except FileNotFoundError:
        return {}


def enrichment_proposals(
    session: Session,
    only_missing: bool = True,
    limit: int = 1000,
    min_score: int = 85,
) -> dict:
    """Per-product field diffs from the matched Titan drug, for human review.

    ``only_missing`` (default) proposes a value ONLY where eStock has none —
    the safe default. Turn it off to also surface disagreements, where Titan
    and eStock both have a value but differ.
    """
    rows = session.execute(
        select(
            m.Product.product_id, m.Product.code, m.Product.name_ar, m.Product.name_en,
            m.Product.scientific_name, m.Product.dosage_form, m.Product.uses,
            m.Product.titan_match_method,
            m.Product.titan_match_score,
            m.TitanDrug.name_en.label("t_name_en"), m.TitanDrug.name_ar.label("t_name_ar"),
            m.TitanDrug.scientific_name.label("t_sci"), m.TitanDrug.category.label("t_cat"),
            m.TitanDrug.origin.label("t_origin"), m.TitanDrug.is_medicine.label("t_med"),
        )
        # OUTER join: a product needs a Titan match OR a Drug-Eye hit to be
        # proposable. Requiring Titan would lock out `uses`, which only
        # Drug-Eye supplies — and Titan matches just 4.3k of 53k products.
        .outerjoin(m.TitanDrug, m.TitanDrug.titan_drug_id == m.Product.titan_drug_id)
        .where(m.Product.is_deleted == False)  # noqa: E712
    ).all()

    de = drugeye_lookup()
    proposals = []
    field_counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        diffs = {}
        # Drug-Eye (online, has indications) supplements Titan (local, has
        # identity). Titan wins where both know a field — it is the licensed
        # local master; Drug-Eye fills what Titan cannot supply, above all
        # `uses`, which neither Titan nor eStock carries.
        d = de.get(_norm(r.name_en)) or de.get(_norm(r.name_ar)) or {}
        # A weak/absent Titan match must not lend authority to Titan fields;
        # below the score threshold, only Drug-Eye's contribution is offered.
        titan_ok = (r.titan_match_score or 0) >= min_score
        if not titan_ok and not d:
            continue
        t_sci = r.t_sci if titan_ok else None
        t_cat = r.t_cat if titan_ok else None
        pairs = (
            ("scientific_name", r.scientific_name, t_sci or d.get("scientific_name"),
             "titan" if t_sci else "drugeye"),
            ("name_en", r.name_en, r.t_name_en if titan_ok else None, "titan"),
            ("name_ar", r.name_ar, r.t_name_ar if titan_ok else None, "titan"),
            ("category", r.dosage_form, t_cat or d.get("category"),
             "titan" if t_cat else "drugeye"),
            ("origin", None, r.t_origin if titan_ok else None, "titan"),
            ("is_medicine", None, r.t_med if titan_ok else None, "titan"),
            ("uses", r.uses, d.get("uses"), "drugeye"),
        )
        for field, current, proposed, source in pairs:
            if proposed in (None, ""):
                continue
            cur_blank = current in (None, "") or not str(current).strip()
            if only_missing and not cur_blank:
                continue
            if not cur_blank and str(current).strip().upper() == str(proposed).strip().upper():
                continue
            diffs[field] = {"current": current, "proposed": proposed, "source": source,
                            "action": "fill" if cur_blank else "replace"}
            field_counts[field] += 1
            source_counts[source] += 1
        if diffs:
            proposals.append({
                "product_id": r.product_id,
                "code": r.code,
                "name_ar": r.name_ar,
                "name_en": r.name_en,
                "match_method": r.titan_match_method,
                "match_score": r.titan_match_score,
                "diffs": diffs,
            })

    total = len(proposals)
    # Drug-Eye-only products have no Titan score; sort them after the
    # Titan-matched ones rather than crashing on the None.
    proposals.sort(key=lambda p: (-(p["match_score"] or 0), p["product_id"]))
    return {
        "proposal_count": total,
        "shown": min(total, limit),
        "by_field": dict(field_counts),
        "by_source": dict(source_counts),
        "only_missing": only_missing,
        "proposals": proposals[:limit],
    }
