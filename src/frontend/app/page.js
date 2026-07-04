"use client";

import { useEffect, useState } from "react";
import Shell from "./components/Shell";
import { BarChart, HBar, CountUp } from "./components/charts";
import Icon from "./components/icons";
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
        // Defensive defaults: a stale/mismatched backend must degrade to empty
        // charts, never crash the whole dashboard.
        if (alive)
          setData({
            summary: summary ?? {},
            daily: daily?.series ?? [],
            top: top?.products ?? [],
            cashiers: cashiers?.cashiers ?? [],
          });
      } catch {
        if (alive) setData({ error: true });
      }
    })();
    return () => {
      alive = false;
    };
  }, [branch]);

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");

  return (
    <Shell titleKey="nav_dashboard">
      {!data && <DashboardSkeleton />}
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
    { label: L("sales_today"), value: k.sales_today, sub: `${k.bills_today} ${L("bills")}`, ico: "receipt" },
    { label: L("sales_month"), value: k.sales_month, sub: L("egp"), ico: "coins" },
    { label: L("profit_month"), value: k.profit_month, sub: L("egp"), ico: "chart" },
    { label: L("low_stock"), value: k.low_stock, sub: "", ico: "pill" },
    { label: L("expiring_30"), value: k.expiring_30, sub: "", ico: "bell" },
    { label: L("debtors"), value: k.debtors, sub: "", ico: "customers" },
  ];
  return (
    <div className="grid kpis">
      {cards.map((c) => (
        <div className="card" key={c.label}>
          <span className="kpi-ico">
            <Icon name={c.ico} size={19} />
          </span>
          <div className="kpi-label">{c.label}</div>
          <div className="kpi-value num">
            <CountUp value={c.value} format={(n) => fmt(Math.round(n))} />
          </div>
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

// Shimmering placeholder cards shown while the dashboard data loads.
function DashboardSkeleton() {
  return (
    <>
      <div className="grid kpis">
        {Array.from({ length: 6 }).map((_, i) => (
          <div className="card" key={i}>
            <div className="shimmer" style={{ height: 13, width: "55%" }} />
            <div className="shimmer" style={{ height: 30, width: "70%", margin: "10px 0 6px" }} />
            <div className="shimmer" style={{ height: 11, width: "35%" }} />
          </div>
        ))}
      </div>
      <div className="grid" style={{ gridTemplateColumns: "1.6fr 1fr", marginTop: 16 }}>
        <div className="card">
          <div className="shimmer" style={{ height: 180 }} />
        </div>
        <div className="card">
          <div className="shimmer" style={{ height: 180 }} />
        </div>
      </div>
    </>
  );
}
