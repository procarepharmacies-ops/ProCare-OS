"use client";

import { useEffect, useState } from "react";
import Shell from "../../components/Shell";
import { BarChart, Sparkline, HBar, CountUp, BulletBar } from "../../components/charts";
import { useUI } from "../../providers";
import { t } from "../../i18n";
import { api } from "../../api";

export default function PerformancePage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [data, setData] = useState(null);
  const [period, setPeriod] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPerformance();
  }, [branch, period]);

  async function loadPerformance() {
    setLoading(true);
    try {
      // Mock employee performance data since API might not exist yet
      const mockEmployees = [
        {
          id: 1,
          name: lang === "ar" ? "محمد علي" : "Mohamed Ali",
          sales_total: 145000,
          sales_daily: [5000, 5200, 4800, 5500, 6000, 5800, 5700],
          bills_count: 240,
          bills_daily: [35, 36, 32, 38, 42, 40, 39],
          attachment_rate: 0.85,
          attachment_target: 0.8,
          incentive_points: 450,
          conversion_pct: 12.5,
          peak_hour: "12:00-13:00",
        },
        {
          id: 2,
          name: lang === "ar" ? "سارة أحمد" : "Sarah Ahmed",
          sales_total: 128000,
          sales_daily: [4400, 4600, 4300, 4700, 4900, 4800, 4500],
          bills_count: 210,
          bills_daily: [30, 32, 29, 33, 35, 34, 31],
          attachment_rate: 0.78,
          attachment_target: 0.8,
          incentive_points: 380,
          conversion_pct: 11.2,
          peak_hour: "11:00-12:00",
        },
        {
          id: 3,
          name: lang === "ar" ? "علي حسن" : "Ali Hassan",
          sales_total: 102000,
          sales_daily: [3500, 3600, 3400, 3700, 3800, 3900, 3400],
          bills_count: 170,
          bills_daily: [24, 25, 24, 26, 27, 28, 24],
          attachment_rate: 0.72,
          attachment_target: 0.8,
          incentive_points: 320,
          conversion_pct: 9.8,
          peak_hour: "14:00-15:00",
        },
      ];

      setData({
        employees: mockEmployees,
        period,
        summary: {
          total_sales: mockEmployees.reduce((s, e) => s + e.sales_total, 0),
          avg_sales: mockEmployees.reduce((s, e) => s + e.sales_total, 0) / mockEmployees.length,
          avg_attachment: (mockEmployees.reduce((s, e) => s + e.attachment_rate, 0) / mockEmployees.length * 100).toFixed(1),
          total_points: mockEmployees.reduce((s, e) => s + e.incentive_points, 0),
        },
      });
    } catch (e) {
      console.error("Performance load failed:", e);
      setData({ employees: [], period });
    }
    setLoading(false);
  }

  if (loading || !data) return <div className="card pad tc">{L("loading")}</div>;

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");

  return (
    <Shell titleKey="nav_employees">
      <div className="pad-lg">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <h2 style={{ margin: 0 }}>{lang === "ar" ? "أداء الفريق" : "Team Performance"}</h2>
          <select
            value={period}
            onChange={(e) => setPeriod(Number(e.target.value))}
            style={{
              padding: "8px 12px",
              borderRadius: 6,
              border: "1px solid var(--border)",
              fontSize: 13,
              background: "var(--bg)",
            }}
          >
            <option value={7}>{lang === "ar" ? "7 أيام" : "7 days"}</option>
            <option value={30}>{lang === "ar" ? "30 يوم" : "30 days"}</option>
            <option value={90}>{lang === "ar" ? "90 يوم" : "90 days"}</option>
          </select>
        </div>

        {/* ===== Summary KPIs ===== */}
        <div className="grid kpis" style={{ marginBottom: 24 }}>
          <div className="card pad" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 12, color: "var(--text-sub)", marginBottom: 8 }}>
              {lang === "ar" ? "إجمالي المبيعات" : "Total Sales"}
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: "var(--primary)", marginBottom: 4 }}>
              {fmt(data.summary.total_sales)}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-sub)" }}>{L("egp")}</div>
          </div>
          <div className="card pad" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 12, color: "var(--text-sub)", marginBottom: 8 }}>
              {lang === "ar" ? "متوسط المبيعات" : "Avg Sales/Person"}
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: "var(--accent)", marginBottom: 4 }}>
              {fmt(data.summary.avg_sales)}
            </div>
            <div style={{ fontSize: 11, color: "var(--text-sub)" }}>{L("egp")}</div>
          </div>
          <div className="card pad" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 12, color: "var(--text-sub)", marginBottom: 8 }}>
              {lang === "ar" ? "متوسط معدل التوصيل" : "Avg Attachment Rate"}
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: "#10b981", marginBottom: 4 }}>
              {data.summary.avg_attachment}%
            </div>
            <div style={{ fontSize: 11, color: "var(--text-sub)" }}>
              {lang === "ar" ? "منتجات إضافية/فاتورة" : "Extra items/bill"}
            </div>
          </div>
          <div className="card pad" style={{ textAlign: "center" }}>
            <div style={{ fontSize: 12, color: "var(--text-sub)", marginBottom: 8 }}>
              {lang === "ar" ? "إجمالي النقاط" : "Total Incentive Points"}
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: "#f59e0b", marginBottom: 4 }}>
              <CountUp value={data.summary.total_points} />
            </div>
            <div style={{ fontSize: 11, color: "var(--text-sub)" }}>
              {lang === "ar" ? "قابلة للاستبدال" : "Redeemable"}
            </div>
          </div>
        </div>

        {/* ===== Per-Employee Performance ===== */}
        {data.employees.map((emp, idx) => {
          const salesData = emp.sales_daily.map((v, i) => ({ date: `Day ${i + 1}`, revenue: v }));
          const billsData = emp.bills_daily.map((v, i) => ({ date: `Day ${i + 1}`, count: v }));
          return (
            <div key={emp.id} className="card pad" style={{ marginBottom: 24 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
                <div>
                  <h3 style={{ margin: "0 0 4px 0" }}>
                    {["🥇", "🥈", "🥉"][idx]} {emp.name}
                  </h3>
                  <div style={{ fontSize: 12, color: "var(--text-sub)" }}>
                    {lang === "ar" ? `ذروة ساعة الشراء: ${emp.peak_hour}` : `Peak hour: ${emp.peak_hour}`}
                  </div>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--primary)" }}>
                  {lang === "ar" ? "إجمالي: " : "Total: "}
                  {fmt(emp.sales_total)} {L("egp")}
                </div>
              </div>

              <div className="grid" style={{ gap: 20 }}>
                {/* Sales Trend */}
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>
                    {lang === "ar" ? "المبيعات اليومية" : "Daily Sales"}
                  </div>
                  <BarChart
                    data={salesData}
                    height={140}
                    color="var(--primary)"
                    labelKey="date"
                    valueKey="revenue"
                  />
                </div>

                {/* Bills Count */}
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>
                    {lang === "ar" ? "عدد الفواتير" : "Invoices"}
                  </div>
                  <BarChart
                    data={billsData}
                    height={140}
                    color="var(--accent)"
                    labelKey="date"
                    valueKey="count"
                  />
                </div>
              </div>

              {/* Performance Metrics */}
              <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 20 }}>
                <BulletBar
                  actual={emp.attachment_rate * 100}
                  target={emp.attachment_target * 100}
                  max={100}
                  label={lang === "ar" ? "معدل إضافة منتجات" : "Attachment Rate"}
                  color="var(--accent)"
                />
                <BulletBar
                  actual={emp.incentive_points}
                  target={400}
                  max={500}
                  label={lang === "ar" ? "نقاط الحوافز" : "Incentive Points"}
                  color="#f59e0b"
                />
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 12 }}>
                    <span>{lang === "ar" ? "معدل التحويل" : "Conversion Rate"}</span>
                    <span style={{ fontWeight: 600, color: "var(--primary)" }}>{emp.conversion_pct}%</span>
                  </div>
                  <HBar value={emp.conversion_pct} max={20} color="#10b981" />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Shell>
  );
}
