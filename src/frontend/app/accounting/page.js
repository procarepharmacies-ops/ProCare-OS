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
  const [ledger, setLedger] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("trial");
  const [daysFilter, setDaysFilter] = useState(30);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [tbRes, ssRes, ledgerRes] = await Promise.all([
          api.get("/accounting/trial-balance", { branch_id: branch || undefined }),
          api.get("/accounting/sales-summary", {
            branch_id: branch || undefined,
            days: daysFilter,
          }),
          api.get("/accounting/ledger", {
            branch_id: branch || undefined,
            days: daysFilter,
          }),
        ]);
        setTrialBalance(tbRes);
        setSalesSummary(ssRes);
        setLedger(ledgerRes.entries || []);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [branch, daysFilter]);

  if (loading) return <Shell titleKey="nav_accounting"><div className="page">{L("loading")}</div></Shell>;

  return (
    <Shell titleKey="nav_accounting">
      <div className="page">
        <div className="kpi-row">
          <div className="kpi-box">
            <div className="kpi-value">{salesSummary?.total_sales_net?.toLocaleString() || "0"}</div>
            <div className="kpi-label">{L("total_sales")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{salesSummary?.total_returns_net?.toLocaleString() || "0"}</div>
            <div className="kpi-label">{L("total_returns")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{salesSummary?.net_revenue?.toLocaleString() || "0"}</div>
            <div className="kpi-label">{L("net_revenue")}</div>
          </div>
        </div>

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

        <div className="tabs">
          <button className={`tab ${activeTab === "trial" ? "active" : ""}`} onClick={() => setActiveTab("trial")}>
            {L("trial_balance")}
          </button>
          <button className={`tab ${activeTab === "ledger" ? "active" : ""}`} onClick={() => setActiveTab("ledger")}>
            {L("ledger")}
          </button>
        </div>

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
                    <td>{parseFloat(acc.debit).toLocaleString()}</td>
                    <td>{parseFloat(acc.credit).toLocaleString()}</td>
                    <td>{parseFloat(acc.balance).toLocaleString()}</td>
                  </tr>
                ))}
                <tr style={{ fontWeight: "bold", borderTop: "1px solid var(--border)" }}>
                  <td>{L("total")}</td>
                  <td>{parseFloat(trialBalance.total_debit).toLocaleString()}</td>
                  <td>{parseFloat(trialBalance.total_credit).toLocaleString()}</td>
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
                      <td>{e.entry_date ? new Date(e.entry_date).toLocaleDateString() : "-"}</td>
                      <td>{e.account_type}</td>
                      <td>{parseFloat(e.debit).toLocaleString()}</td>
                      <td>{parseFloat(e.credit).toLocaleString()}</td>
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
