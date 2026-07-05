"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";
import { printReport } from "../lib/print";

// The cash-flow & inventory audit, computed live from the system database for
// every branch at once. This is the in-system replacement for hand-run SQL:
// the same figures the owner needs to see why a vendor can't be paid, sourced
// straight from the tables ProCare owns (which mirror both eStock stores once
// the sync is configured).
export default function AuditPage() {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  const fmt = (n) => Number(n || 0).toLocaleString("en-US");
  const [months, setMonths] = useState(3);
  const [vendor, setVendor] = useState("");
  const [data, setData] = useState(null);
  const [err, setErr] = useState(false);

  async function load() {
    setData(null);
    setErr(false);
    try {
      setData(await api.auditReport(months, vendor));
    } catch {
      setErr(true);
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [months]);

  const bname = (b) => (lang === "ar" ? b.name_ar : b.name_en || b.name_ar);
  const live = data?.data_source?.mode === "live";

  // Every measure is one row; branches are columns — the classic audit layout.
  const ROWS = data
    ? [
        ["audit_revenue", (b) => fmt(b.revenue), false],
        ["audit_gross_profit", (b) => fmt(b.gross_profit), false],
        ["audit_purchases", (b) => fmt(b.purchases_all_vendors), false],
        ["purch_sales_ratio", (b) => (b.purchases_to_sales_pct != null ? `${b.purchases_to_sales_pct}%` : "—"), "ratio"],
        ["vendor_invoiced", (b) => fmt(b.vendor_invoiced), false],
        ["vendor_paid", (b) => fmt(b.vendor_paid), false],
        ["vendor_gap", (b) => fmt(b.vendor_gap), "gap"],
        ["audit_expenses", (b) => fmt(b.expenses_window), false],
        ["audit_treasury", (b) => fmt(b.treasury_balance), false],
        ["cash_desk_var", (b) => `${fmt(b.cash_desk.variance_total)} (${b.cash_desk.closed_shifts})`, false],
        ["stock_at_cost", (b) => fmt(b.stock_cost), false],
        ["stock_at_retail", (b) => fmt(b.stock_retail), false],
        ["expired_lost", (b) => `${fmt(b.expired.cash_lost)} (${b.expired.batches})`, "bad"],
        ["expiring_90", (b) => fmt(b.expiring_90d_cost), "warn"],
        ["dead_stock", (b) => `${fmt(b.dead_stock.cash_locked)} (${b.dead_stock.products})`, "warn"],
      ]
    : [];

  function doPrint() {
    if (!data) return;
    // Flatten to a branded printable table: one row per measure.
    const cols = [{ key: "measure", label: L("audit_measure") }, ...data.branches.map((b) => ({ key: `b${b.branch_id}`, label: bname(b) }))];
    const rows = ROWS.map(([key, val]) => {
      const row = { measure: L(key) };
      data.branches.forEach((b) => (row[`b${b.branch_id}`] = val(b)));
      return row;
    });
    rows.push({ measure: L("receivables_total"), [`b${data.branches[0]?.branch_id}`]: fmt(data.receivables.total) });
    rows.push({ measure: L("receivables_over"), [`b${data.branches[0]?.branch_id}`]: `${fmt(data.receivables.over_limit)} (${data.receivables.debtors_over_limit})` });
    printReport(L("audit_title"), cols, rows, {
      lang,
      subtitle: `${data.window_months} ${L("months_window")} · ${live ? L("audit_source_live") : L("audit_source_demo")}`,
    });
  }

  return (
    <Shell titleKey="nav_audit">
      {/* Controls */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 14 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>{L("audit_title")}</h2>
          <p className="muted" style={{ margin: "2px 0 0", fontSize: 13 }}>{L("audit_subtitle")}</p>
        </div>
        <span style={{ marginInlineStart: "auto", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <label className="muted" style={{ fontSize: 13 }}>{L("months_window")}</label>
          <select className="select" value={months} onChange={(e) => setMonths(Number(e.target.value))}>
            {[1, 3, 6, 12].map((mo) => <option key={mo} value={mo}>{mo}</option>)}
          </select>
          <input className="input" placeholder={L("vendor_focus")} value={vendor}
                 onChange={(e) => setVendor(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} style={{ width: 170 }} />
          <button className="btn" onClick={load}>{L("refresh")}</button>
          <button className="btn primary" disabled={!data} onClick={doPrint}>{L("print_audit")}</button>
        </span>
      </div>

      {/* Data-source honesty banner */}
      {data && (
        <div className={`badge ${live ? "ok" : "warn"}`} style={{ display: "block", padding: "10px 14px", marginBottom: 16, lineHeight: 1.5 }}>
          <b>{live ? L("audit_source_live") : L("audit_source_demo")}</b>
          {!live && data.data_source.hint && <div style={{ fontSize: 12.5, marginTop: 4 }}>{L("audit_connect_hint")}</div>}
        </div>
      )}

      {!data && !err && <p className="muted">{L("loading")}</p>}
      {err && <p className="badge danger">{L("offline")}</p>}

      {data && (
        <>
          {/* Vendor focus headline */}
          {data.vendor_focus && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                <span>
                  <span className="muted" style={{ fontSize: 12 }}>{L("vendor_focus")}</span>
                  <div style={{ fontWeight: 700, fontSize: 17 }}>{lang === "ar" ? data.vendor_focus.name_ar : data.vendor_focus.name_en || data.vendor_focus.name_ar}</div>
                </span>
                <span style={{ textAlign: "end" }}>
                  <span className="muted" style={{ fontSize: 12 }}>{L("vendor_balance_now")}</span>
                  <div className="num" style={{ fontWeight: 800, fontSize: 22, color: "var(--danger)" }}>{fmt(data.vendor_focus.balance_now)} {L("egp")}</div>
                </span>
              </div>
            </div>
          )}

          {/* The audit table: measures × branches */}
          <div className="card" style={{ padding: 0, overflow: "hidden" }}>
            <div className="table-wrapper">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{L("audit_measure")}</th>
                    {data.branches.map((b) => <th key={b.branch_id} className="num">{bname(b)}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map(([key, val, flag]) => (
                    <tr key={key}>
                      <td>{L(key)}</td>
                      {data.branches.map((b) => {
                        const alarm = flag === "ratio" && b.ratio_alarm;
                        const color = alarm || flag === "bad" ? "var(--danger)" : flag === "warn" ? "var(--warn, #A5691E)" : flag === "gap" ? "var(--danger)" : undefined;
                        return (
                          <td key={b.branch_id} className="num" style={{ color, fontWeight: alarm || flag === "gap" ? 700 : 400 }}>
                            {val(b)}{alarm ? " ⚠️" : ""}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Receivables (company-wide) */}
          <div className="kpi-row" style={{ marginTop: 16 }}>
            <div className="kpi-box">
              <div className="kpi-value num">{fmt(data.receivables.total)}</div>
              <div className="kpi-label">{L("receivables_total")} ({L("egp")})</div>
            </div>
            <div className="kpi-box">
              <div className="kpi-value num" style={{ color: "var(--danger)" }}>{fmt(data.receivables.over_limit)}</div>
              <div className="kpi-label">{L("receivables_over")}</div>
            </div>
            <div className="kpi-box">
              <div className="kpi-value num">{data.receivables.debtors_over_limit}</div>
              <div className="kpi-label">{L("debtors_over")}</div>
            </div>
          </div>

          <p className="muted" style={{ fontSize: 12, marginTop: 14 }}>
            {L("purch_sales_ratio")}: {L("ratio_alarm")} · {data.window_months} {L("months_window")} · {data.generated_at?.replace("T", " ")}
          </p>
        </>
      )}
    </Shell>
  );
}
