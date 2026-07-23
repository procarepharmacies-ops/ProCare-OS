"use client";

import { useCallback, useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

// Change history (سجل التغييرات): price changes, stock movements, and logins —
// the after-the-fact audit trails from the tables ProCare owns.
export default function HistoryPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [tab, setTab] = useState("prices");
  const [prices, setPrices] = useState([]);
  const [stock, setStock] = useState([]);
  const [logins, setLogins] = useState([]);

  const fmt = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });
  const nameOf = (r) => (lang === "ar" ? r.name_ar : r.name_en || r.name_ar);
  const when = (iso) => (iso ? new Date(iso).toLocaleString("en-GB") : "-");

  const load = useCallback(async () => {
    try {
      if (tab === "prices") setPrices((await api.productChanges(branch, 90)).changes || []);
      else if (tab === "stock") setStock((await api.stockChanges(branch, 30)).changes || []);
      else if (tab === "logins") setLogins((await api.authEvents(100)).events || []);
    } catch {
      /* fail-soft */
    }
  }, [tab, branch]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Shell titleKey="nav_history">
      <div className="page">
        <h2 className="section-title">{L("hist_title")}</h2>
        <p className="muted" style={{ marginTop: -4, marginBottom: 12, maxWidth: 720 }}>{L("hist_subtitle")}</p>

        <div className="tabs">
          <button className={`tab ${tab === "prices" ? "active" : ""}`} onClick={() => setTab("prices")}>{L("hist_prices")}</button>
          <button className={`tab ${tab === "stock" ? "active" : ""}`} onClick={() => setTab("stock")}>{L("hist_stock")}</button>
          <button className={`tab ${tab === "logins" ? "active" : ""}`} onClick={() => setTab("logins")}>{L("hist_logins")}</button>
        </div>

        {tab === "prices" && (
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("date")}</th><th>{L("product")}</th><th>{L("hist_field")}</th>
                  <th className="num">{L("hist_old")}</th><th className="num">{L("hist_new")}</th><th>{L("hist_by")}</th>
                </tr>
              </thead>
              <tbody>
                {prices.length === 0 ? <tr><td colSpan="6" className="empty">{L("hist_none")}</td></tr> : prices.map((c) => (
                  <tr key={c.change_id}>
                    <td>{when(c.created_at)}</td>
                    <td>{nameOf(c)}</td>
                    <td>{lang === "ar" ? c.field_ar : c.field_en}</td>
                    <td className="num muted">{fmt(c.old_value)}</td>
                    <td className="num" style={{ fontWeight: 600 }}>{fmt(c.new_value)}</td>
                    <td>{c.employee_name || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === "stock" && (
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("date")}</th><th>{L("product")}</th><th>{L("hist_reason")}</th>
                  <th className="num">{L("hist_change")}</th><th>{L("hist_by")}</th>
                </tr>
              </thead>
              <tbody>
                {stock.length === 0 ? <tr><td colSpan="5" className="empty">{L("hist_none")}</td></tr> : stock.map((c) => (
                  <tr key={c.movement_id}>
                    <td>{when(c.created_at)}</td>
                    <td>{nameOf(c)}</td>
                    <td><span className="badge">{lang === "ar" ? c.reason_ar : c.reason_en}</span></td>
                    <td className="num" style={{ fontWeight: 600, color: c.delta < 0 ? "var(--danger)" : "var(--ok)" }}>
                      {c.delta > 0 ? "+" : ""}{fmt(c.delta)}
                    </td>
                    <td>{c.employee_name || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === "logins" && (
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr><th>{L("date")}</th><th>{L("hist_by")}</th><th>{L("hist_event")}</th><th>IP</th></tr>
              </thead>
              <tbody>
                {logins.length === 0 ? <tr><td colSpan="4" className="empty">{L("hist_none")}</td></tr> : logins.map((e) => (
                  <tr key={e.event_id}>
                    <td>{when(e.created_at)}</td>
                    <td>{e.username}</td>
                    <td>
                      <span className={`badge ${e.event === "login_fail" ? "danger" : e.event === "login_ok" ? "ok" : ""}`}>
                        {e.event}
                      </span>
                    </td>
                    <td className="muted">{e.ip || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Shell>
  );
}
