"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

// Shortage sheet (eStock's Shortcoming): any employee logs what a customer
// asked for and we didn't have. Purchasing works the list and flips statuses;
// open items also feed the predictive purchase proposal as a demand signal.
export default function ShortagesPage() {
  const { lang, branch, branches } = useUI();
  const L = (k) => t(lang, k);
  const fmt = (n) => Number(n || 0).toLocaleString("en-US");
  const [rows, setRows] = useState(null);
  const [filter, setFilter] = useState("open");
  const [msg, setMsg] = useState(null);
  // Add form
  const [prodSearch, setProdSearch] = useState("");
  const [prodResults, setProdResults] = useState([]);
  const [productId, setProductId] = useState(null);
  const [freeName, setFreeName] = useState("");
  const [qty, setQty] = useState("1");
  const [note, setNote] = useState("");
  const shBranch = branch || branches[0]?.branch_id;

  async function refresh() {
    try {
      const r = await api.shortages(branch, filter || undefined);
      setRows(r.shortages || []);
    } catch {
      setRows([]);
    }
  }
  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branch, filter]);

  // Catalogue lookup so the item links to a real product when it exists.
  useEffect(() => {
    if (!prodSearch || productId) {
      setProdResults([]);
      return;
    }
    const id = setTimeout(() => {
      api.products(shBranch, prodSearch).then((r) => setProdResults(r.products.slice(0, 6))).catch(() => {});
    }, 250);
    return () => clearTimeout(id);
  }, [prodSearch, productId, shBranch]);

  async function add() {
    setMsg(null);
    try {
      await api.createShortage({
        branch_id: shBranch,
        product_id: productId,
        product_name: productId ? null : (freeName || prodSearch),
        qty_requested: Number(qty) || 1,
        note: note || null,
      });
      setProdSearch(""); setProductId(null); setFreeName(""); setQty("1"); setNote("");
      setMsg({ ok: true, msg: "✓" });
      refresh();
    } catch (e) {
      setMsg({ ok: false, msg: e.message });
    }
  }

  async function setStatus(id, status) {
    try {
      await api.setShortageStatus(id, status);
      refresh();
    } catch {
      /* keep */
    }
  }

  const statusBadge = { open: "warn", ordered: "", received: "ok", cancelled: "danger" };

  return (
    <Shell titleKey="nav_shortages">
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 className="section-title">{L("add_shortage")}</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ position: "relative", flex: 2, minWidth: 220 }}>
            <input
              className="input"
              placeholder={`${L("search")} / ${L("product_free_text")}`}
              value={prodSearch}
              onChange={(e) => { setProdSearch(e.target.value); setProductId(null); }}
              style={{ width: "100%" }}
            />
            {prodResults.length > 0 && (
              <div className="card" style={{ position: "absolute", insetInlineStart: 0, insetInlineEnd: 0, zIndex: 5, padding: 4, maxHeight: 220, overflowY: "auto" }}>
                {prodResults.map((p) => (
                  <div key={p.product_id} className="navlink" onClick={() => { setProductId(p.product_id); setProdSearch(lang === "ar" ? p.name_ar : p.name_en || p.name_ar); setProdResults([]); }}>
                    {lang === "ar" ? p.name_ar : p.name_en || p.name_ar}
                    <span className="muted" style={{ marginInlineStart: 6, fontSize: 12 }}>({fmt(p.on_hand)})</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <input className="input" type="number" min={1} placeholder={L("qty_requested")} value={qty} onChange={(e) => setQty(e.target.value)} style={{ width: 110 }} />
          <input className="input" placeholder={L("note_lbl")} value={note} onChange={(e) => setNote(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
          <button className="btn primary" disabled={!prodSearch.trim()} onClick={add}>＋</button>
          {msg && <span className={`badge ${msg.ok ? "ok" : "danger"}`}>{msg.msg}</span>}
        </div>
        {productId && <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>✓ {L("product")} #{productId}</p>}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        {["open", "ordered", "received", ""].map((s) => (
          <button key={s || "all"} className={`btn ${filter === s ? "primary" : ""}`} onClick={() => setFilter(s)}>
            {s ? L(`status_${s}`) : L("all_tasks")}
          </button>
        ))}
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>{L("product")}</th>
              <th className="num">{L("qty_requested")}</th>
              <th>{L("note_lbl")}</th>
              <th>{L("bill_date")}</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {!rows && <tr><td colSpan="6" className="empty">{L("loading")}</td></tr>}
            {rows && rows.length === 0 && <tr><td colSpan="6" className="empty">{L("none")}</td></tr>}
            {rows?.map((s) => (
              <tr key={s.shortage_id}>
                <td>{s.product_name || `#${s.product_id}`}</td>
                <td className="num">{fmt(s.qty_requested)}</td>
                <td className="muted" style={{ fontSize: 12 }}>{s.note || "—"}</td>
                <td className="muted">{s.created_at ? new Date(s.created_at).toLocaleDateString() : "—"}</td>
                <td><span className={`badge ${statusBadge[s.status] || ""}`}>{L(`status_${s.status}`)}</span></td>
                <td>
                  {s.status === "open" && (
                    <button className="btn" onClick={() => setStatus(s.shortage_id, "ordered")}>{L("mark_ordered")}</button>
                  )}
                  {s.status === "ordered" && (
                    <button className="btn" onClick={() => setStatus(s.shortage_id, "received")}>{L("mark_received")}</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}
