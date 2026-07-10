"""Prescription reader — capture a doctor's prescription with the phone camera,
extract the doctor + drug lines, and build the doctor-prescribing-habits report
for the pharmacy's area.

Two extraction paths (same gated-adapter pattern as the AI assistant):
  * **Gemini vision** when ``GEMINI_API_KEY`` is set (AI Studio free tier is
    enough): the photo goes to ``models/<model>:generateContent`` with a strict
    JSON-only instruction and we parse doctor/clinic/drugs out of the reply.
  * **Manual** otherwise: the screen lets staff type the fields; the record is
    stored the same way so the habits report works either way.

The image itself is NOT stored (privacy + size) — only the extraction.
"""
from __future__ import annotations

import json
import re
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models as m
from app.services.common import TODAY

_EXTRACT_PROMPT = (
    "You read a photo of a medical prescription from Egypt (Arabic and/or English). "
    "Reply with ONLY a JSON object, no markdown fence, in this exact shape: "
    '{"doctor_name": string|null, "doctor_specialty": string|null, "clinic": string|null, '
    '"drugs": [{"name": string, "dose": string|null, "frequency": string|null, "duration": string|null}], '
    '"raw_text": string} . '
    "raw_text is everything legible on the page. Use null when a field is not visible."
)


def is_configured() -> bool:
    """True when the active AI provider is Gemini with a real key (vision needs
    Gemini — the Anthropic path has no key wired for images here)."""
    return settings.ai_provider == "gemini" and bool(settings.ai_api_key())


def status() -> dict:
    return {
        "reader": "gemini" if is_configured() else "manual",
        "configured": is_configured(),
        "hint": None if is_configured() else "set GEMINI_API_KEY to enable automatic photo reading",
    }


def analyze_image(image_b64: str, mime_type: str = "image/jpeg") -> dict | None:
    """Send the photo to Gemini and parse the strict-JSON extraction.

    Returns the parsed dict, or None on any failure (caller falls back to
    manual entry — never blocks the workflow).
    """
    api_key = settings.ai_api_key()
    if not is_configured() or not api_key:
        return None
    try:
        import httpx

        model = settings.ai_model
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": api_key},
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": _EXTRACT_PROMPT},
                            {"inline_data": {"mime_type": mime_type, "data": image_b64}},
                        ],
                    }
                ],
                "generation_config": {"temperature": 0},
            },
            timeout=45,
        )
        resp.raise_for_status()
        text = ""
        for cand in resp.json().get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                text += part.get("text", "")
        # Tolerate a stray markdown fence despite the instruction.
        text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        data.setdefault("drugs", [])
        return data
    except Exception:
        return None


def save(
    session: Session,
    *,
    branch_id: int | None = None,
    customer_id: int | None = None,
    doctor_name: str | None = None,
    doctor_specialty: str | None = None,
    clinic: str | None = None,
    drugs: list[dict] | None = None,
    raw_text: str | None = None,
    source: str = "manual",
    captured_by: int | None = None,
) -> m.Prescription:
    rx = m.Prescription(
        branch_id=branch_id,
        customer_id=customer_id,
        doctor_name=(doctor_name or "").strip() or None,
        doctor_specialty=(doctor_specialty or "").strip() or None,
        clinic=(clinic or "").strip() or None,
        drugs_json=json.dumps(drugs or [], ensure_ascii=False)[:4000],
        raw_text=(raw_text or "")[:4000] or None,
        source=source if source in ("gemini", "manual") else "manual",
        captured_by=captured_by,
    )
    session.add(rx)
    session.commit()
    session.refresh(rx)
    return rx


def _row(rx: m.Prescription) -> dict:
    try:
        drugs = json.loads(rx.drugs_json or "[]")
    except Exception:
        drugs = []
    return {
        "prescription_id": rx.prescription_id,
        "branch_id": rx.branch_id,
        "customer_id": rx.customer_id,
        "doctor_name": rx.doctor_name,
        "doctor_specialty": rx.doctor_specialty,
        "clinic": rx.clinic,
        "drugs": drugs,
        "raw_text": rx.raw_text,
        "source": rx.source,
        "status": getattr(rx, "status", "captured"),
        "created_at": rx.created_at.isoformat() if rx.created_at else None,
    }


# --- capture -> review -> dispense workflow ---------------------------------
def _match_products(session: Session, name: str, branch_id: int | None) -> list[dict]:
    """Best-effort match of a free-text drug name to catalogue products:
    exact/prefix on Arabic or English name, then scientific-name (active
    ingredient) overlap. Returns candidates with on-hand at the branch."""
    from app.services import clinical

    name = (name or "").strip()
    if not name:
        return []
    like = f"%{name}%"
    products = session.scalars(
        select(m.Product)
        .where(
            m.Product.is_active == True,  # noqa: E712
            m.Product.is_deleted == False,  # noqa: E712
            (m.Product.name_ar.ilike(like))
            | (m.Product.name_en.ilike(like))
            | (m.Product.scientific_name.ilike(like)),
        )
        .limit(8)
    ).all()

    # On-hand per product at the branch (available = amount>0, non-expired).
    def on_hand(pid: int) -> float:
        q = select(func.coalesce(func.sum(m.StockBatch.amount), 0)).where(
            m.StockBatch.product_id == pid,
            (m.StockBatch.exp_date == None) | (m.StockBatch.exp_date > TODAY),  # noqa: E711
            m.StockBatch.amount > 0,
        )
        if branch_id:
            q = q.where(m.StockBatch.branch_id == branch_id)
        return float(session.scalar(q) or 0)

    out = []
    for p in products:
        out.append(
            {
                "product_id": p.product_id,
                "name_ar": p.name_ar,
                "name_en": p.name_en,
                "scientific_name": p.scientific_name,
                "sell_price": float(p.sell_price or 0),
                "on_hand": on_hand(p.product_id),
            }
        )
    # In-stock candidates first, then by name length (closer match).
    out.sort(key=lambda c: (c["on_hand"] <= 0, len(c["name_ar"] or "")))
    return out


def resolve_products(session: Session, prescription_id: int, branch_id: int | None = None) -> dict | None:
    """For each extracted drug line, list catalogue product candidates + stock,
    so staff can confirm the match before turning the Rx into a sale."""
    rx = session.get(m.Prescription, prescription_id)
    if rx is None:
        return None
    try:
        drugs = json.loads(rx.drugs_json or "[]")
    except Exception:
        drugs = []
    branch = branch_id or rx.branch_id
    lines = []
    for d in drugs:
        nm = d.get("name") if isinstance(d, dict) else str(d)
        candidates = _match_products(session, nm or "", branch)
        lines.append(
            {
                "name": nm,
                "dose": d.get("dose") if isinstance(d, dict) else None,
                "candidates": candidates,
                "best_product_id": candidates[0]["product_id"] if candidates else None,
            }
        )
    return {"prescription_id": rx.prescription_id, "status": rx.status, "branch_id": branch, "lines": lines}


def review(session: Session, prescription_id: int, drugs: list[dict], reviewed_by: int | None = None) -> dict | None:
    """Save the staff-corrected drug lines (each may carry a resolved
    product_id) and mark the prescription 'reviewed'."""
    rx = session.get(m.Prescription, prescription_id)
    if rx is None:
        return None
    rx.drugs_json = json.dumps(drugs or [], ensure_ascii=False)[:4000]
    rx.status = "reviewed"
    rx.reviewed_by = reviewed_by
    session.commit()
    session.refresh(rx)
    return _row(rx)


def cart_lines(session: Session, prescription_id: int, branch_id: int | None = None) -> dict | None:
    """The reviewed prescription as POS-ready cart lines: only lines with a
    resolved, in-stock product. Out-of-stock/unmatched lines are returned
    separately so the cashier can substitute or order them."""
    rx = session.get(m.Prescription, prescription_id)
    if rx is None:
        return None
    try:
        drugs = json.loads(rx.drugs_json or "[]")
    except Exception:
        drugs = []
    branch = branch_id or rx.branch_id
    ready, unresolved = [], []
    for d in drugs:
        pid = d.get("product_id") if isinstance(d, dict) else None
        if not pid:
            unresolved.append({"name": d.get("name") if isinstance(d, dict) else str(d), "reason": "unmatched"})
            continue
        p = session.get(m.Product, pid)
        if p is None:
            unresolved.append({"name": d.get("name"), "reason": "unmatched"})
            continue
        oh = _match_products(session, p.name_ar, branch)
        on_hand = next((c["on_hand"] for c in oh if c["product_id"] == pid), 0)
        line = {
            "product_id": pid,
            "name_ar": p.name_ar,
            "name_en": p.name_en,
            "sell_price": float(p.sell_price or 0),
            "amount": float(d.get("qty") or 1),
            "on_hand": on_hand,
        }
        (ready if on_hand > 0 else unresolved).append(line if on_hand > 0 else {**line, "reason": "out_of_stock"})
    return {"prescription_id": rx.prescription_id, "branch_id": branch, "lines": ready, "unresolved": unresolved}


def mark_dispensed(session: Session, prescription_id: int) -> dict | None:
    rx = session.get(m.Prescription, prescription_id)
    if rx is None:
        return None
    rx.status = "dispensed"
    session.commit()
    return {"prescription_id": rx.prescription_id, "status": rx.status}


def list_prescriptions(
    session: Session, branch_id: int | None = None, doctor: str | None = None, limit: int = 100
) -> list[dict]:
    q = select(m.Prescription).order_by(m.Prescription.created_at.desc())
    if branch_id:
        q = q.where(m.Prescription.branch_id == branch_id)
    if doctor:
        q = q.where(m.Prescription.doctor_name.ilike(f"%{doctor}%"))
    return [_row(rx) for rx in session.scalars(q.limit(limit)).all()]


def doctor_habits(session: Session, branch_id: int | None = None, days: int = 180) -> list[dict]:
    """Prescribing habits per doctor in the area: how many prescriptions we
    captured, and which drugs each doctor writes most (with counts) — so the
    pharmacy stocks what local doctors actually prescribe."""
    start = TODAY - timedelta(days=days)
    q = select(m.Prescription).where(func.date(m.Prescription.created_at) >= start)
    if branch_id:
        q = q.where(m.Prescription.branch_id == branch_id)

    by_doctor: dict[str, dict] = {}
    for rx in session.scalars(q).all():
        name = (rx.doctor_name or "").strip() or "غير محدد / unknown"
        d = by_doctor.setdefault(
            name,
            {"doctor_name": name, "doctor_specialty": rx.doctor_specialty, "prescriptions": 0, "drug_counts": {}},
        )
        d["prescriptions"] += 1
        if rx.doctor_specialty and not d["doctor_specialty"]:
            d["doctor_specialty"] = rx.doctor_specialty
        try:
            drugs = json.loads(rx.drugs_json or "[]")
        except Exception:
            drugs = []
        for drug in drugs:
            dn = (drug.get("name") or "").strip()
            if dn:
                d["drug_counts"][dn] = d["drug_counts"].get(dn, 0) + 1

    out = []
    for d in by_doctor.values():
        top = sorted(d["drug_counts"].items(), key=lambda kv: kv[1], reverse=True)[:10]
        out.append(
            {
                "doctor_name": d["doctor_name"],
                "doctor_specialty": d["doctor_specialty"],
                "prescriptions": d["prescriptions"],
                "top_drugs": [{"name": n, "count": c} for n, c in top],
            }
        )
    out.sort(key=lambda r: r["prescriptions"], reverse=True)
    return out


def demand_signal(session: Session, branch_id: int | None = None, days: int = 30) -> dict[str, int]:
    """Drug-name → mention count from recent prescriptions. Feeds the
    predictive auto-purchasing (drugs doctors prescribe are drugs to stock)."""
    start = TODAY - timedelta(days=days)
    q = select(m.Prescription.drugs_json).where(func.date(m.Prescription.created_at) >= start)
    if branch_id:
        q = q.where(m.Prescription.branch_id == branch_id)
    counts: dict[str, int] = {}
    for (drugs_json,) in session.execute(q).all():
        try:
            drugs = json.loads(drugs_json or "[]")
        except Exception:
            continue
        for drug in drugs:
            dn = (drug.get("name") or "").strip().lower()
            if dn:
                counts[dn] = counts.get(dn, 0) + 1
    return counts
