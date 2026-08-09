"use client";

// Drug alternatives at the counter: search a product, see same-ingredient
// substitutes that are actually in stock, and where.
//
// The API returns availability consolidated across branches with a branches[]
// breakdown, which is exactly what a counter person wants — "we don't have it,
// but Mas-hala does" is the answer that saves the sale.
//
// Advisory only. Nothing here blocks or gates a sale.

import { useState } from "react";
import { useUI } from "../../providers";
import { t } from "../../i18n";
import { api } from "../../api";

export default function RXSubstitutesPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);

  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [picked, setPicked] = useState(null);
  const [alts, setAlts] = useState(null);
  const [busy, setBusy] = useState(false);

  const name = (p) => (lang === "ar" ? p.name_ar : p.name_en || p.name_ar);

  async function search() {
    if (!q.trim()) return;
    setBusy(true);
    setPicked(null);
    setAlts(null);
    try {
      const r = await api.products(branch, q.trim());
      setResults((r.products || []).slice(0, 12));
    } catch {
      setResults([]);
    }
    setBusy(false);
  }

  async function pick(product) {
    setPicked(product);
    setBusy(true);
    setAlts(null);
    try {
      const r = await api.substitutions(product.product_id, branch, lang);
      setAlts(r.substitutions || []);
    } catch {
      setAlts([]);
    }
    setBusy(false);
  }

  return (
    <div>
      <div className="rx-card">
        <div className="rx-row">
          <input
            enterKeyHint="search"
            placeholder={L("search")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
          />
          <button className="rx-btn" style={{ width: 72 }} disabled={busy} onClick={search}>
            🔍
          </button>
        </div>
      </div>

      {!picked &&
        results.map((p) => (
          <button
            key={p.product_id}
            className="rx-btn"
            style={{ marginBottom: 6, textAlign: "start" }}
            onClick={() => pick(p)}
          >
            {name(p)}
          </button>
        ))}

      {picked && (
        <div className="rx-card accent">
          <b style={{ fontSize: 17 }}>{name(picked)}</b>
          <div className="rx-muted">{picked.scientific_name || ""}</div>
          <div style={{ height: 8 }} />
          <button className="rx-btn" onClick={() => { setPicked(null); setAlts(null); }}>
            {L("rx_back_to_search")}
          </button>
        </div>
      )}

      {picked && alts !== null && (
        <div className="rx-card">
          <b>{L("alternatives")}</b>
          {busy && <div className="rx-muted">{L("loading")}</div>}
          {!busy && alts.length === 0 && <div className="rx-muted">{L("none")}</div>}
          {alts.map((a) => (
            <div className="rx-list-item" key={a.product_id} style={{ display: "block" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                <b>{a.name}</b>
                <span className="rx-chip ok">{a.available_qty}</span>
              </div>
              <div className="rx-muted">
                {a.scientific_name} · {a.sell_price}
              </div>
              {(a.branches || []).map((b) => (
                <div className="rx-muted" key={b.branch_id}>
                  {b.branch_name}: {b.qty}
                  {b.nearest_expiry ? ` · ${L("stk_scan_exp")} ${b.nearest_expiry}` : ""}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
