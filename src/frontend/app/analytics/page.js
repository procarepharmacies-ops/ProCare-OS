"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { BarChart, Sparkline, Donut, StackedBar, BulletBar, Heatmap, CountUp } from "../components/charts";
import Icon from "../components/icons";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

export default function AnalyticsPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAnalytics();
  }, [branch]);

  async function loadAnalytics() {
    setLoading(true);
    try {
      const [summary, daily, top, branches, forecast, forecast_risks, decisions, loyalty, staff] =
        await Promise.all([
          api.dashboardSummary(branch).catch(() => ({})),
          api.dailySales(branch, 30).catch(() => ({ series: [] })),
          api.topProducts(branch, 30).catch(() => ({ products: [] })),
          api.byBranch().catch(() => ({ branches: [] })),
          api.dashboardSummary(branch).catch(() => ({})),
          api.dashboardSummary(branch).catch(() => ({})),
          api.decisions().catch(() => ({ cards: [] })),
          api.dashboardSummary(branch).catch(() => ({})),
          api.staffNow(branch).catch(() => null),
        ]);

      setData({
        summary: summary?.kpis || {},
        daily: daily?.series || [],
        top: top?.products || [],
        branches: branches?.branches || [],
        decisions: decisions?.cards || [],
        staff: staff || null,
      });
    } catch (e) {
      console.error("Analytics load failed:", e);
    }
    setLoading(false);
  }

  if (loading || !data) return <div className="card pad tc">{L("loading")}</div>;

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");
  const pct = (n) => `${Number(n || 0).toFixed(1)}%`;

  // Branch comparison data
  const branchData = data.branches.map((b) => ({
    date: b.name || b.branch_id,
    revenue: b.sales_today || 0,
    bills: b.bills_today || 0,
  }));

  // Sales + forecast overlay
  const forecastData = data.daily.map((d) => ({
    date: d.date,
    actual: d.revenue,
    forecast: d.revenue * 1.05, // Mock forecast
  }));

  // Top products as donut
  const topDonutData = data.top.slice(0, 5).map((p) => ({
    label: p.name_ar || p.name_en,
    value: p.revenue || 0,
  }));

  // Loyalty tier distribution
  const loyaltyTiers = [
    { label: lang === "ar" ? "ذهبي" : "Gold", value: 45 },
    { label: lang === "ar" ? "فضي" : "Silver", value: 65 },
    { label: lang === "ar" ? "عادي" : "Standard", value: 190 },
  ];

  // Incentive leaderboard (mock)
  const leaderboard = [
    { name: lang === "ar" ? "محمد علي" : "Mohamed Ali", sales: 45000, incentive: 2250, points: 450 },
    { name: lang === "ar" ? "سارة أحمد" : "Sarah Ahmed", sales: 38000, incentive: 1900, points: 380 },
    { name: lang === "ar" ? "علي حسن" : "Ali Hassan", sales: 32000, incentive: 1600, points: 320 },
  ];

  // Decision cards summary
  const decisionCritical = data.decisions.filter((c) => c.severity === "critical").length;
  const decisionWarning = data.decisions.filter((c) => c.severity === "warning").length;

  return (
    <Shell titleKey="nav_analytics">
      {/* ===== Branch Comparison Strip ===== */}
      <div className="grid kpis" style={{ marginBottom: 24 }}>
        {branchData.map((b, i) => (
          <div key={i} className="card pad" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 12, color: "var(--text-sub)", marginBottom: 8 }}>{b.date}</div>
            <div style={{ fontSize: 20, fontWeight: 600, color: "var(--primary)", marginBottom: 4 }}>
              {fmt(b.revenue)} {L("egp")}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-sub)" }}>{b.bills} {L("bills")}</div>
          </div>
        ))}
      </div>

      {/* ===== Sales Trend + Forecast ===== */}
      <div className="card pad" style={{ marginBottom: 24 }}>
        <h3 style={{ marginTop: 0, marginBottom: 16 }}>{lang === "ar" ? "المبيعات و التنبؤات" : "Sales & Forecast"}</h3>
        <StackedBar
          data={forecastData.map((d) => ({ date: d.date, actual: d.actual, forecast: d.forecast }))}
          height={220}
          labelKey="date"
          series={[
            { key: "actual", label: lang === "ar" ? "فعلي" : "Actual" },
            { key: "forecast", label: lang === "ar" ? "متوقع" : "Forecast" },
          ]}
        />
      </div>

      <div className="grid" style={{ marginBottom: 24 }}>
        {/* ===== Top Products (Donut) ===== */}
        <div className="card pad">
          <h3 style={{ marginTop: 0, marginBottom: 16 }}>{lang === "ar" ? "أفضل المنتجات" : "Top Products"}</h3>
          <Donut data={topDonutData} labelKey="label" valueKey="value" />
        </div>

        {/* ===== Loyalty Tiers ===== */}
        <div className="card pad">
          <h3 style={{ marginTop: 0, marginBottom: 16 }}>{lang === "ar" ? "مستويات الولاء" : "Loyalty Tiers"}</h3>
          <Donut data={loyaltyTiers} labelKey="label" valueKey="value" />
        </div>
      </div>

      {/* ===== Sales Goals (Bullet Bars) ===== */}
      <div className="card pad" style={{ marginBottom: 24 }}>
        <h3 style={{ marginTop: 0, marginBottom: 20 }}>{lang === "ar" ? "الأهداف مقابل الفعلي" : "Goals vs Actual"}</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <BulletBar
            actual={data.summary.sales_today || 0}
            target={5000}
            max={10000}
            label={lang === "ar" ? "مبيعات اليوم" : "Today's Sales"}
            color="var(--primary)"
          />
          <BulletBar
            actual={data.summary.bills_today || 0}
            target={50}
            max={100}
            label={lang === "ar" ? "عدد الفواتير" : "Bill Count"}
            color="var(--accent)"
          />
          <BulletBar
            actual={data.summary.profit_month || 0}
            target={20000}
            max={40000}
            label={lang === "ar" ? "الربح الشهري" : "Monthly Profit"}
            color="#10b981"
          />
        </div>
      </div>

      {/* ===== Incentive Leaderboard ===== */}
      <div className="card pad" style={{ marginBottom: 24 }}>
        <h3 style={{ marginTop: 0, marginBottom: 16 }}>{lang === "ar" ? "لوحة الحوافز" : "Incentive Leaderboard"}</h3>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th style={{ textAlign: "left", padding: "8px 0", fontWeight: 600 }}>{lang === "ar" ? "الموظف" : "Employee"}</th>
                <th style={{ textAlign: "right", padding: "8px 0", fontWeight: 600 }}>{lang === "ar" ? "المبيعات" : "Sales"}</th>
                <th style={{ textAlign: "right", padding: "8px 0", fontWeight: 600 }}>{lang === "ar" ? "الحافز" : "Incentive"}</th>
                <th style={{ textAlign: "right", padding: "8px 0", fontWeight: 600 }}>{lang === "ar" ? "النقاط" : "Points"}</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.map((emp, i) => (
                <tr key={i} style={{ borderBottom: i < leaderboard.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <td style={{ padding: "12px 0", display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 18, color: "var(--text-sub)" }}>{["🥇", "🥈", "🥉"][i]}</span>
                    <span>{emp.name}</span>
                  </td>
                  <td style={{ padding: "12px 0", textAlign: "right", color: "var(--primary)", fontWeight: 500 }}>{fmt(emp.sales)}</td>
                  <td style={{ padding: "12px 0", textAlign: "right", color: "var(--accent)", fontWeight: 500 }}>{fmt(emp.incentive)}</td>
                  <td style={{ padding: "12px 0", textAlign: "right" }}>
                    <span style={{ background: "var(--primary)", color: "#fff", padding: "2px 8px", borderRadius: 12, fontSize: 11 }}>
                      {emp.points}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ===== Decision Cards Summary ===== */}
      <div className="card pad" style={{ marginBottom: 24 }}>
        <h3 style={{ marginTop: 0, marginBottom: 16 }}>{lang === "ar" ? "القرارات العاجلة" : "Urgent Decisions"}</h3>
        <div className="grid kpis">
          <div style={{ textAlign: "center", padding: 16 }}>
            <div style={{ fontSize: 32, fontWeight: 700, color: "var(--danger)" }}>
              <CountUp value={decisionCritical} />
            </div>
            <div style={{ fontSize: 12, color: "var(--text-sub)", marginTop: 4 }}>
              {lang === "ar" ? "حرج" : "Critical"}
            </div>
          </div>
          <div style={{ textAlign: "center", padding: 16 }}>
            <div style={{ fontSize: 32, fontWeight: 700, color: "#f59e0b" }}>
              <CountUp value={decisionWarning} />
            </div>
            <div style={{ fontSize: 12, color: "var(--text-sub)", marginTop: 4 }}>
              {lang === "ar" ? "تحذير" : "Warning"}
            </div>
          </div>
        </div>
      </div>

      {/* ===== Sparklines (Quick Trends) ===== */}
      <div className="card pad">
        <h3 style={{ marginTop: 0, marginBottom: 16 }}>{lang === "ar" ? "الاتجاهات السريعة" : "Quick Trends"}</h3>
        <div style={{ display: "grid", gap: 16 }}>
          {data.daily.slice(-7).map((d, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: 12, minWidth: 60 }}>{d.date}</span>
              <div style={{ flex: 1, height: 24, marginLeft: 8, marginRight: 8 }}>
                <Sparkline data={[{ value: d.revenue }]} height={24} />
              </div>
              <span style={{ fontSize: 12, fontWeight: 600, minWidth: 80, textAlign: "right" }}>
                {fmt(d.revenue)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Shell>
  );
}
