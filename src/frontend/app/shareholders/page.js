"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

// Shareholders / owners register (company_Owner mirror): capital + dividends,
// with a per-shareholder annual dividend history drill-down.
export default function ShareholdersPage() {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  const fmt = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });
  const nameOf = (r) => (lang === "ar" ? r.name_ar : r.name_en || r.name_ar);

  const [data, setData] = useState(null);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    api.shareholders().then(setData).catch(() => setData({ shareholders: [], count: 0, total_capital: 0, total_dividends: 0 }));
  }, []);

  const open = async (id) => {
    try {
      setDetail(await api.shareholder(id));
    } catch {
      /* ignore */
    }
  };

  return (
    <Shell titleKey="nav_shareholders">
      <div className="page">
        <h2 className="section-title">{L("sh_title")}</h2>
        <p className="muted" style={{ marginTop: -4, marginBottom: 12, maxWidth: 720 }}>{L("sh_subtitle")}</p>

        {data && data.count === 0 && <p className="muted">{L("sh_none")}</p>}

        {data && data.count > 0 && (
          <div className="card">
            <div className="table-wrapper">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{L("sh_name")}</th>
                    <th className="num">{L("sh_start_capital")}</th>
                    <th className="num">{L("sh_current_capital")}</th>
                    <th className="num">{L("sh_share")}</th>
                    <th className="num">{L("sh_dividends")}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.shareholders.map((r) => (
                    <tr key={r.shareholder_id}>
                      <td>{nameOf(r)}{r.code ? <span className="muted"> · {r.code}</span> : null}</td>
                      <td className="num muted">{fmt(r.start_capital)}</td>
                      <td className="num" style={{ fontWeight: 600 }}>{fmt(r.current_capital)}</td>
                      <td className="num"><span className="badge">{r.share_pct}%</span></td>
                      <td className="num">{fmt(r.total_dividends)}</td>
                      <td><button className="btn" onClick={() => open(r.shareholder_id)}>{L("sh_history")}</button></td>
                    </tr>
                  ))}
                  <tr style={{ fontWeight: 700, borderTop: "1px solid var(--border)" }}>
                    <td>{L("total")}</td>
                    <td></td>
                    <td className="num">{fmt(data.total_capital)}</td>
                    <td></td>
                    <td className="num">{fmt(data.total_dividends)}</td>
                    <td></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {detail && (
          <div className="card" style={{ marginTop: 16 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
              <h3 className="section-title" style={{ margin: 0 }}>{nameOf(detail)}</h3>
              <span className="muted" style={{ fontSize: 12 }}>
                {L("sh_current_capital")}: {fmt(detail.current_capital)} · {L("sh_total_dividends")}: {fmt(detail.total_dividends)}
              </span>
              <button className="btn icon" style={{ marginInlineStart: "auto" }} onClick={() => setDetail(null)}>✕</button>
            </div>
            <div className="table-wrapper">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{L("sh_year")}</th>
                    <th className="num">{L("sh_amount")}</th>
                    <th className="num">{L("sh_payments")}</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.dividend_history.length === 0 ? (
                    <tr><td colSpan="3" className="empty">{L("sh_none")}</td></tr>
                  ) : detail.dividend_history.map((h) => (
                    <tr key={h.year || "na"}>
                      <td>{h.year ?? "—"}</td>
                      <td className="num" style={{ fontWeight: 600 }}>{fmt(h.amount)}</td>
                      <td className="num muted">{h.payments}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}
