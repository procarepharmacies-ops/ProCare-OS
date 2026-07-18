"use client";

/* Daily Sales report — ProCare's version of eStock's `sales_daily_rpt`.
   Per-day: bills, items, gross, discount, net, cash, non-cash + period totals.
   The reusable REPORT PATTERN for the other 119 reports: date filter, branch
   tag, totals row, CSV (Excel) export, and print-to-PDF with ProCare branding. */

import { useEffect, useState, useCallback } from "react";
import { useUI } from "../providers";
import { apiFetch } from "../api";

const L = {
  ar: { title: "تقرير المبيعات اليومي", sub: "لكل يوم: الفواتير والأصناف والإجمالي والخصم والصافي والنقدي",
    days: "الفترة", d7: "٧ أيام", d14: "١٤ يوم", d30: "٣٠ يوم", d90: "٩٠ يوم",
    date: "التاريخ", bills: "الفواتير", items: "الأصناف", gross: "قيمة الفواتير", disc: "الخصم",
    net: "الصافي", cash: "نقدي", noncash: "غير نقدي", total: "الإجمالي", branch: "الفرع", all: "كل الفروع",
    csv: "تصدير Excel", pdf: "طباعة / PDF", empty: "لا توجد بيانات", brand: "صيدليات بروكير" },
  en: { title: "Daily Sales Report", sub: "Per day: bills, items, gross, discount, net, cash",
    days: "Period", d7: "7 days", d14: "14 days", d30: "30 days", d90: "90 days",
    date: "Date", bills: "Bills", items: "Items", gross: "Gross", disc: "Discount",
    net: "Net", cash: "Cash", noncash: "Non-cash", total: "Total", branch: "Branch", all: "All branches",
    csv: "Export Excel", pdf: "Print / PDF", empty: "No data", brand: "ProCare Pharmacies" },
};

const n = (v) => (Number(v) || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });

export default function DailySalesReport() {
  const { lang, branch } = useUI();
  const t = L[lang] || L.ar;
  const [days, setDays] = useState(30);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const bq = branch ? `&branch_id=${branch}` : "";
      const res = await apiFetch(`/api/dashboard/daily-sales?days=${days}${bq}`).catch(() => ({ series: [] }));
      // endpoint returns {days, series:[...]} OR a bare array depending on caller
      setRows(res.series || res || []);
    } finally {
      setLoading(false);
    }
  }, [days, branch]);

  useEffect(() => { load(); }, [load]);

  // Only days that actually have activity (eStock report skips empty days).
  const active = rows.filter((r) => r.bills > 0);
  const tot = active.reduce((a, r) => ({
    bills: a.bills + (r.bills || 0), items: a.items + (r.items || 0),
    gross: a.gross + (r.gross || 0), disc: a.disc + (r.discount || 0),
    net: a.net + (r.net || 0), cash: a.cash + (r.cash || 0), noncash: a.noncash + (r.non_cash || 0),
  }), { bills: 0, items: 0, gross: 0, disc: 0, net: 0, cash: 0, noncash: 0 });

  function exportCSV() {
    const head = [t.date, t.bills, t.items, t.gross, t.disc, t.net, t.cash, t.noncash];
    const lines = active.map((r) => [r.date, r.bills, r.items, r.gross, r.discount, r.net, r.cash, r.non_cash].join(","));
    const totalLine = [t.total, tot.bills, n(tot.items), n(tot.gross), n(tot.disc), n(tot.net), n(tot.cash), n(tot.noncash)].join(",");
    const csv = "﻿" + [t.brand + " — " + t.title, head.join(","), ...lines, totalLine].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
    const a = document.createElement("a");
    a.href = url; a.download = `daily-sales-${days}d.csv`; a.click();
    URL.revokeObjectURL(url);
  }

  const cols = [t.date, t.bills, t.items, t.gross, t.disc, t.net, t.cash, t.noncash];

  return (
    <div className="page">
      <style>{`@media print { .no-print { display:none !important } .print-only { display:block !important } .shell .sidebar { display:none } }
        .print-only { display:none }`}</style>

      <div className="print-only" style={{ textAlign: "center", marginBottom: 12 }}>
        <div style={{ fontSize: 20, fontWeight: 800, color: "#1a76b4" }}>{t.brand}</div>
        <div style={{ fontWeight: 700 }}>{t.title}</div>
      </div>

      <div className="topbar no-print">
        <div>
          <h1 className="page-title">{t.title}</h1>
          <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{t.sub}</div>
        </div>
        <div className="controls">
          <span className="badge">{branch ? `${t.branch} #${branch}` : t.all}</span>
          <select className="select" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>{t.d7}</option>
            <option value={14}>{t.d14}</option>
            <option value={30}>{t.d30}</option>
            <option value={90}>{t.d90}</option>
          </select>
          <button className="btn" onClick={exportCSV}>⬇ {t.csv}</button>
          <button className="btn" onClick={() => window.print()}>🖨 {t.pdf}</button>
        </div>
      </div>

      <div className="table-wrapper">
        <table className="tbl">
          <thead>
            <tr>{cols.map((c, i) => <th key={i} className={i ? "num" : ""}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {active.map((r) => (
              <tr key={r.date}>
                <td>{r.date}</td>
                <td className="num">{r.bills}</td>
                <td className="num">{n(r.items)}</td>
                <td className="num">{n(r.gross)}</td>
                <td className="num">{n(r.discount)}</td>
                <td className="num" style={{ fontWeight: 700 }}>{n(r.net)}</td>
                <td className="num">{n(r.cash)}</td>
                <td className="num">{n(r.non_cash)}</td>
              </tr>
            ))}
            {active.length === 0 && <tr><td colSpan={8} className="empty">{loading ? "…" : t.empty}</td></tr>}
          </tbody>
          {active.length > 0 && (
            <tfoot>
              <tr style={{ fontWeight: 800, borderTop: "2px solid var(--primary)" }}>
                <td>{t.total}</td>
                <td className="num">{tot.bills}</td>
                <td className="num">{n(tot.items)}</td>
                <td className="num">{n(tot.gross)}</td>
                <td className="num">{n(tot.disc)}</td>
                <td className="num">{n(tot.net)}</td>
                <td className="num">{n(tot.cash)}</td>
                <td className="num">{n(tot.noncash)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
