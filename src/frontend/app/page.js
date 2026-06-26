"use client";

import { useEffect, useState } from "react";
import Shell from "./components/Shell";
import { BarChart, HBar } from "./components/charts";
import { useUI } from "./providers";
import { t } from "./i18n";
import { api } from "./api";

export default function DashboardPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [summary, daily, top, cashiers] = await Promise.all([
          api.dashboardSummary(branch),
          api.dailySales(branch, 30),
          api.topProducts(branch, 30),
          api.cashiers(branch),
        ]);
        if (alive) setData({ summary, daily: daily.series, top: top.products, cashiers: cashiers.cashiers });
      } catch {
        if (alive) setData({ error: true });
      }
    })();
    return () => {
      alive = false;
    };
  }, [branch]);

  const fmt = (n) => Number(n || 0).toLocaleString(lang === "ar" ? "ar-EG" : "en-US");

  return (
    <Shell titleKey="nav_dashboard">
      {!data && <p className="muted">{L("loading")}</p>}
      {data?.error && <p className="badge danger">{L("offline")}</p>}
      {data && !data.error && (
        <>
          <KPIs k={data.summary.kpis} L={L} fmt={fmt} />

          <div className="grid" style={{ gridTemplateColumns: "1.6fr 1fr", marginTop: 16 }}>
            <div className="card">
              <h3 className="section-title">{L("daily_sales")}</h3>
              <BarChart data={data.daily} valueKey="revenue" labelKey="date" />
            </div>
            <div className="card">
              <h3 className="section-title">{L("top_products")}</h3>
              <Ranked
                rows={data.top.map((p) => ({
                  name: lang === "ar" ? p.name_ar : p.name_en || p.name_ar,
                  value: p.revenue,
                }))}
                fmt={fmt}
                unit={L("egp")}
              />
            </div>
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <h3 className="section-title">{L("cashier_perf")}</h3>
            <Ranked
              rows={data.cashiers.map((c) => ({ name: c.cashier, value: c.revenue, sub: `${c.bills} ${L("bills")}` }))}
              fmt={fmt}
              unit={L("egp")}
              color="var(--primary)"
            />
          </div>
        </>
      )}
    </Shell>
  );
}

function KPIs({ k, L, fmt }) {
  const cards = [
    { label: L("sales_today"), value: fmt(k.sales_today), sub: `${k.bills_today} ${L("bills")}` },
    { label: L("sales_month"), value: fmt(k.sales_month), sub: L("egp") },
    { label: L("profit_month"), value: fmt(k.profit_month), sub: L("egp") },
    { label: L("low_stock"), value: fmt(k.low_stock), sub: "" },
    { label: L("expiring_30"), value: fmt(k.expiring_30), sub: "" },
    { label: L("debtors"), value: fmt(k.debtors), sub: "" },
  ];
  return (
    <div className="grid kpis">
      {cards.map((c) => (
        <div className="card" key={c.label}>
          <div className="kpi-label">{c.label}</div>
          <div className="kpi-value num">{c.value}</div>
          <div className="kpi-sub">{c.sub}</div>
        </div>
      ))}
    </div>
  );
}

function Ranked({ rows, fmt, unit, color = "var(--accent)" }) {
  if (!rows || rows.length === 0) return <p className="muted">—</p>;
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {rows.map((r, i) => (
        <div key={i}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, marginBottom: 4 }}>
            <span>{r.name}</span>
            <span className="num muted">
              {fmt(r.value)} {unit} {r.sub ? `· ${r.sub}` : ""}
            </span>
          </div>
          <HBar value={r.value} max={max} color={color} />
        </div>
      ))}
    </div>
  );
}
