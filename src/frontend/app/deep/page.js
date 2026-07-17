"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { BarChart, HBar } from "../components/charts";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

// Severity → the app's badge class + a stripe colour.
const SEV = {
  high: { badge: "danger", color: "var(--danger)" },
  medium: { badge: "warn", color: "var(--warning)" },
  low: { badge: "", color: "var(--muted)" },
  positive: { badge: "ok", color: "var(--ok)" },
};

export default function DeepAnalysisPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [data, setData] = useState(null);
  const fmt = (n) => Number(n || 0).toLocaleString("en-US");

  useEffect(() => {
    let alive = true;
    setData(null);
    (async () => {
      try {
        const d = await api.perfDeep(branch, 5, lang);
        if (alive) setData(d);
      } catch {
        if (alive) setData({ error: true });
      }
    })();
    return () => {
      alive = false;
    };
  }, [branch, lang]);

  return (
    <Shell titleKey="nav_deep">
      <div className="page">
        {!data && <p className="muted">{L("loading")}</p>}
        {data?.error && <p className="badge danger">{L("offline")}</p>}

        {data && !data.error && (
          <>
            <p className="muted" style={{ marginTop: -4, marginBottom: 14, fontSize: 13 }}>
              {L("deep_subtitle")} · {data.period.range[0]}–{data.period.range[1]} · {data.as_of}
            </p>

            {/* Scorecard */}
            <div className="kpi-row">
              <div className="kpi-box">
                <div className="kpi-value" style={{ color: "var(--danger)" }}>{data.scorecard.high_risks}</div>
                <div className="kpi-label">{L("deep_high_risks")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value" style={{ color: "var(--warning)" }}>{data.scorecard.medium_risks}</div>
                <div className="kpi-label">{L("deep_watch_items")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value" style={{ color: "var(--ok)" }}>{data.scorecard.strengths}</div>
                <div className="kpi-label">{L("deep_strengths")}</div>
              </div>
            </div>

            {/* Executive summary */}
            <div className="card" style={{ marginTop: 16, padding: 18 }}>
              <h3 className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <span>{L("deep_exec_summary")}</span>
                <span className="kpi-sub" style={{ fontWeight: 400 }}>{L("deep_generated_by")}: {data.narrative_engine}</span>
              </h3>
              <p style={{ fontSize: 14.5, lineHeight: 1.7, color: "var(--text)" }}>{data.narrative}</p>
            </div>

            {/* KPI tiles */}
            <div className="kpi-row" style={{ marginTop: 16 }}>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.sales.totals.revenue)}</div>
                <div className="kpi-label">{L("perf_revenue")} ({L("egp")})</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.sales.totals.gross_profit)}</div>
                <div className="kpi-label">{L("perf_gross_profit")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.sales.totals.invoices)}</div>
                <div className="kpi-label">{L("perf_invoices")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.inventory.snapshot.stock_value_at_cost)}</div>
                <div className="kpi-label">{L("perf_stock_value_cost")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.inventory.turnover.annual_inventory_turns ?? "—"}</div>
                <div className="kpi-label">{L("deep_turns_yr")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.inventory.snapshot.payables_to_vendors)}</div>
                <div className="kpi-label">{L("perf_payables")}</div>
              </div>
            </div>

            {/* 5-year revenue trend */}
            <div className="card" style={{ marginTop: 16, padding: 18 }}>
              <h3 className="section-title">{L("perf_5yr_title")}</h3>
              <BarChart data={data.sales.yearly} valueKey="revenue" labelKey="year" />
            </div>

            {/* Findings + recommendations */}
            <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16, marginTop: 16 }} className="deep-cols">
              <div>
                <h3 className="section-title">{L("deep_findings")}</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
                  {data.findings.map((f, i) => {
                    const s = SEV[f.severity] || SEV.low;
                    return (
                      <div key={i} className="card" style={{ padding: "11px 13px", borderInlineStart: `4px solid ${s.color}` }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 13, fontWeight: 600 }}>{lang === "ar" ? f.title_ar : f.title_en}</span>
                          <span className={`badge ${s.badge}`} style={{ marginInlineStart: "auto", fontSize: 10 }}>
                            {L(`deep_sev_${f.severity}`)}
                          </span>
                        </div>
                        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 5, lineHeight: 1.5 }}>
                          {lang === "ar" ? f.detail_ar : f.detail_en}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div className="card" style={{ padding: 18, alignSelf: "start" }}>
                <h3 className="section-title">{L("deep_recommendations")}</h3>
                {data.recommendations.length === 0 ? (
                  <p className="muted">{L("none")}</p>
                ) : (
                  data.recommendations.map((r, i) => (
                    <div key={i} style={{ display: "flex", gap: 9, padding: "9px 0", borderBottom: i < data.recommendations.length - 1 ? "1px solid var(--border)" : "none", fontSize: 12.5 }}>
                      <span style={{ color: "var(--primary)", fontWeight: 700 }}>{String(i + 1).padStart(2, "0")}</span>
                      <span>{lang === "ar" ? r.action_ar : r.action_en}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* By branch */}
            {data.by_branch && data.by_branch.length > 0 && (
              <div className="table-wrapper" style={{ marginTop: 16 }}>
                <h3 className="section-title">{L("perf_by_branch")}</h3>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>{L("branch")}</th>
                      <th className="num">{L("perf_revenue")}</th>
                      <th className="num">{L("perf_gross_profit")}</th>
                      <th className="num">{L("perf_invoices")}</th>
                      <th className="num">{L("perf_stock_value")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_branch.map((b) => (
                      <tr key={b.branch_id}>
                        <td>{lang === "ar" ? b.name_ar : b.name_en || b.name_ar}</td>
                        <td className="num">{fmt(b.totals.revenue)}</td>
                        <td className="num">{fmt(b.totals.gross_profit)}</td>
                        <td className="num">{fmt(b.totals.invoices)}</td>
                        <td className="num">{fmt(b.snapshot.stock_value_at_cost)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Supplier concentration + inventory + customers */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }} className="deep-cols">
              <div className="card" style={{ padding: 18 }}>
                <h3 className="section-title">{L("deep_supplier_conc")}</h3>
                <div className="kpi-sub" style={{ marginBottom: 10 }}>
                  {data.suppliers.top_vendor} · {data.suppliers.top_vendor_share_pct}% · {L("deep_hhi")} {data.suppliers.herfindahl_index}
                </div>
                {data.suppliers.ranking.map((r, i) => (
                  <div key={i} style={{ marginBottom: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5 }}>
                      <span>{r.name_en || r.name_ar}</span>
                      <span>{fmt(r.spend)} · {r.share_pct}%</span>
                    </div>
                    <HBar value={r.spend} max={data.suppliers.ranking[0]?.spend} />
                  </div>
                ))}
              </div>

              <div className="card" style={{ padding: 18 }}>
                <h3 className="section-title">{L("deep_inventory_health")}</h3>
                <Metric L={L} k="perf_stock_value_cost" v={`${fmt(data.inventory.snapshot.stock_value_at_cost)} ${L("egp")}`} />
                <Metric L={L} k="deep_days_cover" v={data.inventory.turnover.days_of_stock_cover ?? "—"} />
                <Metric L={L} k="perf_expired_value" v={`${fmt(data.inventory.snapshot.expired_in_stock_value)} ${L("egp")}`} danger={data.inventory.snapshot.expired_in_stock_value > 0} />
                <Metric L={L} k="deep_dead_stock" v={`${data.inventory.dead_stock.count} · ${fmt(data.inventory.dead_stock.value_at_cost)} ${L("egp")}`} />
                <Metric L={L} k="low_stock" v={data.inventory.snapshot.low_stock_products} />

                <h3 className="section-title" style={{ marginTop: 16 }}>{L("deep_customers_retention")}</h3>
                <Metric L={L} k="deep_registered" v={data.customers.registered} />
                <Metric L={L} k="deep_active_90" v={data.customers.active_90d} />
                <Metric L={L} k="deep_lapsed_365" v={data.customers.lapsed_365d} />
                <Metric L={L} k="perf_receivables" v={`${fmt(data.customers.receivables)} ${L("egp")}`} />
                <Metric L={L} k="over_limit" v={data.customers.over_limit} danger={data.customers.over_limit > 0} />
              </div>
            </div>
          </>
        )}
      </div>

      <style jsx>{`
        @media (max-width: 820px) {
          :global(.deep-cols) {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </Shell>
  );
}

function Metric({ L, k, v, danger }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
      <span className="muted">{L(k)}</span>
      <span style={{ fontWeight: 600, color: danger ? "var(--danger)" : "var(--text)" }}>{v}</span>
    </div>
  );
}
