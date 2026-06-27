"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

export default function ClinicalPage() {
  const { lang, branch, branches } = useUI();
  const L = (k) => t(lang, k);
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [card, setCard] = useState(null);
  const [age, setAge] = useState(30);
  const [dose, setDose] = useState(null);

  // Drug-info uses a concrete branch for the in-stock alternatives view.
  const infoBranch = branch || branches[0]?.branch_id;

  useEffect(() => {
    let alive = true;
    const id = setTimeout(async () => {
      try {
        const r = await api.products(infoBranch, search);
        if (alive) setProducts(r.products);
      } catch {
        /* ignore */
      }
    }, 200);
    return () => {
      alive = false;
      clearTimeout(id);
    };
  }, [infoBranch, search]);

  useEffect(() => {
    if (!selected) return;
    api.drugInfo(selected.product_id, infoBranch, lang).then((r) => setCard(r.drug)).catch(() => setCard(null));
  }, [selected, infoBranch, lang]);

  useEffect(() => {
    if (!selected) return;
    api.dose(selected.product_id, age, lang).then((r) => setDose(r.dose)).catch(() => setDose(null));
  }, [selected, age, lang]);

  const fmt = (n) => Number(n || 0).toLocaleString(lang === "ar" ? "ar-EG" : "en-US");

  return (
    <Shell titleKey="nav_clinical">
      <p className="muted" style={{ marginBottom: 12 }}>
        {L("clinical_intro")} <span className="badge warn">{L("advisory_note")}</span>
      </p>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1.4fr" }}>
        {/* Drug picker */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: 12, borderBottom: "1px solid var(--border)" }}>
            <input
              className="input"
              placeholder={L("search") + "…"}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>
          <div style={{ maxHeight: 480, overflowY: "auto" }}>
            <table className="tbl">
              <tbody>
                {products.map((p) => (
                  <tr
                    key={p.product_id}
                    style={{ cursor: "pointer", background: selected?.product_id === p.product_id ? "var(--bg)" : undefined }}
                    onClick={() => setSelected(p)}
                  >
                    <td>
                      {lang === "ar" ? p.name_ar : p.name_en || p.name_ar}
                      <div className="muted" style={{ fontSize: 12 }}>{p.scientific_name}</div>
                    </td>
                    <td className="num muted">{fmt(p.sell_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Drug card */}
        <div className="card">
          {!card && <p className="muted">{L("pick_drug")}</p>}
          {card && (
            <>
              <h3 className="section-title" style={{ marginTop: 0 }}>{card.name}</h3>
              <div style={{ marginBottom: 10 }}>
                <span className="muted">{L("active_ingredients")}: </span>
                {card.active_ingredients.length ? card.active_ingredients.join("، ") : L("none")}
                {card.classes.map((c) => (
                  <span key={c} className="badge" style={{ marginInlineStart: 6 }}>{c}</span>
                ))}
              </div>

              {/* Dosing */}
              <div style={{ borderTop: "1px solid var(--border)", paddingTop: 10, marginTop: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <strong>{L("dosing")}</strong>
                  <span className="muted">· {L("patient_age")}:</span>
                  <input
                    className="input"
                    type="number"
                    min={0}
                    max={120}
                    value={age}
                    onChange={(e) => setAge(Number(e.target.value))}
                    style={{ width: 70 }}
                  />
                </div>
                {dose ? (
                  <div style={{ fontSize: 14 }}>
                    <div><span className="muted">{L("dose_label")}:</span> {dose.dose} {dose.weight_based && <span className="badge warn">{L("weight_based")}</span>}</div>
                    <div><span className="muted">{L("frequency")}:</span> {dose.frequency}</div>
                    <div><span className="muted">{L("max_daily")}:</span> {dose.max_daily}</div>
                  </div>
                ) : (
                  <p className="muted">{L("no_dose")}</p>
                )}
              </div>

              {/* In-stock substitutions */}
              <div style={{ borderTop: "1px solid var(--border)", paddingTop: 10, marginTop: 10 }}>
                <strong>{L("substitutes")}</strong>
                {card.substitutions.length === 0 ? (
                  <p className="muted">{L("no_substitutes")}</p>
                ) : (
                  <table className="tbl" style={{ marginTop: 6 }}>
                    <thead>
                      <tr>
                        <th>{L("product")}</th>
                        <th className="num">{L("price")}</th>
                        <th className="num">{L("on_hand")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {card.substitutions.map((s) => (
                        <tr key={s.product_id}>
                          <td>{s.name}<div className="muted" style={{ fontSize: 12 }}>{s.scientific_name}</div></td>
                          <td className="num">{fmt(s.sell_price)}</td>
                          <td className="num">{fmt(s.available_qty)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </Shell>
  );
}
