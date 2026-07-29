"use client";

import { useEffect, useState } from "react";
import Shell from "../../components/Shell";
import { BarChart, StackedBar, BulletBar, Sparkline } from "../../components/charts";
import Icon from "../../components/icons";
import { useUI } from "../../providers";
import { t } from "../../i18n";
import { api } from "../../api";

export default function ForecastPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all"); // "all", "high_risk", "medium_risk", "ok"

  useEffect(() => {
    loadForecasts();
  }, [branch]);

  async function loadForecasts() {
    setLoading(true);
    try {
      // Mock forecast data since real API might not exist yet
      const mockForecasts = [
        {
          product_id: 1,
          name: lang === "ar" ? "بارسيتامول" : "Paracetamol",
          on_hand: 150,
          daily_avg: 12.5,
          trend: 0.05,
          stockout_days: 12,
          forecast_30: [12, 13, 12, 14, 15, 13, 14, 15, 16, 15, 14, 16, 17, 15, 14, 16, 17, 18, 16, 15, 17, 18, 19, 17, 16, 18, 19, 20, 18, 17],
          risk: "high",
          severity: "critical",
        },
        {
          product_id: 2,
          name: lang === "ar" ? "ايبوبروفين" : "Ibuprofen",
          on_hand: 280,
          daily_avg: 8.2,
          trend: -0.02,
          stockout_days: 34,
          forecast_30: [8, 8, 8, 7, 8, 8, 7, 8, 8, 7, 8, 8, 7, 8, 8, 7, 8, 8, 7, 8, 8, 7, 8, 8, 7, 8, 8, 7, 8, 8],
          risk: "low",
          severity: "ok",
        },
        {
          product_id: 3,
          name: lang === "ar" ? "أموكسيسيلين" : "Amoxicillin",
          on_hand: 420,
          daily_avg: 15.3,
          trend: 0.08,
          stockout_days: 27,
          forecast_30: [15, 16, 17, 18, 19, 17, 18, 19, 20, 21, 19, 20, 21, 22, 23, 21, 22, 23, 24, 25, 23, 24, 25, 26, 27, 25, 26, 27, 28, 29],
          risk: "medium",
          severity: "warning",
        },
        {
          product_id: 4,
          name: lang === "ar" ? "ميتفورمين" : "Metformin",
          on_hand: 1200,
          daily_avg: 22.4,
          trend: 0.03,
          stockout_days: 53,
          forecast_30: [22, 23, 22, 23, 24, 23, 22, 23, 24, 23, 22, 23, 24, 23, 22, 23, 24, 23, 22, 23, 24, 23, 22, 23, 24, 23, 22, 23, 24, 23],
          risk: "low",
          severity: "ok",
        },
      ];

      setData({
        forecasts: mockForecasts,
        summary: {
          total_products: mockForecasts.length,
          critical: mockForecasts.filter((f) => f.severity === "critical").length,
          warning: mockForecasts.filter((f) => f.severity === "warning").length,
          ok: mockForecasts.filter((f) => f.severity === "ok").length,
        },
      });
    } catch (e) {
      console.error("Forecast load failed:", e);
      setData({ forecasts: [], summary: { total_products: 0, critical: 0, warning: 0, ok: 0 } });
    }
    setLoading(false);
  }

  if (loading || !data) return <div className="card pad tc">{L("loading")}</div>;

  const filteredForecasts = data.forecasts.filter((f) => {
    if (filter === "all") return true;
    return f.risk === filter.replace("_risk", "") || (filter === "ok" && f.risk === "low");
  });

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");
  const statusColor = { critical: "var(--danger)", warning: "#f59e0b", ok: "var(--ok)" };
  const statusIcon = { critical: "alert", warning: "warning", ok: "check" };

  return (
    <Shell titleKey="nav_analytics">
      <div className="pad-lg">
        <h2 style={{ marginTop: 0, marginBottom: 24 }}>{lang === "ar" ? "توقعات الطلب" : "Demand Forecasts"}</h2>

        {/* ===== Summary Cards ===== */}
        <div className="grid kpis" style={{ marginBottom: 24 }}>
          <div className="card pad" style={{ textAlign: "center", borderLeft: `4px solid var(--danger)` }}>
            <div style={{ fontSize: 32, fontWeight: 700, color: "var(--danger)", marginBottom: 4 }}>{data.summary.critical}</div>
            <div style={{ fontSize: 12, color: "var(--text-sub)" }}>{lang === "ar" ? "حرج (خطر نفاد)" : "Critical (Stockout Risk)"}</div>
          </div>
          <div className="card pad" style={{ textAlign: "center", borderLeft: `4px solid #f59e0b` }}>
            <div style={{ fontSize: 32, fontWeight: 700, color: "#f59e0b", marginBottom: 4 }}>{data.summary.warning}</div>
            <div style={{ fontSize: 12, color: "var(--text-sub)" }}>{lang === "ar" ? "تحذير (30 يوم)" : "Warning (30-day risk)"}</div>
          </div>
          <div className="card pad" style={{ textAlign: "center", borderLeft: `4px solid var(--ok)` }}>
            <div style={{ fontSize: 32, fontWeight: 700, color: "var(--ok)", marginBottom: 4 }}>{data.summary.ok}</div>
            <div style={{ fontSize: 12, color: "var(--text-sub)" }}>{lang === "ar" ? "آمن (أكثر من 30 يوم)" : "Safe (>30 days)"}</div>
          </div>
        </div>

        {/* ===== Filter Buttons ===== */}
        <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap" }}>
          {["all", "high_risk", "medium_risk", "ok"].map((f) => (
            <button
              key={f}
              className={`btn ${filter === f ? "primary" : ""}`}
              onClick={() => setFilter(f)}
              style={{
                background: filter === f ? "var(--primary)" : "var(--bg-2)",
                color: filter === f ? "#fff" : "var(--text)",
              }}
            >
              {f === "all"
                ? lang === "ar"
                  ? "الكل"
                  : "All"
                : f === "high_risk"
                  ? lang === "ar"
                    ? "خطر عالي"
                    : "High Risk"
                  : f === "medium_risk"
                    ? lang === "ar"
                      ? "خطر متوسط"
                      : "Medium Risk"
                    : lang === "ar"
                      ? "آمن"
                      : "Safe"}
            </button>
          ))}
        </div>

        {/* ===== Forecast Cards ===== */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {filteredForecasts.map((f) => {
            const forecastData = f.forecast_30.map((v, i) => ({ date: `Day ${i + 1}`, demand: v }));
            const daysOfCover = Math.ceil(f.on_hand / (f.daily_avg || 1));
            const statusLabel = {
              critical: lang === "ar" ? "حرج — خطر نفاد خلال أسبوعين" : "Critical — Stockout within 2 weeks",
              warning: lang === "ar" ? "تحذير — قد ينفد خلال 30 يوم" : "Warning — May stockout within 30 days",
              ok: lang === "ar" ? "آمن — مخزون كافي" : "Safe — Adequate stock",
            };

            return (
              <div key={f.product_id} className="card pad">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
                  <div>
                    <h3 style={{ margin: "0 0 8px 0", display: "flex", alignItems: "center", gap: 8 }}>
                      <Icon
                        name={statusIcon[f.severity]}
                        style={{ color: statusColor[f.severity], fontSize: 20 }}
                      />
                      {f.name}
                    </h3>
                    <div style={{ fontSize: 12, color: "var(--text-sub)" }}>{statusLabel[f.severity]}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: statusColor[f.severity], marginBottom: 4 }}>
                      {f.stockout_days} {lang === "ar" ? "أيام" : "days"}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-sub)" }}>
                      {lang === "ar" ? "حتى النفاد" : "Until stockout"}
                    </div>
                  </div>
                </div>

                <div className="grid" style={{ gap: 20, marginBottom: 20 }}>
                  {/* Forecast Trend */}
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>
                      {lang === "ar" ? "توقع الطلب (30 يوم)" : "30-Day Forecast"}
                    </div>
                    <BarChart
                      data={forecastData}
                      height={120}
                      color={statusColor[f.severity]}
                      labelKey="date"
                      valueKey="demand"
                    />
                  </div>

                  {/* Inventory Bullets */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    <BulletBar
                      actual={f.on_hand}
                      target={f.daily_avg * 30}
                      max={f.daily_avg * 40}
                      label={lang === "ar" ? "المخزون الحالي" : "Current Stock"}
                      color={statusColor[f.severity]}
                    />
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>
                        {lang === "ar" ? "ملخص الإحصائيات" : "Statistics"}
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
                        <div style={{ padding: 8, background: "var(--bg-2)", borderRadius: 4 }}>
                          <div style={{ color: "var(--text-sub)", marginBottom: 2 }}>
                            {lang === "ar" ? "المبيعات اليومية" : "Daily Avg"}
                          </div>
                          <div style={{ fontWeight: 600 }}>{f.daily_avg.toFixed(1)} {lang === "ar" ? "وحدة" : "units"}</div>
                        </div>
                        <div style={{ padding: 8, background: "var(--bg-2)", borderRadius: 4 }}>
                          <div style={{ color: "var(--text-sub)", marginBottom: 2 }}>
                            {lang === "ar" ? "أيام التغطية" : "Days of Cover"}
                          </div>
                          <div style={{ fontWeight: 600 }}>{daysOfCover} {lang === "ar" ? "يوم" : "days"}</div>
                        </div>
                        <div style={{ padding: 8, background: "var(--bg-2)", borderRadius: 4 }}>
                          <div style={{ color: "var(--text-sub)", marginBottom: 2 }}>
                            {lang === "ar" ? "الاتجاه" : "Trend"}
                          </div>
                          <div style={{ fontWeight: 600, color: f.trend > 0 ? "var(--danger)" : "var(--ok)" }}>
                            {f.trend > 0 ? "↑" : "↓"} {Math.abs((f.trend * 100).toFixed(1))}%
                          </div>
                        </div>
                        <div style={{ padding: 8, background: "var(--bg-2)", borderRadius: 4 }}>
                          <div style={{ color: "var(--text-sub)", marginBottom: 2 }}>
                            {lang === "ar" ? "الرصيد الحالي" : "On Hand"}
                          </div>
                          <div style={{ fontWeight: 600 }}>{fmt(f.on_hand)} {lang === "ar" ? "وحدة" : "units"}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Action Button */}
                {(f.severity === "critical" || f.severity === "warning") && (
                  <div style={{ marginTop: 12 }}>
                    <button
                      className="btn primary"
                      style={{ display: "flex", alignItems: "center", gap: 6 }}
                    >
                      <Icon name="plus" /> {lang === "ar" ? "إنشاء طلب شراء" : "Create PO"}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </Shell>
  );
}
