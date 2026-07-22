"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Shell from "./components/Shell";
import { BarChart, HBar, CountUp } from "./components/charts";
import Icon from "./components/icons";
import DetailModal from "./components/DetailModal";
import DecisionCardsWidget from "./components/DecisionCardsWidget";
import { useUI } from "./providers";
import { t } from "./i18n";
import { api } from "./api";

export default function DashboardPage() {
  const { lang, branch, setBranch } = useUI();
  const L = (k) => t(lang, k);
  const router = useRouter();

  // Core data
  const [data, setData] = useState(null);
  const [purchasing, setPurchasing] = useState(null);
  const [cashData, setCashData] = useState([]);
  const [expenses, setExpenses] = useState(null);
  const [yoyData, setYoyData] = useState(null);
  const [staff, setStaff] = useState(null);
  const [branchCmp, setBranchCmp] = useState([]);

  // Chart/view switcher
  const [view, setView] = useState("days");
  const [months, setMonths] = useState([]);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [rangeData, setRangeData] = useState(null);
  const [yoyMode, setYoyMode] = useState("sales"); // "sales" | "profit"

  // Modals
  const [insight, setInsight] = useState(null);

  // جرد alert banner
  const [stkAlerts, setStkAlerts] = useState([]);
  const alertTimerRef = useRef(null);

  async function openProduct(productId) {
    setInsight({ loading: true });
    try {
      setInsight(await api.productInsight(productId, branch));
    } catch {
      setInsight(null);
    }
  }

  // Main data load
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [summary, daily, top, cashiers, cmp, purch, cash, exp, yoy, staffNow] =
          await Promise.all([
            api.dashboardSummary(branch),
            api.dailySales(branch, 30),
            api.topProducts(branch, 30),
            api.cashiers(branch),
            api.byBranch().catch(() => ({ branches: [] })),
            api.purchasing(branch).catch(() => null),
            api.dashboardCash().catch(() => ({ branches: [] })),
            api.expenses(branch).catch(() => null),
            api.yoy(branch).catch(() => null),
            api.staffNow(branch).catch(() => null),
          ]);
        if (alive) {
          setData({
            summary: summary ?? {},
            daily: daily?.series ?? [],
            top: top?.products ?? [],
            cashiers: cashiers?.cashiers ?? [],
          });
          setBranchCmp(cmp?.branches ?? []);
          setPurchasing(purch);
          setCashData(cash?.branches ?? []);
          setExpenses(exp);
          setYoyData(yoy);
          setStaff(staffNow);
        }
      } catch {
        if (alive) setData({ error: true });
      }
    })();
    return () => { alive = false; };
  }, [branch]);

  // Month view
  useEffect(() => {
    if (view !== "month") return;
    let alive = true;
    api.monthlySales(branch, 12).then((r) => alive && setMonths(r?.months ?? [])).catch(() => {});
    return () => { alive = false; };
  }, [view, branch]);

  // جرد alert polling (every 30s)
  const pollAlerts = useCallback(() => {
    api.stocktakingAlerts(5).then((r) => {
      if (r?.alerts?.length) setStkAlerts(r.alerts);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    pollAlerts();
    alertTimerRef.current = setInterval(pollAlerts, 30000);
    return () => clearInterval(alertTimerRef.current);
  }, [pollAlerts]);

  async function loadRange() {
    if (!fromDate || !toDate) return;
    try {
      setRangeData(await api.rangeSummary(branch, fromDate, toDate));
    } catch {
      setRangeData(null);
    }
  }

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");
  const pct = (n) => `${Number(n || 0).toFixed(1)}%`;

  // Ratio status color
  const ratioColor = { green: "var(--ok)", red: "var(--danger)", yellow: "#f59e0b" };

  return (
    <Shell titleKey="nav_dashboard">
      {/* ===== جرد Alert Banner ===== */}
      {stkAlerts.length > 0 && (
        <div
          style={{
            background: "var(--danger)",
            color: "#fff",
            padding: "10px 16px",
            borderRadius: 8,
            marginBottom: 12,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            fontWeight: 600,
            fontSize: 14,
            animation: "fadeIn .3s",
          }}
        >
          <span>
            {L("stk_alert_title")} — {stkAlerts[stkAlerts.length - 1].message}
          </span>
          <button
            className="btn"
            style={{ background: "rgba(255,255,255,.2)", color: "#fff", padding: "4px 12px", minWidth: 0 }}
            onClick={() => setStkAlerts([])}
          >
            {L("stk_alert_dismiss")}
          </button>
        </div>
      )}

      {!data && <DashboardSkeleton />}
      {data?.error && <p className="badge danger">{L("offline")}</p>}
      {data && !data.error && (
        <>
          {/* ===== KPI Row 1: Sales ===== */}
          <div className="grid kpis">
            <KpiCard
              label={L("sales_today")}
              value={data.summary.kpis?.sales_today}
              sub={`${fmt(data.summary.kpis?.bills_today)} ${L("bills")}`}
              ico="receipt"
              href="/reports"
              go={router.push.bind(router)}
              fmt={fmt}
            />
            <KpiCard
              label={L("sales_month")}
              value={data.summary.kpis?.sales_month}
              sub={`${fmt(data.summary.kpis?.bills_month ?? 0)} ${L("bills")} · ${L("egp")}`}
              ico="coins"
              href="/reports"
              go={router.push.bind(router)}
              fmt={fmt}
            />
            <KpiCard
              label={L("profit_month")}
              value={data.summary.kpis?.profit_month}
              sub={
                data.summary.kpis?.sales_month > 0
                  ? pct((data.summary.kpis.profit_month / data.summary.kpis.sales_month) * 100) +
                    " " + L("profit_margin")
                  : L("egp")
              }
              ico="chart"
              href="/reports"
              go={router.push.bind(router)}
              fmt={fmt}
              valueColor={data.summary.kpis?.profit_month >= 0 ? "var(--ok)" : "var(--danger)"}
            />
          </div>

          {/* ===== KPI Row 2: Purchasing ===== */}
          <div className="grid kpis" style={{ marginTop: 10 }}>
            <KpiCard
              label={L("purch_today")}
              value={purchasing?.purchasing_today ?? 0}
              sub={L("egp")}
              ico="pill"
              href="/purchasing"
              go={router.push.bind(router)}
              fmt={fmt}
            />
            <KpiCard
              label={L("purch_month")}
              value={purchasing?.purchasing_month ?? 0}
              sub={L("egp")}
              ico="pill"
              href="/purchasing"
              go={router.push.bind(router)}
              fmt={fmt}
            />
            <div
              className="card"
              onClick={() => router.push("/purchasing")}
              style={{ cursor: "pointer" }}
            >
              <div className="kpi-label">{L("purch_ratio")}</div>
              <div className="kpi-value num" style={{ color: ratioColor[purchasing?.ratio_status] ?? "inherit" }}>
                {pct(purchasing?.ratio_pct ?? 0)}
              </div>
              <div
                className="kpi-sub"
                style={{
                  padding: "3px 8px",
                  borderRadius: 6,
                  background: ratioColor[purchasing?.ratio_status ?? "yellow"] + "22",
                  color: ratioColor[purchasing?.ratio_status ?? "yellow"],
                  fontWeight: 600,
                  display: "inline-block",
                  fontSize: 12,
                  marginTop: 4,
                }}
              >
                {L(`purch_status_${purchasing?.ratio_status ?? "yellow"}`)} · {L("purch_ratio_target")}
              </div>
            </div>
          </div>

          {/* ===== KPI Row 3: Cash & Expenses ===== */}
          <div className="grid kpis" style={{ marginTop: 10 }}>
            {cashData.slice(0, 2).map((br, i) => (
              <KpiCard
                key={br.branch_id}
                label={L(i === 0 ? "cash_pos1" : "cash_pos2")}
                value={br.cash_balance}
                sub={br.name_ar}
                ico="coins"
                href="/treasury"
                go={router.push.bind(router)}
                fmt={fmt}
                valueColor={br.cash_balance >= 0 ? "var(--ok)" : "var(--danger)"}
              />
            ))}
            {cashData.length === 0 && [0, 1].map((i) => (
              <KpiCard
                key={i}
                label={L(i === 0 ? "cash_pos1" : "cash_pos2")}
                value={0}
                sub="—"
                ico="coins"
                href="/treasury"
                go={router.push.bind(router)}
                fmt={fmt}
              />
            ))}
            <KpiCard
              label={L("expenses_month")}
              value={expenses?.expenses_month ?? 0}
              sub={`${L("expenses_today")}: ${fmt(expenses?.expenses_today ?? 0)} ${L("egp")}`}
              ico="chart"
              href="/treasury"
              go={router.push.bind(router)}
              fmt={fmt}
              valueColor="var(--danger)"
            />
          </div>

          {/* ===== KPI Row 4: Alerts ===== */}
          <div className="grid kpis" style={{ marginTop: 10 }}>
            <KpiCard label={L("low_stock")} value={data.summary.kpis?.low_stock} sub="" ico="pill" href="/alerts" go={router.push.bind(router)} fmt={fmt} />
            <KpiCard label={L("expiring_30")} value={data.summary.kpis?.expiring_30} sub="" ico="bell" href="/alerts" go={router.push.bind(router)} fmt={fmt} />
            <KpiCard label={L("debtors")} value={data.summary.kpis?.debtors} sub="" ico="customers" href="/customers" go={router.push.bind(router)} fmt={fmt} />
          </div>

          {/* ===== Daily Decisions (القرارات اليومية) ===== */}
          <DecisionCardsWidget lang={lang} />

          {/* ===== View switcher ===== */}
          <div style={{ display: "flex", gap: 8, marginTop: 16, alignItems: "center", flexWrap: "wrap" }}>
            <button className={`btn ${view === "days" ? "primary" : ""}`} onClick={() => setView("days")}>{L("view_days")}</button>
            <button className={`btn ${view === "month" ? "primary" : ""}`} onClick={() => setView("month")}>{L("view_month")}</button>
            <button className={`btn ${view === "yoy" ? "primary" : ""}`} onClick={() => setView("yoy")}>YOY</button>
            <button className={`btn ${view === "range" ? "primary" : ""}`} onClick={() => setView("range")}>{L("view_range")}</button>
            {view === "range" && (
              <>
                <input className="input" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} title={L("from_date")} />
                <input className="input" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} title={L("to_date")} />
                <button className="btn primary" disabled={!fromDate || !toDate} onClick={loadRange}>{L("apply")}</button>
              </>
            )}
          </div>

          {/* ===== Range summary ===== */}
          {view === "range" && rangeData && (
            <div className="kpi-row" style={{ marginTop: 12 }}>
              <div className="kpi-box"><div className="kpi-value num">{fmt(rangeData.revenue)}</div><div className="kpi-label">{L("revenue")} ({L("egp")})</div></div>
              <div className="kpi-box"><div className="kpi-value num">{fmt(rangeData.bills)}</div><div className="kpi-label">{L("bills")}</div></div>
              <div className="kpi-box"><div className="kpi-value num">{fmt(rangeData.discount)}</div><div className="kpi-label">{L("discount_lbl")}</div></div>
              <div className="kpi-box"><div className="kpi-value num">{fmt(rangeData.profit)}</div><div className="kpi-label">{L("profit_lbl")}</div></div>
            </div>
          )}

          {/* ===== Month view ===== */}
          {view === "month" && (
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
                        <td className="num" style={{ color: mo.profit >= 0 ? "var(--ok)" : "var(--danger)" }}>{fmt(mo.profit)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ===== YOY Charts ===== */}
          {view === "yoy" && yoyData && (
            <div className="card" style={{ marginTop: 16 }}>
              <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center" }}>
                <h3 className="section-title" style={{ margin: 0, flex: 1 }}>
                  {yoyMode === "sales" ? L("yoy_sales") : L("yoy_profit")}
                </h3>
                <button className={`btn ${yoyMode === "sales" ? "primary" : ""}`} onClick={() => setYoyMode("sales")}>{L("revenue")}</button>
                <button className={`btn ${yoyMode === "profit" ? "primary" : ""}`} onClick={() => setYoyMode("profit")}>{L("profit_lbl")}</button>
              </div>
              <YoyChart
                current={yoyData.current_year}
                prev={yoyData.last_year}
                valueKey={yoyMode === "sales" ? "revenue" : "profit"}
                L={L}
                fmt={fmt}
              />
            </div>
          )}

          {/* ===== Daily view ===== */}
          {(view === "days" || view === "range") && (
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

          {/* ===== Branch comparison ===== */}
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

          {/* ===== Cashier performance ===== */}
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

          {/* ===== Staff widget ===== */}
          <StaffWidget staff={staff} L={L} fmt={fmt} />

          {/* ===== Product insight modal ===== */}
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

// ─── Sub-components ──────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, ico, href, go, fmt, valueColor }) {
  return (
    <div
      className="card"
      onClick={() => go(href)}
      style={{ cursor: "pointer" }}
      title={label}
    >
      <span className="kpi-ico"><Icon name={ico} size={19} /></span>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value num" style={valueColor ? { color: valueColor } : undefined}>
        <CountUp value={value} format={(n) => fmt(Math.round(n))} />
      </div>
      <div className="kpi-sub">{sub || "—"}</div>
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
            <span className="num muted">{fmt(r.value)} {unit} {r.sub ? `· ${r.sub}` : ""}</span>
          </div>
          <HBar value={r.value} max={max} color={color} />
        </div>
      ))}
    </div>
  );
}

function YoyChart({ current, prev, valueKey, L, fmt }) {
  // Build month labels from both arrays
  const allMonths = [...new Set([...prev.map(m => m.month.slice(5)), ...current.map(m => m.month.slice(5))])].sort();
  const prevMap = Object.fromEntries(prev.map(m => [m.month.slice(5), m[valueKey]]));
  const curMap = Object.fromEntries(current.map(m => [m.month.slice(5), m[valueKey]]));
  const maxVal = Math.max(...Object.values(prevMap), ...Object.values(curMap), 1);

  return (
    <div style={{ overflowX: "auto" }}>
      <div style={{ display: "flex", gap: 12, marginBottom: 8, fontSize: 12 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 12, background: "var(--primary)", borderRadius: 2, display: "inline-block" }} />
          {L("this_year")}
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 12, height: 12, background: "var(--accent)", borderRadius: 2, display: "inline-block" }} />
          {L("last_year")}
        </span>
      </div>
      <div style={{ display: "flex", gap: 6, alignItems: "flex-end", minHeight: 120 }}>
        {allMonths.map((mo) => {
          const curVal = curMap[mo] || 0;
          const prevVal = prevMap[mo] || 0;
          const curH = Math.round((curVal / maxVal) * 100);
          const prevH = Math.round((prevVal / maxVal) * 100);
          return (
            <div key={mo} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 100 }}>
                <div title={`${L("last_year")}: ${fmt(prevVal)}`} style={{ width: 10, height: prevH, background: "var(--accent)", borderRadius: "2px 2px 0 0", minHeight: prevVal > 0 ? 3 : 0 }} />
                <div title={`${L("this_year")}: ${fmt(curVal)}`} style={{ width: 10, height: curH, background: "var(--primary)", borderRadius: "2px 2px 0 0", minHeight: curVal > 0 ? 3 : 0 }} />
              </div>
              <div style={{ fontSize: 10, color: "var(--muted)", textAlign: "center" }}>{mo}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StaffWidget({ staff, L, fmt }) {
  if (!staff) return null;
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 className="section-title">{L("staff_now")}</h3>
      {staff.on_shift.length === 0 ? (
        <p className="muted">{L("staff_empty")}</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {staff.on_shift.map((emp) => (
            <div key={emp.shift_id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", background: "var(--bg-alt)", borderRadius: 8 }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{emp.name_ar}</div>
                <div className="muted" style={{ fontSize: 12 }}>{emp.role} · {emp.name_ar !== emp.name_en ? emp.name_en : ""}</div>
              </div>
              {emp.on_since && (
                <div className="muted" style={{ fontSize: 12 }}>
                  {L("staff_since")} {new Date(emp.on_since).toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {staff.next_up.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>{L("staff_next")}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {staff.next_up.map((emp) => (
              <div key={emp.employee_id} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                <span>{emp.name_ar}</span>
                <span className="muted">{emp.task}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Shimmering placeholder shown while dashboard data loads
function DashboardSkeleton() {
  return (
    <>
      {[0, 1, 2, 3].map((row) => (
        <div key={row} className="grid kpis" style={{ marginTop: row === 0 ? 0 : 10 }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div className="card" key={i}>
              <div className="shimmer" style={{ height: 13, width: "55%" }} />
              <div className="shimmer" style={{ height: 30, width: "70%", margin: "10px 0 6px" }} />
              <div className="shimmer" style={{ height: 11, width: "35%" }} />
            </div>
          ))}
        </div>
      ))}
      <div className="grid" style={{ gridTemplateColumns: "1.6fr 1fr", marginTop: 16 }}>
        <div className="card"><div className="shimmer" style={{ height: 180 }} /></div>
        <div className="card"><div className="shimmer" style={{ height: 180 }} /></div>
      </div>
    </>
  );
}
