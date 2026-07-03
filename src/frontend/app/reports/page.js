"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { BarChart, HBar } from "../components/charts";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

const TABS = ["daily", "sales", "pl", "purchasing", "stock", "cashiers", "productivity"];

export default function ReportsPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [tab, setTab] = useState("daily");
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const fmt = (n) => Number(n || 0).toLocaleString("en-US");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [salesSummary, profitLoss, byCustomer, daily, top, cashiers, purchSummary, expiry, lowStock, dailyReport, productivity, footfall] = await Promise.all([
          api.get("/accounting/sales-summary", { branch_id: branch || undefined, days }),
          api.profitLoss(branch, days),
          api.salesByCustomer(branch, days),
          api.dailySales(branch, days),
          api.topProducts(branch, days),
          api.cashiers(branch),
          api.get("/purchasing/summary", { branch_id: branch || undefined }),
          api.expiry(branch, 30),
          api.lowStock(branch),
          api.get("/insights/daily", { branch_id: branch || undefined }),
          api.get("/insights/productivity", { branch_id: branch || undefined, days }),
          api.get("/footfall/summary", { branch_id: branch || undefined, days: Math.min(days, 90) }),
        ]);
        if (alive) {
          setData({
            salesSummary,
            profitLoss,
            byCustomer: byCustomer.customers,
            daily: daily.series,
            top: top.products,
            cashiers: cashiers.cashiers,
            purchSummary,
            expiry,
            lowStock: lowStock.items,
            dailyReport,
            productivity,
            footfall,
          });
        }
      } catch {
        if (alive) setData({ error: true });
      }
    })();
    return () => {
      alive = false;
    };
  }, [branch, days]);

  return (
    <Shell titleKey="nav_reports">
      <div className="page">
        <div className="tabs" style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          {TABS.map((tb) => (
            <button
              key={tb}
              className={`btn ${tab === tb ? "primary" : ""}`}
              onClick={() => setTab(tb)}
            >
              {L(`report_${tb}`)}
            </button>
          ))}
          <select className="select" value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ marginInlineStart: "auto" }}>
            {[7, 30, 90, 365].map((d) => (
              <option key={d} value={d}>
                {d} {L("days_unit")}
              </option>
            ))}
          </select>
        </div>

        {!data && <p className="muted">{L("loading")}</p>}
        {data?.error && <p className="badge danger">{L("offline")}</p>}

        {data && !data.error && tab === "daily" && (
          <>
            <div className="kpi-row">
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.dailyReport.sales.revenue)}</div>
                <div className="kpi-label">{L("sales_today")} ({L("egp")})</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.dailyReport.sales.bills}</div>
                <div className="kpi-label">{L("bills_today")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.dailyReport.sales.returns}</div>
                <div className="kpi-label">{L("returns_lbl")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.dailyReport.visitors}</div>
                <div className="kpi-label">{L("visitors")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.dailyReport.conversion_pct != null ? `${data.dailyReport.conversion_pct}%` : "—"}</div>
                <div className="kpi-label">{L("conversion")}</div>
              </div>
            </div>
            <div className="kpi-row">
              <div className="kpi-box">
                <div className="kpi-value">{data.dailyReport.tasks.pending}</div>
                <div className="kpi-label">{L("pending_tasks")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.dailyReport.tasks.done_today}</div>
                <div className="kpi-label">{L("done_today")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.dailyReport.alerts.low_stock}</div>
                <div className="kpi-label">{L("low_stock")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.dailyReport.alerts.expiring_30d}</div>
                <div className="kpi-label">{L("expiring_30")}</div>
              </div>
            </div>
            {!data.footfall.counter_connected && (
              <p className="badge warn" style={{ display: "block", padding: 10 }}>{L("counter_offline")}</p>
            )}
          </>
        )}

        {data && !data.error && tab === "productivity" && (
          <>
            <div className="kpi-row">
              <div className="kpi-box">
                <div className="kpi-value">{data.productivity.busiest_hour != null ? `${data.productivity.busiest_hour}:00` : "—"}</div>
                <div className="kpi-label">{L("busiest_hour")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.productivity.quietest_open_hour != null ? `${data.productivity.quietest_open_hour}:00` : "—"}</div>
                <div className="kpi-label">{L("quietest_hour")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.footfall.total_visitors}</div>
                <div className="kpi-label">{L("visitors")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.footfall.conversion_pct != null ? `${data.footfall.conversion_pct}%` : "—"}</div>
                <div className="kpi-label">{L("conversion")}</div>
              </div>
            </div>

            <div className="card" style={{ marginTop: 16 }}>
              <h3 className="section-title">{L("hourly_rhythm")}</h3>
              <BarChart
                data={data.productivity.hourly_total.map((v, h) => ({ hour: `${h}:00`, bills: v }))}
                valueKey="bills"
                labelKey="hour"
                height={120}
              />
            </div>

            <div className="table-wrapper" style={{ marginTop: 16 }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{L("employee")}</th>
                    <th>{L("bills_count")}</th>
                    <th>{L("revenue")}</th>
                    <th>{L("avg_bill")}</th>
                    <th>{L("bills_per_day")}</th>
                    <th>{L("active_days")}</th>
                    <th>{L("peak_hour")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.productivity.employees.length === 0 ? (
                    <tr><td colSpan="7" className="empty">{L("none")}</td></tr>
                  ) : (
                    data.productivity.employees.map((e) => (
                      <tr key={e.employee_id}>
                        <td>{e.name}</td>
                        <td>{e.bills}</td>
                        <td>{fmt(e.revenue)}</td>
                        <td>{fmt(e.avg_bill)}</td>
                        <td>{e.bills_per_active_day}</td>
                        <td>{e.active_days}</td>
                        <td>{e.peak_hour != null ? `${e.peak_hour}:00` : "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {!data.footfall.counter_connected && (
              <p className="badge warn" style={{ display: "block", padding: 10, marginTop: 12 }}>{L("counter_offline")}</p>
            )}
          </>
        )}

        {data && !data.error && tab === "sales" && (
          <>
            <div className="kpi-row">
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.salesSummary.total_sales_net)}</div>
                <div className="kpi-label">{L("total_sales_net")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.salesSummary.total_returns_net)}</div>
                <div className="kpi-label">{L("total_returns_net")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.salesSummary.net_revenue)}</div>
                <div className="kpi-label">{L("net_revenue")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.salesSummary.num_sales)}</div>
                <div className="kpi-label">{L("num_sales")}</div>
              </div>
            </div>
            <div className="card" style={{ marginTop: 16 }}>
              <h3 className="section-title">{L("daily_sales")}</h3>
              <BarChart data={data.daily} valueKey="revenue" labelKey="date" />
            </div>
            {data.byCustomer.length > 0 && (
              <div className="card" style={{ marginTop: 16 }}>
                <h3 className="section-title">{L("sales_by_customer")}</h3>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>{L("customer")}</th>
                      <th className="num">{L("invoices_count")}</th>
                      <th className="num">{L("revenue")} ({L("egp")})</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.byCustomer.map((c) => (
                      <tr key={c.customer_id}>
                        <td>{lang === "ar" ? c.name_ar : c.name_en || c.name_ar}</td>
                        <td className="num">{fmt(c.invoices)}</td>
                        <td className="num">{fmt(c.revenue)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="card" style={{ marginTop: 16 }}>
              <h3 className="section-title">{L("top_products")}</h3>
              {data.top.map((p, i) => (
                <div key={i} style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                    <span>{lang === "ar" ? p.name_ar : p.name_en || p.name_ar}</span>
                    <span>{fmt(p.revenue)} {L("egp")}</span>
                  </div>
                  <HBar value={p.revenue} max={data.top[0]?.revenue} />
                </div>
              ))}
            </div>
          </>
        )}

        {data && !data.error && tab === "pl" && (
          <>
            <div className="kpi-row">
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.profitLoss.revenue)}</div>
                <div className="kpi-label">{L("revenue")} ({L("egp")})</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.profitLoss.returns_refund)}</div>
                <div className="kpi-label">{L("returns_refund")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.profitLoss.net_revenue)}</div>
                <div className="kpi-label">{L("net_revenue")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.profitLoss.cogs)}</div>
                <div className="kpi-label">{L("cogs")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value" style={{ color: data.profitLoss.gross_profit >= 0 ? "var(--ok)" : "var(--danger)" }}>
                  {fmt(data.profitLoss.gross_profit)}
                </div>
                <div className="kpi-label">{L("gross_profit")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.profitLoss.margin_pct}%</div>
                <div className="kpi-label">{L("margin")}</div>
              </div>
            </div>
            <p className="muted" style={{ marginTop: 12, fontSize: 12 }}>
              {lang === "ar"
                ? "مجمل الربح = صافي الإيرادات − تكلفة البضاعة المباعة (التكلفة المسجلة وقت البيع)"
                : "Gross profit = net revenue − cost of goods sold (cost captured at sale time)"}
            </p>
          </>
        )}

        {data && !data.error && tab === "purchasing" && (
          <div className="kpi-row">
            <div className="kpi-box">
              <div className="kpi-value">{fmt(data.purchSummary.total_purchases)}</div>
              <div className="kpi-label">{L("total_purchases")}</div>
            </div>
            <div className="kpi-box">
              <div className="kpi-value">{fmt(data.purchSummary.total_spent)}</div>
              <div className="kpi-label">{L("total_purchase_amount")}</div>
            </div>
          </div>
        )}

        {data && !data.error && tab === "stock" && (
          <>
            <div className="kpi-row">
              <div className="kpi-box">
                <div className="kpi-value">{data.expiry?.counts?.d30 ?? 0}</div>
                <div className="kpi-label">{L("expiring_30")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{fmt(data.expiry?.expected_loss_within_horizon)}</div>
                <div className="kpi-label">{L("expected_loss")}</div>
              </div>
              <div className="kpi-box">
                <div className="kpi-value">{data.lowStock?.length ?? 0}</div>
                <div className="kpi-label">{L("low_stock")}</div>
              </div>
            </div>
            <div className="table-wrapper" style={{ marginTop: 16 }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{L("product")}</th>
                    <th>{L("on_hand")}</th>
                    <th>{L("expires_in")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const b = data.expiry?.buckets || {};
                    const rows = [...(b.expired || []), ...(b.d7 || []), ...(b.d30 || []), ...(b.d90 || [])];
                    if (rows.length === 0) {
                      return (
                        <tr>
                          <td colSpan="3" className="empty">{L("none")}</td>
                        </tr>
                      );
                    }
                    return rows.slice(0, 30).map((row, i) => (
                      <tr key={i}>
                        <td>{lang === "ar" ? row.name_ar : row.name_en || row.name_ar}</td>
                        <td>{fmt(row.qty)}</td>
                        <td>{row.days_left} {L("days_unit")}</td>
                      </tr>
                    ));
                  })()}
                </tbody>
              </table>
            </div>
          </>
        )}

        {data && !data.error && tab === "cashiers" && (
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("cashier")}</th>
                  <th>{L("bills_count")}</th>
                  <th>{L("revenue")}</th>
                </tr>
              </thead>
              <tbody>
                {data.cashiers.length === 0 ? (
                  <tr>
                    <td colSpan="3" className="empty">{L("none")}</td>
                  </tr>
                ) : (
                  data.cashiers.map((c, i) => (
                    <tr key={i}>
                      <td>{c.cashier}</td>
                      <td>{c.bills}</td>
                      <td>{fmt(c.revenue)}</td>
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
