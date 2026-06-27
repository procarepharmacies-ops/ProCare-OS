"use client";

import { useEffect, useState } from "react";
import { useUI } from "../providers";
import Shell from "../components/Shell";
import { t } from "../i18n";
import api from "../api";

export default function PurchasingPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [purchases, setPurchases] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("purchases");

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [purchasesRes, draftsRes, summaryRes] = await Promise.all([
          api.get("/api/purchasing/purchases", { branch_id: branch || undefined }),
          api.get("/api/purchasing/drafts", { branch_id: branch || undefined }),
          api.get("/api/purchasing/summary", { branch_id: branch || undefined }),
        ]);
        setPurchases(purchasesRes.purchases || []);
        setDrafts(draftsRes.drafts || []);
        setSummary(summaryRes);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [branch]);

  if (loading) return <Shell titleKey="nav_purchasing"><div className="page">{L("loading")}</div></Shell>;

  return (
    <Shell titleKey="nav_purchasing">
      <div className="page">
        {/* KPIs */}
        <div className="kpi-row">
          <div className="kpi-box">
            <div className="kpi-value">{summary?.total_spent.toLocaleString() || "0"}</div>
            <div className="kpi-label">{L("total_sales")} (EGP)</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{summary?.pending_drafts || "0"}</div>
            <div className="kpi-label">{L("pending_drafts")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{summary?.total_purchases || "0"}</div>
            <div className="kpi-label">{L("purchases")}</div>
          </div>
        </div>

        {/* Tabs */}
        <div className="tabs">
          <button
            className={`tab ${activeTab === "purchases" ? "active" : ""}`}
            onClick={() => setActiveTab("purchases")}
          >
            {L("purchases")}
          </button>
          <button
            className={`tab ${activeTab === "drafts" ? "active" : ""}`}
            onClick={() => setActiveTab("drafts")}
          >
            {L("drafts")}
          </button>
        </div>

        {/* Purchases Table */}
        {activeTab === "purchases" && (
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("bill_number")}</th>
                  <th>{L("vendor")}</th>
                  <th>{L("bill_date")}</th>
                  <th>{L("total_gross")}</th>
                  <th>{L("total_discount")}</th>
                  <th>{L("total_tax")}</th>
                  <th>{L("is_return")}</th>
                </tr>
              </thead>
              <tbody>
                {purchases.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="empty">{L("none")}</td>
                  </tr>
                ) : (
                  purchases.map((p) => (
                    <tr key={p.purchase_id}>
                      <td>{p.bill_number || "-"}</td>
                      <td>{p.vendor_name}</td>
                      <td>{p.bill_date ? new Date(p.bill_date).toLocaleDateString() : "-"}</td>
                      <td>{parseFloat(p.total_gross).toLocaleString()}</td>
                      <td>{parseFloat(p.total_discount).toLocaleString()}</td>
                      <td>{parseFloat(p.total_tax).toLocaleString()}</td>
                      <td>{p.is_return ? "✓" : "-"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Drafts Table */}
        {activeTab === "drafts" && (
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("product")}</th>
                  <th>{L("vendor")}</th>
                  <th>{L("on_hand_qty")}</th>
                  <th>{L("suggested_qty")}</th>
                  <th>{L("reorder")}</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {drafts.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="empty">{L("none")}</td>
                  </tr>
                ) : (
                  drafts.map((d) => (
                    <tr key={d.draft_id}>
                      <td>{d.product_name}</td>
                      <td>{d.vendor_name || "-"}</td>
                      <td>{parseFloat(d.on_hand).toLocaleString()}</td>
                      <td>{parseFloat(d.suggested_qty).toLocaleString()}</td>
                      <td>{d.reason}</td>
                      <td>{d.status}</td>
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
