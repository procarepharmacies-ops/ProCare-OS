"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Shell from "./components/Shell";
import { BarChart, HBar, CountUp } from "./components/charts";
import Icon from "./components/icons";
import DetailModal from "./components/DetailModal";
import { useUI } from "./providers";
import { t } from "./i18n";
import { api } from "./api";

export default function DashboardPage() {
  const { lang, branch, setBranch } = useUI();
  const L = (k) => t(lang, k);
  const router = useRouter();
  const [data, setData] = useState(null);
  // View: last-30-days (default) / month series / custom date range.
  const [view, setView] = useState("days");
  const [months, setMonths] = useState([]);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [rangeData, setRangeData] = useState(null);
  const [branchCmp, setBranchCmp] = useState([]);
  // Product drill-down modal (dashboard "second click").
  const [insight, setInsight] = useState(null);

  async function openProduct(productId) {
    setInsight({ loading: true });
    try {
      setInsight(await api.productInsight(productId, branch));
    } catch {
      setInsight(null);
    }
  }

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [summary, daily, top, cashiers, cmp] = await Promise.all([
          api.dashboardSummary(branch),
          api.dailySales(branch, 30),
          api.topProducts(branch, 30),
          api.cashiers(branch),
          api.byBranch().catch(() => ({ branches: [] })),
        ]);
        // Defensive defaults: a stale/mismatched backend must degrade to empty
        // charts, never crash the whole dashboard.
        if (alive) {
          setData({
            summary: summary ?? {},
            daily: daily?.series ?? [],
            top: top?.products ?? [],
            cashiers: cashiers?.cashiers ?? [],
          });
          setBranchCmp(cmp?.branches ?? []);
        }
      } catch {
        if (alive) setData({ error: true });
      }
    })();
    return () => {
      alive = false;
    };
  }, [branch]);

  useEffect(() => {
    if (view !== "month") return;
    let alive = true;
    api.monthlySales(branch, 12).then((r) => alive && setMonths(r?.months ?? [])).catch(() => {});
    return () => {
      alive = false;
    };
  }, [view, branch]);

  async function loadRange() {
    if (!fromDate || !toDate) return;
    try {
      setRangeData(await api.rangeSummary(branch, fromDate, toDate));
    } catch {
      setRangeData(null);
    }
  }

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");

  return (
    <Shell titleKey="nav_dashboard">
      {!data && <DashboardSkeleton />}
      {data?.error && <p className="badge danger">{L("offline")}</p>}
      {data && !data.error && (
        <>
          <KPIs k={data.summary.kpis} L={L} fmt={fmt} go={(href) => router.push(href)} />

          {/* View switcher: 30 days / month view / custom range */}
          <div style={{ display: "flex", gap: 8, marginTop: 16, alignItems: "center", flexWrap: "wrap" }}>
            <button className={`btn ${view === "days" ? "primary" : ""}`} onClick={() => setView("days")}>
              {L("view_days")}
            </button>
            <button className={`btn ${view === "month" ? "primary" : ""}`} onClick={() => setView("month")}>
              {L("view_month")}
            </button>
            <button className={`btn ${view === "range" ? "primary" : ""}`} onClick={() => setView("range")}>
              {L("view_range")}
            </button>
            {view === "range" && (
              <>
                <input className="input" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} title={L("from_date")} />
                <input className="input" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} title={L("to_date")} />
                <button className="btn primary" disabled={!fromDate || !toDate} onClick={loadRange}>
                  {L("apply")}
                </button>
              </>
            )}
          </div>

          {view === "range" && rangeData && (
            <div className="kpi-row" style={{ marginTop: 12 }}>
              <div className="kpi-box"><div className="kpi-value num">{fmt(rangeData.revenue)}</div><div className="kpi-label">{L("revenue")} ({L("egp")})</div></div>
              <div className="kpi-box"><div className="kpi-value num">{fmt(rangeData.bills)}</div><div className="kpi-label">{L("bills")}</div></div>
              <div className="kpi-box"><div className="kpi-value num">{fmt(rangeData.discount)}</div><div className="kpi-label">{L("discount_lbl")}</div></div>
              <div className="kpi-box"><div className="kpi-value num">{fmt(rangeData.profit)}</div><div className="kpi-label">{L("profit_lbl")}</div></div>
            </div>
          )}

          {view === "month" ? (
            <div className="card" style={{ marginTop: 16 }}>
              <h3 className="section-title">{L("view_month")}</h3>
              <BarChart data={months} valueKey="revenue" labelKey="month" />
              <div className="table-wrapper" style={{ marginTop: 12 }}>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>{L("month_lbl")}</th>
                      <th className="num">{L("bills")}</th>
                      <th className="num">{L("revenue")}</th>
                      <th className="num">{L("discount_lbl")}</th>
                      <th className="num">{L("profit_lbl")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {months.map((mo) => (
                      <tr key={mo.month}>
                        <td>{mo.month}</td>
                        <td className="num">{fmt(mo.bills)}</td>
                        <td className="num">{fmt(mo.revenue)}</td>
                        <td className="num">{fmt(mo.discount)}</td>
                        <td className="num">{fmt(mo.profit)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
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
                    onClick: p.product_id ? () => openProduct(p.product_id) : null,
                  }))}
                  fmt={fmt}
                  unit={L("egp")}
                />
              </div>
            </div>
          )}

          {/* All-branches comparison (this month) */}
          {branchCmp.length > 1 && (
            <div className="card" style={{ marginTop: 16 }}>
              <h3 className="section-title">{L("by_branch_cmp")}</h3>
              <div className="table-wrapper">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>{L("branch")}</th>
                      <th className="num">{L("bills")}</th>
                      <th className="num">{L("revenue")} ({L("egp")})</th>
                      <th className="num">{L("discount_lbl")}</th>
                      <th className="num">{L("profit_lbl")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {branchCmp.map((b) => (
                      <tr
                        key={b.branch_id}
                        style={{ cursor: "pointer" }}
                        title={L("view_details")}
                        onClick={() => { setBranch(b.branch_id); router.push("/reports"); }}
                      >
                        <td>{lang === "ar" ? b.name_ar : b.name_en || b.name_ar}</td>
                        <td className="num">{fmt(b.bills)}</td>
                        <td className="num">{fmt(b.revenue)}</td>
                        <td className="num">{fmt(b.discount)}</td>
                        <td className="num" style={{ color: b.profit >= 0 ? "var(--ok)" : "var(--danger)" }}>{fmt(b.profit)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="card" style={{ marginTop: 16 }}>
            <h3 className="section-title">{L("cashier_perf")}</h3>
            <Ranked
              rows={data.cashiers.map((c) => ({
                name: c.cashier,
                value: c.revenue,
                sub: `${c.bills} ${L("bills")}`,
                onClick: () => router.push("/employees"),
              }))}
              fmt={fmt}
              unit={L("egp")}
              color="var(--primary)"
            />
          </div>

          {insight && (
            <DetailModal
              title={insight.loading ? L("loading") : (lang === "ar" ? insight.name_ar : insight.name_en || insight.name_ar)}
              onClose={() => setInsight(null)}
            >
              {insight.loading ? (
                <p className="muted">{L("loading")}</p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div className="muted" style={{ fontSize: 13 }}>{insight.scientific_name}</div>
                  <div className="kpi-row">
                    <div className="kpi-box"><div className="kpi-value num">{fmt(insight.total_on_hand)}</div><div className="kpi-label">{L("stock")}</div></div>
                    <div className="kpi-box"><div className="kpi-value num">{fmt(insight.sell_price)}</div><div className="kpi-label">{L("egp")}</div></div>
                    <div className="kpi-box"><div className="kpi-value num">{fmt(Math.round(insight.forecast_30d?.projected_units || 0))}</div><div className="kpi-label">{L("forecast_30d")}</div></div>
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, marginBottom: 6 }}>{L("by_branch_cmp")}</div>
                    {insight.on_hand_by_branch.map((b) => (
                      <div key={b.branch_id} style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "2px 0" }}>
                        <span>{b.branch}</span>
                        <span className="num">{fmt(b.on_hand)}</span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, marginBottom: 6 }}>{L("recent_sales")}</div>
                    {insight.recent_sales.length === 0 && <p className="muted">—</p>}
                    {insight.recent_sales.slice(0, 8).map((s) => (
                      <div key={s.sale_id} style={{ display: "flex", justifyContent: "space-between", fontSize: 13, padding: "2px 0" }}>
                        <span className="muted">{s.date}</span>
                        <span className="num">{fmt(s.qty)} × · {fmt(s.total)} {L("egp")}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </DetailModal>
          )}
        </>
      )}
    </Shell>
  );
}

function KPIs({ k, L, fmt, go }) {
  // Every number links to its detail screen (owner: "link any dashboard
  // number to see more details").
  const cards = [
    { label: L("sales_today"), value: k.sales_today, sub: `${k.bills_today} ${L("bills")}`, ico: "receipt", href: "/reports" },
    { label: L("sales_month"), value: k.sales_month, sub: L("egp"), ico: "coins", href: "/reports" },
    { label: L("profit_month"), value: k.profit_month, sub: L("egp"), ico: "chart", href: "/reports" },
    { label: L("low_stock"), value: k.low_stock, sub: "", ico: "pill", href: "/alerts" },
    { label: L("expiring_30"), value: k.expiring_30, sub: "", ico: "bell", href: "/alerts" },
    { label: L("debtors"), value: k.debtors, sub: "", ico: "customers", href: "/customers" },
  ];
  return (
    <div className="grid kpis">
      {cards.map((c) => (
        <div
          className="card"
          key={c.label}
          onClick={() => go(c.href)}
          style={{ cursor: "pointer" }}
          title={L("view_details")}
        >
          <span className="kpi-ico">
            <Icon name={c.ico} size={19} />
          </span>
          <div className="kpi-label">{c.label}</div>
          <div className="kpi-value num">
            <CountUp value={c.value} format={(n) => fmt(Math.round(n))} />
          </div>
          <div className="kpi-sub">{c.sub || L("view_details")}</div>
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
        <div
          key={i}
          onClick={r.onClick || undefined}
          style={r.onClick ? { cursor: "pointer" } : undefined}
          title={r.onClick ? "↗" : undefined}
        >
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, marginBottom: 4 }}>
            <span>{r.name}{r.onClick ? " ›" : ""}</span>
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
