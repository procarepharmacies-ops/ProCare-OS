"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";
import { downloadCSV, downloadExcel, printReport } from "../lib/print";

// eStock "تقرير حركة مبيعات صنف في فترة" — pick an item, see its per-day
// opening → in/out/returns/adjust → closing ledger over a window, with the
// live on-hand reconcile check and CSV/Excel/print export.
export default function ItemMovementPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const fmt = (n) => Number(n || 0).toLocaleString("en-US");

  const [search, setSearch] = useState("");
  const [results, setResults] = useState([]);
  const [picked, setPicked] = useState(null); // {product_id, name_ar, name_en, code}
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  // Debounced product search (same shape the POS uses).
  useEffect(() => {
    if (picked || search.trim().length === 0) {
      setResults([]);
      return;
    }
    let alive = true;
    const id = setTimeout(async () => {
      try {
        const r = await api.products(branch, search);
        if (alive) setResults((r.products || []).slice(0, 12));
      } catch {
        /* ignore */
      }
    }, 200);
    return () => {
      alive = false;
      clearTimeout(id);
    };
  }, [search, branch, picked]);

  // Load the movement report whenever the picked item / window / branch changes.
  useEffect(() => {
    if (!picked) {
      setData(null);
      return;
    }
    let alive = true;
    setLoading(true);
    (async () => {
      try {
        const r = await api.itemMovement(picked.product_id, branch, days);
        if (alive) setData(r);
      } catch {
        if (alive) setData({ error: true });
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [picked, days, branch]);

  const nameOf = (p) => (lang === "ar" ? p.name_ar : p.name_en || p.name_ar);

  const exportColumns = [
    { key: "date", label: L("bill_date") },
    { key: "purchased", label: L("im_purchased") },
    { key: "sold", label: L("im_sold") },
    { key: "sale_returned", label: L("im_sale_returned") },
    { key: "purchase_returned", label: L("im_purchase_returned") },
    { key: "adjusted", label: L("im_adjusted") },
    { key: "closing", label: L("im_closing") },
  ];
  const exportTitle = data?.product
    ? `${L("im_title")} — ${nameOf(data.product)}`
    : L("im_title");

  return (
    <Shell titleKey="nav_item_movement">
      <div className="page">
        <h2 className="section-title">{L("im_title")}</h2>

        {/* Item picker */}
        <div className="card" style={{ marginBottom: 16, position: "relative" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <input
              className="input"
              style={{ flex: "1 1 260px" }}
              placeholder={L("im_search_ph")}
              value={picked ? `${nameOf(picked)}${picked.code ? ` (${picked.code})` : ""}` : search}
              onChange={(e) => {
                setPicked(null);
                setSearch(e.target.value);
              }}
            />
            {picked && (
              <button className="btn" onClick={() => { setPicked(null); setSearch(""); }}>
                ✕
              </button>
            )}
            <select
              className="select"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            >
              {[7, 30, 90, 180, 365].map((d) => (
                <option key={d} value={d}>{d} {L("days_unit")}</option>
              ))}
            </select>
          </div>

          {results.length > 0 && (
            <div
              className="card"
              style={{
                position: "absolute", zIndex: 20, insetInlineStart: 12, insetInlineEnd: 12,
                marginTop: 4, maxHeight: 320, overflowY: "auto", padding: 4,
              }}
            >
              {results.map((p) => (
                <div
                  key={p.product_id}
                  onClick={() => { setPicked(p); setResults([]); }}
                  style={{ padding: "8px 10px", cursor: "pointer", borderRadius: 6, display: "flex", justifyContent: "space-between" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--hover, rgba(0,0,0,0.05))")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <span>{nameOf(p)}</span>
                  <span className="muted" style={{ fontSize: 12 }}>{p.code || ""}</span>
                </div>
              ))}
            </div>
          )}
          {!picked && <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>{L("im_pick_hint")}</p>}
        </div>

        {loading && <p className="muted">{L("loading")}</p>}
        {data?.error && <p className="badge danger">{L("offline")}</p>}

        {data && !data.error && data.product && (
          <>
            {/* Summary row */}
            <div className="kpi-row">
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.opening)}</div>
                <div className="kpi-label">{L("im_opening")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value" style={{ color: "var(--ok)" }}>{fmt(data.totals.purchased)}</div>
                <div className="kpi-label">{L("im_purchased")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value" style={{ color: "var(--danger)" }}>{fmt(data.totals.sold)}</div>
                <div className="kpi-label">{L("im_sold")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.totals.sale_returned)}</div>
                <div className="kpi-label">{L("im_sale_returned")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.totals.adjusted)}</div>
                <div className="kpi-label">{L("im_adjusted")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.totals.closing)}</div>
                <div className="kpi-label">{L("im_closing")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.on_hand_now)}</div>
                <div className="kpi-label">
                  {L("im_on_hand_now")}{" "}
                  <span className={`badge ${data.reconciles ? "ok" : "warn"}`} style={{ fontSize: 10 }}>
                    {data.reconciles ? L("im_reconciles") : L("im_not_reconciles")}
                  </span>
                </div>
              </div>
            </div>

            {/* Export toolbar */}
            <div style={{ display: "flex", alignItems: "center", margin: "12px 0" }}>
              <h3 className="section-title" style={{ margin: 0 }}>{nameOf(data.product)}{data.product.code ? ` — ${data.product.code}` : ""}</h3>
              {data.rows.length > 0 && (
                <span style={{ display: "inline-flex", gap: 6, marginInlineStart: "auto" }}>
                  <button className="btn" onClick={() => downloadCSV(exportTitle, exportColumns, data.rows)}>{L("export_csv")}</button>
                  <button className="btn" onClick={() => downloadExcel(exportTitle, exportColumns, data.rows)}>{L("export_excel")}</button>
                  <button className="btn" onClick={() => printReport(exportTitle, exportColumns, data.rows, { lang })}>{L("print_branded")}</button>
                </span>
              )}
            </div>

            {/* Daily ledger */}
            <div className="table-wrapper" style={{ maxHeight: 460, overflowY: "auto" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{L("bill_date")}</th>
                    <th className="num">{L("im_purchased")}</th>
                    <th className="num">{L("im_sold")}</th>
                    <th className="num">{L("im_sale_returned")}</th>
                    <th className="num">{L("im_purchase_returned")}</th>
                    <th className="num">{L("im_adjusted")}</th>
                    <th className="num">{L("im_closing")}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ fontWeight: 600, background: "var(--hover, rgba(0,0,0,0.03))" }}>
                    <td>{L("im_opening")}</td>
                    <td className="num" colSpan="5"></td>
                    <td className="num">{fmt(data.opening)}</td>
                  </tr>
                  {data.rows.length === 0 ? (
                    <tr><td colSpan="7" className="empty">{L("im_no_movement")}</td></tr>
                  ) : (
                    data.rows.map((r) => (
                      <tr key={r.date}>
                        <td>{r.date}</td>
                        <td className="num" style={{ color: r.purchased ? "var(--ok)" : undefined }}>{r.purchased ? fmt(r.purchased) : "—"}</td>
                        <td className="num" style={{ color: r.sold ? "var(--danger)" : undefined }}>{r.sold ? fmt(r.sold) : "—"}</td>
                        <td className="num">{r.sale_returned ? fmt(r.sale_returned) : "—"}</td>
                        <td className="num">{r.purchase_returned ? fmt(r.purchase_returned) : "—"}</td>
                        <td className="num">{r.adjusted ? fmt(r.adjusted) : "—"}</td>
                        <td className="num" style={{ fontWeight: 600 }}>{fmt(r.closing)}</td>
                      </tr>
                    ))
                  )}
                  {data.rows.length > 0 && (
                    <tr style={{ fontWeight: 700, borderTop: "2px solid var(--border, #ccc)" }}>
                      <td>{L("im_closing")}</td>
                      <td className="num">{fmt(data.totals.purchased)}</td>
                      <td className="num">{fmt(data.totals.sold)}</td>
                      <td className="num">{fmt(data.totals.sale_returned)}</td>
                      <td className="num">{fmt(data.totals.purchase_returned)}</td>
                      <td className="num">{fmt(data.totals.adjusted)}</td>
                      <td className="num">{fmt(data.totals.closing)}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}
