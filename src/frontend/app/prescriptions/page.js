"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

// Prescription reader: phone camera capture → Gemini extraction (when a key is
// configured) → stored record; manual entry otherwise. Bottom half is the
// doctor-prescribing-habits report for the area.
export default function PrescriptionsPage() {
  const { lang, branch, branches } = useUI();
  const L = (k) => t(lang, k);
  const router = useRouter();
  const fileRef = useRef(null);
  // Review-before-dispense panel state.
  const [reviewRx, setReviewRx] = useState(null); // {prescription_id, lines:[{name, candidates, product_id}]}
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  // Manual/reviewed form state.
  const [doctor, setDoctor] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [clinic, setClinic] = useState("");
  const [drugs, setDrugs] = useState([{ name: "", dose: "", frequency: "" }]);
  const [history, setHistory] = useState([]);
  const [habits, setHabits] = useState([]);
  const rxBranch = branch || branches[0]?.branch_id;

  useEffect(() => {
    api.rxStatus().then(setStatus).catch(() => {});
  }, []);

  async function refresh() {
    try {
      const [h, hb] = await Promise.all([api.rxList(branch), api.rxHabits(branch)]);
      setHistory(h.prescriptions || []);
      setHabits(hb.doctors || []);
    } catch {
      /* offline */
    }
  }
  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branch]);

  async function onPhoto(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setMsg(null);
    setBusy(true);
    try {
      const b64 = await new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(String(r.result).split(",")[1]);
        r.onerror = reject;
        r.readAsDataURL(file);
      });
      const res = await api.rxAnalyze({
        image_b64: b64,
        mime_type: file.type || "image/jpeg",
        branch_id: rxBranch,
        save: true,
      });
      if (res.ok) {
        setMsg({ ok: true, msg: `${L("rx_saved")} — ${res.extraction?.doctor_name || "?"}` });
        refresh();
      } else {
        // No Gemini key / unreadable — pre-open the manual form.
        setMsg({ ok: false, msg: L("rx_reader_off") });
      }
    } catch (err) {
      setMsg({ ok: false, msg: err.message });
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function saveManual() {
    setMsg(null);
    try {
      await api.rxCreate({
        branch_id: rxBranch,
        doctor_name: doctor,
        doctor_specialty: specialty,
        clinic,
        drugs: drugs.filter((d) => d.name.trim()).map((d) => ({ name: d.name, dose: d.dose || null, frequency: d.frequency || null })),
      });
      setMsg({ ok: true, msg: L("rx_saved") });
      setDoctor(""); setSpecialty(""); setClinic("");
      setDrugs([{ name: "", dose: "", frequency: "" }]);
      refresh();
    } catch (e) {
      setMsg({ ok: false, msg: e.message });
    }
  }

  const setDrug = (i, k, v) => setDrugs((ds) => ds.map((d, idx) => (idx === i ? { ...d, [k]: v } : d)));

  // Open the review panel: resolve each drug line to catalogue candidates.
  async function openReview(prescriptionId) {
    setMsg(null);
    try {
      const res = await api.rxResolve(prescriptionId, rxBranch);
      setReviewRx({
        prescription_id: prescriptionId,
        lines: (res.lines || []).map((l) => ({
          name: l.name,
          dose: l.dose,
          candidates: l.candidates || [],
          product_id: l.best_product_id || "",
          qty: 1,
        })),
      });
    } catch (e) {
      setMsg({ ok: false, msg: e.message });
    }
  }

  const setReviewLine = (i, k, v) =>
    setReviewRx((r) => ({ ...r, lines: r.lines.map((l, idx) => (idx === i ? { ...l, [k]: v } : l)) }));

  // Save the reviewed lines, then jump to POS with the prescription seeded.
  async function reviewToPOS() {
    try {
      await api.rxReview(reviewRx.prescription_id, {
        drugs: reviewRx.lines.map((l) => ({
          name: l.name,
          dose: l.dose,
          product_id: l.product_id ? Number(l.product_id) : null,
          qty: Number(l.qty) || 1,
        })),
      });
      const id = reviewRx.prescription_id;
      setReviewRx(null);
      router.push(`/pos?rx=${id}`);
    } catch (e) {
      setMsg({ ok: false, msg: e.message });
    }
  }

  return (
    <Shell titleKey="nav_prescriptions">
      {reviewRx && (
        <div className="card" style={{ marginBottom: 16, border: "2px solid var(--brand)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h3 className="section-title">{L("rx_review_title")} #{reviewRx.prescription_id}</h3>
            <button className="btn icon" onClick={() => setReviewRx(null)}>✕</button>
          </div>
          <p className="muted" style={{ fontSize: 13 }}>{L("rx_review_hint")}</p>
          {reviewRx.lines.map((l, i) => (
            <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", padding: "6px 0", borderBottom: "1px solid var(--border)", flexWrap: "wrap" }}>
              <span style={{ flex: 1, minWidth: 120 }}><strong>{l.name}</strong>{l.dose ? <span className="muted"> · {l.dose}</span> : null}</span>
              <select className="select" value={l.product_id} onChange={(e) => setReviewLine(i, "product_id", e.target.value)} style={{ flex: 2, minWidth: 180 }}>
                <option value="">{L("rx_no_match")}</option>
                {l.candidates.map((c) => (
                  <option key={c.product_id} value={c.product_id}>
                    {(lang === "ar" ? c.name_ar : c.name_en || c.name_ar)} — {L("stock")}: {c.on_hand}
                  </option>
                ))}
              </select>
              <input className="input" type="number" min={1} value={l.qty} onChange={(e) => setReviewLine(i, "qty", e.target.value)} style={{ width: 64 }} />
            </div>
          ))}
          <button className="btn primary" style={{ marginTop: 10 }} onClick={reviewToPOS}>
            {L("rx_to_invoice")} →
          </button>
        </div>
      )}
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16, alignItems: "start" }}>
        {/* Capture + manual entry */}
        <div className="card">
          <h3 className="section-title">{L("rx_capture")}</h3>
          <p className={`badge ${status?.configured ? "ok" : "warn"}`} style={{ display: "inline-block", padding: 8 }}>
            {status?.configured ? L("rx_reader_on") : L("rx_reader_off")}
          </p>
          <div style={{ margin: "12px 0" }}>
            {/* capture="environment" opens the phone's back camera directly. */}
            <input ref={fileRef} type="file" accept="image/*" capture="environment" onChange={onPhoto} style={{ display: "none" }} />
            <button className="btn primary" style={{ width: "100%", padding: 14 }} disabled={busy} onClick={() => fileRef.current?.click()}>
              {busy ? L("rx_analyzing") : L("rx_take_photo")}
            </button>
          </div>

          <h3 className="section-title" style={{ marginTop: 18 }}>{L("rx_doctor")}</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <input className="input" placeholder={L("rx_doctor")} value={doctor} onChange={(e) => setDoctor(e.target.value)} />
            <div style={{ display: "flex", gap: 8 }}>
              <input className="input" placeholder={L("rx_specialty")} value={specialty} onChange={(e) => setSpecialty(e.target.value)} style={{ flex: 1 }} />
              <input className="input" placeholder={L("rx_clinic")} value={clinic} onChange={(e) => setClinic(e.target.value)} style={{ flex: 1 }} />
            </div>
            <div style={{ fontWeight: 700, marginTop: 6 }}>{L("rx_drugs")}</div>
            {drugs.map((d, i) => (
              <div key={i} style={{ display: "flex", gap: 6 }}>
                <input className="input" placeholder={L("product")} value={d.name} onChange={(e) => setDrug(i, "name", e.target.value)} style={{ flex: 2 }} />
                <input className="input" placeholder="Dose" value={d.dose} onChange={(e) => setDrug(i, "dose", e.target.value)} style={{ flex: 1 }} />
                <input className="input" placeholder="×/يوم" value={d.frequency} onChange={(e) => setDrug(i, "frequency", e.target.value)} style={{ flex: 1 }} />
                <button className="btn icon" onClick={() => setDrugs((ds) => ds.filter((_, idx) => idx !== i))}>✕</button>
              </div>
            ))}
            <button className="btn" onClick={() => setDrugs((ds) => [...ds, { name: "", dose: "", frequency: "" }])}>
              ＋ {L("rx_add_drug")}
            </button>
            <button className="btn primary" disabled={!doctor.trim() && !drugs.some((d) => d.name.trim())} onClick={saveManual}>
              {L("rx_save")}
            </button>
            {msg && <p className={`badge ${msg.ok ? "ok" : "danger"}`} style={{ padding: 8 }}>{msg.msg}</p>}
          </div>
        </div>

        {/* Doctor habits */}
        <div className="card">
          <h3 className="section-title">{L("rx_habits")}</h3>
          {habits.length === 0 && <p className="muted">{L("none")}</p>}
          {habits.map((d) => (
            <div key={d.doctor_name} style={{ borderBottom: "1px solid var(--border)", padding: "10px 0" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700 }}>
                <span>
                  {d.doctor_name}
                  {d.doctor_specialty && <span className="muted" style={{ fontWeight: 400 }}> · {d.doctor_specialty}</span>}
                </span>
                <span className="badge ok">{d.prescriptions} {L("rx_count")}</span>
              </div>
              {d.top_drugs.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                  {d.top_drugs.map((td) => (
                    <span key={td.name} className="badge" style={{ padding: "3px 8px" }}>
                      {td.name} ×{td.count}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Recent prescriptions */}
      <div className="card" style={{ marginTop: 16 }}>
        <h3 className="section-title">{L("rx_history")}</h3>
        <div className="table-wrapper">
          <table className="tbl">
            <thead>
              <tr>
                <th>#</th>
                <th>{L("rx_doctor")}</th>
                <th>{L("rx_specialty")}</th>
                <th>{L("rx_drugs")}</th>
                <th>{L("bill_date")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {history.length === 0 ? (
                <tr><td colSpan="6" className="empty">{L("none")}</td></tr>
              ) : (
                history.map((rx) => (
                  <tr key={rx.prescription_id}>
                    <td className="num">{rx.prescription_id}</td>
                    <td>{rx.doctor_name || "—"}</td>
                    <td className="muted">{rx.doctor_specialty || "—"}</td>
                    <td>{(rx.drugs || []).map((d) => d.name).join("، ") || "—"}</td>
                    <td className="muted">{rx.created_at ? new Date(rx.created_at).toLocaleDateString() : "—"}</td>
                    <td style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      {rx.source === "gemini" ? <span className="badge ok">AI</span> : null}
                      {rx.status === "dispensed" ? (
                        <span className="badge ok">{L("rx_dispensed")}</span>
                      ) : (
                        <button className="btn" style={{ padding: "2px 8px" }} onClick={() => openReview(rx.prescription_id)}>
                          {L("rx_review_dispense")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}
