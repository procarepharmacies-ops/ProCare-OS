"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { BarChart, HBar } from "../components/charts";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

const TABS = ["sales", "purchasing", "stock", "cashiers"];

export default function ReportsPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [tab, setTab] = useState("sales");
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const fmt = (n) => Number(n || 0).toLocaleString(lang === "ar" ? "ar-EG" : "en-US");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [salesSummary, daily, top, cashiers, purchSummary, expiry, lowStock] = await Promise.all([
          api.get("/accounting/sales-summary", { branch_id: branch || undefined, days }),
          api.dailySales(branch, days),
          api.topProducts(branch, days),
          api.cashiers(branch),
          api.get("/purchasing/summary", { branch_id: branch || undefined }),
          api.expiry(branch, 30),
          api.lowStock(branch),
        ]);
        if (alive) {
          setData({
            salesSummary,
            daily: daily.series,
            top: top.products,
            cashiers: cashiers.cashiers,
            purchSummary,
            expiry,
            lowStock: lowStock.items,
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
