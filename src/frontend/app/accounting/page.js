"use client";

import { useEffect, useState } from "react";
import { useUI } from "../providers";
import Shell from "../components/Shell";
import { t } from "../i18n";
import { api } from "../api";

export default function AccountingPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [trialBalance, setTrialBalance] = useState(null);
  const [salesSummary, setSalesSummary] = useState(null);
  const [profitLoss, setProfitLoss] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [chart, setChart] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("chart");
  const [daysFilter, setDaysFilter] = useState(30);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [tbRes, ssRes, plRes, ledgerRes, chartRes] = await Promise.all([
          api.get("/accounting/trial-balance", { branch_id: branch || undefined }),
          api.get("/accounting/sales-summary", {
            branch_id: branch || undefined,
            days: daysFilter,
          }),
          api.get("/accounting/profit-loss", {
            branch_id: branch || undefined,
            days: daysFilter,
          }),
          api.get("/accounting/ledger", {
            branch_id: branch || undefined,
            days: daysFilter,
          }),
          api.chartOfAccounts(branch).catch(() => null),
        ]);
        setTrialBalance(tbRes);
        setSalesSummary(ssRes);
        setProfitLoss(plRes);
        setLedger(ledgerRes.entries || []);
        setChart(chartRes);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [branch, daysFilter]);

  const fmt = (v) => Number(v || 0).toLocaleString("en-US");

  if (loading) return <Shell titleKey="nav_accounting"><div className="page">{L("loading")}</div></Shell>;

  return (
    <Shell titleKey="nav_accounting">
      <div className="page">
        <div style={{ marginBottom: 16, padding: "8px 16px", background: "var(--surface)", borderRadius: 8 }}>
          <label>
            {L("period")}:{" "}
            <select className="select" value={daysFilter} onChange={(e) => setDaysFilter(Number(e.target.value))}>
              <option value={7}>{L("days_7")}</option>
              <option value={30}>{L("days_30")}</option>
              <option value={90}>{L("days_90")}</option>
              <option value={365}>{L("days_365")}</option>
            </select>
          </label>
        </div>

        {/* Revenue & profit KPIs */}
        <div className="kpi-row">
          <div className="kpi-box">
            <div className="kpi-value">{fmt(profitLoss?.revenue)}</div>
            <div className="kpi-label">{L("revenue")} ({L("egp")})</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{fmt(salesSummary?.total_returns_net)}</div>
            <div className="kpi-label">{L("total_returns")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{fmt(profitLoss?.net_revenue)}</div>
            <div className="kpi-label">{L("net_revenue")}</div>
          </div>
          <div className="kpi-box">
            <div
              className="kpi-value"
              style={{ color: (profitLoss?.gross_profit || 0) >= 0 ? "var(--ok)" : "var(--danger)" }}
            >
              {fmt(profitLoss?.gross_profit)}
            </div>
            <div className="kpi-label">{L("gross_profit")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{profitLoss?.margin_pct ?? 0}%</div>
            <div className="kpi-label">{L("margin")}</div>
          </div>
        </div>

        {/* Paid amount by payment type */}
        <div className="kpi-row">
          <div className="kpi-box">
            <div className="kpi-value" style={{ color: "var(--ok)" }}>{fmt(salesSummary?.total_paid)}</div>
            <div className="kpi-label">{L("paid_amount")}</div>
            <div className="kpi-sub">
              {L("paid_cash")}: {fmt(salesSummary?.cash_paid)} · {L("paid_card")}: {fmt(salesSummary?.card_paid)}
            </div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{fmt(salesSummary?.cash_paid)}</div>
            <div className="kpi-label">{L("paid_cash")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{fmt(salesSummary?.card_paid)}</div>
            <div className="kpi-label">{L("paid_card")}</div>
          </div>
          <div className="kpi-box">
            <div
              className="kpi-value"
              style={{ color: (salesSummary?.credit_sales || 0) > 0 ? "var(--danger)" : undefined }}
            >
              {fmt(salesSummary?.credit_sales)}
            </div>
            <div className="kpi-label">{L("credit_unpaid")}</div>
          </div>
        </div>

        <div className="tabs">
          <button className={`tab ${activeTab === "chart" ? "active" : ""}`} onClick={() => setActiveTab("chart")}>
            {L("coa_title")}
          </button>
          <button className={`tab ${activeTab === "trial" ? "active" : ""}`} onClick={() => setActiveTab("trial")}>
            {L("trial_balance")}
          </button>
          <button className={`tab ${activeTab === "ledger" ? "active" : ""}`} onClick={() => setActiveTab("ledger")}>
            {L("ledger")}
          </button>
        </div>

        {activeTab === "chart" && chart && (
          <>
            <p style={{ marginBottom: 8 }}>
              <span className={`badge ${chart.balanced ? "ok" : "danger"}`}>
                {chart.balanced ? L("coa_balanced") : L("coa_unbalanced")}
              </span>{" "}
              <span className="muted">
                {L("coa_debit")}: {parseFloat(chart.total_debit).toLocaleString("en-US")} · {L("coa_credit")}: {parseFloat(chart.total_credit).toLocaleString("en-US")}
              </span>
            </p>
            <div className="table-wrapper">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{L("account")}</th>
                    <th className="num">{L("coa_debit")}</th>
                    <th className="num">{L("coa_credit")}</th>
                    <th className="num">{L("coa_balance")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(chart.groups || []).map((g) => (
                    <>
                      <tr key={g.type} style={{ cursor: "pointer", fontWeight: 700, background: "var(--surface)" }} onClick={() => setExpanded((x) => ({ ...x, [g.type]: !x[g.type] }))}>
                        <td>{expanded[g.type] ? "▾" : "▸"} {g.label} <span className="muted" style={{ fontWeight: 400 }}>({g.accounts.length})</span></td>
                        <td className="num">{parseFloat(g.debit).toLocaleString("en-US")}</td>
                        <td className="num">{parseFloat(g.credit).toLocaleString("en-US")}</td>
                        <td className="num">{parseFloat(g.balance).toLocaleString("en-US")}</td>
                      </tr>
                      {expanded[g.type] && g.accounts.map((a, i) => (
                        <tr key={`${g.type}-${a.ref ?? i}`}>
                          <td style={{ paddingInlineStart: 28 }} className="muted">{a.name}</td>
                          <td className="num">{parseFloat(a.debit).toLocaleString("en-US")}</td>
                          <td className="num">{parseFloat(a.credit).toLocaleString("en-US")}</td>
                          <td className="num">{parseFloat(a.balance).toLocaleString("en-US")}</td>
                        </tr>
                      ))}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {activeTab === "trial" && trialBalance && (
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("account")}</th>
                  <th>{L("debit")}</th>
                  <th>{L("credit")}</th>
                  <th>{L("balance")}</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(trialBalance.accounts || {}).map(([key, acc]) => (
                  <tr key={key}>
                    <td>{acc.type}</td>
                    <td>{parseFloat(acc.debit).toLocaleString("en-US")}</td>
                    <td>{parseFloat(acc.credit).toLocaleString("en-US")}</td>
                    <td>{parseFloat(acc.balance).toLocaleString("en-US")}</td>
                  </tr>
                ))}
                <tr style={{ fontWeight: "bold", borderTop: "1px solid var(--border)" }}>
                  <td>{L("total")}</td>
                  <td>{parseFloat(trialBalance.total_debit).toLocaleString("en-US")}</td>
                  <td>{parseFloat(trialBalance.total_credit).toLocaleString("en-US")}</td>
                  <td>-</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "ledger" && (
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("date")}</th>
                  <th>{L("account_type")}</th>
                  <th>{L("debit")}</th>
                  <th>{L("credit")}</th>
                  <th>{L("note")}</th>
                </tr>
              </thead>
              <tbody>
                {ledger.length === 0 ? (
                  <tr><td colSpan="5" className="empty">{L("none")}</td></tr>
                ) : (
                  ledger.map((e) => (
                    <tr key={e.entry_id}>
                      <td>{e.entry_date ? new Date(e.entry_date).toLocaleDateString("en-US") : "-"}</td>
                      <td>{e.account_type}</td>
                      <td>{parseFloat(e.debit).toLocaleString("en-US")}</td>
                      <td>{parseFloat(e.credit).toLocaleString("en-US")}</td>
                      <td>{e.note || "-"}</td>
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
