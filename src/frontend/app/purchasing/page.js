"use client";

import { useEffect, useState } from "react";
import { useUI } from "../providers";
import Shell from "../components/Shell";
import { t } from "../i18n";
import { api } from "../api";

export default function PurchasingPage() {
  const { lang, branch, branches } = useUI();
  const L = (k) => t(lang, k);
  const [purchases, setPurchases] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("purchases");
  // Receive-goods form (eStock's New Purchase Invoice).
  const [vendors, setVendors] = useState([]);
  const [vendorId, setVendorId] = useState("");
  const [billNumber, setBillNumber] = useState("");
  const [prodSearch, setProdSearch] = useState("");
  const [prodResults, setProdResults] = useState([]);
  const [lines, setLines] = useState([]);
  const [saveMsg, setSaveMsg] = useState(null);
  const recvBranch = branch || branches[0]?.branch_id;

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [purchasesRes, draftsRes, summaryRes] = await Promise.all([
          api.get("/purchasing/purchases", { branch_id: branch || undefined }),
          api.get("/purchasing/drafts", { branch_id: branch || undefined }),
          api.get("/purchasing/summary", { branch_id: branch || undefined }),
        ]);
        setPurchases(purchasesRes.purchases || []);
        setDrafts(draftsRes.drafts || []);
        setSummary(summaryRes);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [branch]);

  useEffect(() => {
    api.vendors().then((r) => setVendors(r.vendors)).catch(() => {});
  }, []);

  // Debounced product search for the receive form.
  useEffect(() => {
    if (activeTab !== "receive" || !prodSearch) {
      setProdResults([]);
      return;
    }
    const id = setTimeout(() => {
      api.products(recvBranch, prodSearch).then((r) => setProdResults(r.products.slice(0, 8))).catch(() => {});
    }, 250);
    return () => clearTimeout(id);
  }, [prodSearch, activeTab, recvBranch]);

  function addLine(p) {
    setProdSearch("");
    setProdResults([]);
    setLines((ls) => [
      ...ls,
      {
        product_id: p.product_id,
        name: lang === "ar" ? p.name_ar : p.name_en || p.name_ar,
        amount: 1,
        bonus: 0,
        buy_price: p.sell_price ? Math.round(p.sell_price * 0.8 * 100) / 100 : 0,
        sell_price: p.sell_price || 0,
        exp_date: "",
      },
    ]);
  }

  function setLine(i, key, value) {
    setLines((ls) => ls.map((l, idx) => (idx === i ? { ...l, [key]: value } : l)));
  }

  async function savePurchase() {
    setSaveMsg(null);
    try {
      const r = await api.createPurchase({
        branch_id: recvBranch,
        vendor_id: Number(vendorId),
        bill_number: billNumber || null,
        lines: lines.map((l) => ({
          product_id: l.product_id,
          amount: Number(l.amount),
          bonus: Number(l.bonus) || 0,
          buy_price: Number(l.buy_price),
          sell_price: Number(l.sell_price) || null,
          exp_date: l.exp_date || null,
        })),
      });
      setSaveMsg({ ok: true, msg: `${L("purchase_done")} ${r.purchase_id} · ${r.total_gross.toLocaleString("en-US")} ${L("egp")}` });
      setLines([]);
      setVendorId("");
      setBillNumber("");
    } catch (e) {
      setSaveMsg({ ok: false, msg: e.message });
    }
  }

  if (loading) return <Shell titleKey="nav_purchasing"><div className="page">{L("loading")}</div></Shell>;

  return (
    <Shell titleKey="nav_purchasing">
      <div className="page">
        {/* KPIs */}
        <div className="kpi-row">
          <div className="kpi-box">
            <div className="kpi-value">{summary?.total_spent.toLocaleString("en-US") || "0"}</div>
            <div className="kpi-label">{L("total_spent")} ({L("egp")})</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{summary?.pending_drafts || "0"}</div>
            <div className="kpi-label">{L("pending_drafts")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{summary?.total_purchases || "0"}</div>
            <div className="kpi-label">{L("purchases")}</div>
          </div>
        </div>

        {/* Tabs */}
        <div className="tabs">
          <button
            className={`tab ${activeTab === "purchases" ? "active" : ""}`}
            onClick={() => setActiveTab("purchases")}
          >
            {L("purchases")}
          </button>
          <button
            className={`tab ${activeTab === "drafts" ? "active" : ""}`}
            onClick={() => setActiveTab("drafts")}
          >
            {L("drafts")}
          </button>
          <button
            className={`tab ${activeTab === "receive" ? "active" : ""}`}
            onClick={() => setActiveTab("receive")}
          >
            {L("receive_goods")}
          </button>
        </div>

        {/* Receive goods (new purchase invoice) */}
        {activeTab === "receive" && (
          <div className="card" style={{ maxWidth: 860 }}>
            <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
              <select className="select" value={vendorId} onChange={(e) => setVendorId(e.target.value)} style={{ flex: 1, minWidth: 180 }}>
                <option value="">{L("select_vendor")}</option>
                {vendors.map((v) => (
                  <option key={v.vendor_id} value={v.vendor_id}>
                    {lang === "ar" ? v.name_ar : v.name_en || v.name_ar}
                  </option>
                ))}
              </select>
              <input className="input" placeholder={L("bill_number")} value={billNumber}
                     onChange={(e) => setBillNumber(e.target.value)} style={{ width: 160 }} />
            </div>

            <div style={{ position: "relative", marginBottom: 12 }}>
              <input className="input" placeholder={`${L("add_line")} — ${L("search")}…`} value={prodSearch}
                     onChange={(e) => setProdSearch(e.target.value)} style={{ width: "100%" }} />
              {prodResults.length > 0 && (
                <div className="card" style={{ position: "absolute", insetInlineStart: 0, insetInlineEnd: 0, zIndex: 5, padding: 4, maxHeight: 240, overflowY: "auto" }}>
                  {prodResults.map((p) => (
                    <div key={p.product_id} className="navlink" onClick={() => addLine(p)}>
                      {lang === "ar" ? p.name_ar : p.name_en || p.name_ar}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {lines.length > 0 && (
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{L("product")}</th>
                    <th className="num">{L("qty")}</th>
                    <th className="num">{L("bonus")}</th>
                    <th className="num">{L("buy_price_label")}</th>
                    <th className="num">{L("price")}</th>
                    <th>{L("exp_date")}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((l, i) => (
                    <tr key={i}>
                      <td>{l.name}</td>
                      <td className="num"><input className="input" type="number" min={1} value={l.amount} onChange={(e) => setLine(i, "amount", e.target.value)} style={{ width: 64 }} /></td>
                      <td className="num"><input className="input" type="number" min={0} value={l.bonus} onChange={(e) => setLine(i, "bonus", e.target.value)} style={{ width: 56 }} /></td>
                      <td className="num"><input className="input" type="number" min={0} step="0.01" value={l.buy_price} onChange={(e) => setLine(i, "buy_price", e.target.value)} style={{ width: 84 }} /></td>
                      <td className="num"><input className="input" type="number" min={0} step="0.01" value={l.sell_price} onChange={(e) => setLine(i, "sell_price", e.target.value)} style={{ width: 84 }} /></td>
                      <td><input className="input" type="date" value={l.exp_date} onChange={(e) => setLine(i, "exp_date", e.target.value)} /></td>
                      <td><button className="btn icon" onClick={() => setLines((ls) => ls.filter((_, idx) => idx !== i))}>✕</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
              <span style={{ fontWeight: 700 }}>
                {L("total")}:{" "}
                <span className="num">
                  {lines.reduce((s, l) => s + Number(l.amount || 0) * Number(l.buy_price || 0), 0).toLocaleString("en-US")} {L("egp")}
                </span>
              </span>
              <button className="btn primary" disabled={!vendorId || lines.length === 0} onClick={savePurchase}>
                {L("save_purchase")}
              </button>
            </div>
            {saveMsg && (
              <p className={`badge ${saveMsg.ok ? "ok" : "danger"}`} style={{ marginTop: 12, display: "inline-block", padding: 8 }}>
                {saveMsg.msg}
              </p>
            )}
          </div>
        )}

        {/* Purchases Table */}
        {activeTab === "purchases" && (
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("bill_number")}</th>
                  <th>{L("vendor")}</th>
                  <th>{L("bill_date")}</th>
                  <th>{L("total_gross")}</th>
                  <th>{L("total_discount")}</th>
                  <th>{L("total_tax")}</th>
                  <th>{L("is_return")}</th>
                </tr>
              </thead>
              <tbody>
                {purchases.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="empty">{L("none")}</td>
                  </tr>
                ) : (
                  purchases.map((p) => (
                    <tr key={p.purchase_id}>
                      <td>{p.bill_number || "-"}</td>
                      <td>{p.vendor_name}</td>
                      <td>{p.bill_date ? new Date(p.bill_date).toLocaleDateString("en-US") : "-"}</td>
                      <td>{parseFloat(p.total_gross).toLocaleString("en-US")}</td>
                      <td>{parseFloat(p.total_discount).toLocaleString("en-US")}</td>
                      <td>{parseFloat(p.total_tax).toLocaleString("en-US")}</td>
                      <td>{p.is_return ? "✓" : "-"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Drafts Table */}
        {activeTab === "drafts" && (
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("product")}</th>
                  <th>{L("vendor")}</th>
                  <th>{L("on_hand_qty")}</th>
                  <th>{L("suggested_qty")}</th>
                  <th>{L("reorder")}</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {drafts.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="empty">{L("none")}</td>
                  </tr>
                ) : (
                  drafts.map((d) => (
                    <tr key={d.draft_id}>
                      <td>{d.product_name}</td>
                      <td>{d.vendor_name || "-"}</td>
                      <td>{parseFloat(d.on_hand).toLocaleString("en-US")}</td>
                      <td>{parseFloat(d.suggested_qty).toLocaleString("en-US")}</td>
                      <td>{d.reason}</td>
                      <td>{d.status}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Shell>
  );
}
