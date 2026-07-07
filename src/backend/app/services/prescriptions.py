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
from app.services.common import TODAY, as_date

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
        "created_at": rx.created_at.isoformat() if rx.created_at else None,
    }


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
    q = select(m.Prescription).where(as_date(m.Prescription.created_at) >= start)
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
    q = select(m.Prescription.drugs_json).where(as_date(m.Prescription.created_at) >= start)
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
