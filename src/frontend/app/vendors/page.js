"use client";

import { useEffect, useState } from "react";
import { useUI } from "../providers";
import Shell from "../components/Shell";
import { t } from "../i18n";
import { api } from "../api";

export default function VendorsPage() {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  const [vendors, setVendors] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selectedVendor, setSelectedVendor] = useState(null);
  const [vendorPurchases, setVendorPurchases] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [vendorsRes, sumRes] = await Promise.all([
          api.get("/api/vendors/list"),
          api.get("/api/vendors/summary"),
        ]);
        setVendors(vendorsRes.vendors || []);
        setSummary(sumRes);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const viewVendorDetail = async (vendor) => {
    try {
      const [detailRes, purchasesRes] = await Promise.all([
        api.get(`/api/vendors/${vendor.vendor_id}`),
        api.get(`/api/vendors/${vendor.vendor_id}/purchases`),
      ]);
      setSelectedVendor(detailRes);
      setVendorPurchases(purchasesRes.purchases || []);
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) return <Shell titleKey="nav_vendors"><div className="page">{L("loading")}</div></Shell>;

  return (
    <Shell titleKey="nav_vendors">
      <div className="page">
        {/* KPIs */}
        <div className="kpi-row">
          <div className="kpi-box">
            <div className="kpi-value">{summary?.total_vendors || "0"}</div>
            <div className="kpi-label">{L("vendors")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{summary?.active_vendors || "0"}</div>
            <div className="kpi-label">{L("active")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{summary?.vendors_over_limit || "0"}</div>
            <div className="kpi-label">{L("vendors_over_limit")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{summary?.available_credit?.toLocaleString() || "0"}</div>
            <div className="kpi-label">{L("available_credit")}</div>
          </div>
        </div>

        {/* Detail View */}
        {selectedVendor && (
          <div className="card" style={{ marginBottom: 16 }}>
            <button
              className="btn"
              onClick={() => setSelectedVendor(null)}
              style={{ marginBottom: 12 }}
            >
              ← Back
            </button>
            <h3>{selectedVendor.name_ar}</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
              <div>
                <strong>{L("telephone")}:</strong> {selectedVendor.tel || selectedVendor.mobile || "-"}
              </div>
              <div>
                <strong>{L("credit_limit")}:</strong> {parseFloat(selectedVendor.credit_limit).toLocaleString()}
              </div>
              <div>
                <strong>{L("current_balance")}:</strong> {parseFloat(selectedVendor.current_balance).toLocaleString()}
              </div>
              <div>
                <strong>{L("available_credit")}:</strong> {parseFloat(selectedVendor.available_credit).toLocaleString()}
              </div>
              <div>
                <strong>{L("purchase_count")}:</strong> {selectedVendor.purchase_count}
              </div>
              <div>
                <strong>{L("total_spent")}:</strong> {parseFloat(selectedVendor.total_spent).toLocaleString()}
              </div>
            </div>

            <h4>{L("purchases")}</h4>
            <table className="tbl" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>{L("bill_number")}</th>
                  <th>{L("bill_date")}</th>
                  <th>{L("total_gross")}</th>
                  <th>{L("total_discount")}</th>
                  <th>{L("total_tax")}</th>
                </tr>
              </thead>
              <tbody>
                {vendorPurchases.length > 0 ? (
                  vendorPurchases.map((p) => (
                    <tr key={p.purchase_id}>
                      <td>{p.bill_number || "-"}</td>
                      <td>{p.bill_date ? new Date(p.bill_date).toLocaleDateString() : "-"}</td>
                      <td>{parseFloat(p.total_gross).toLocaleString()}</td>
                      <td>{parseFloat(p.total_discount).toLocaleString()}</td>
                      <td>{parseFloat(p.total_tax).toLocaleString()}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="5" className="empty">{L("none")}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Vendors Table */}
        <div className="table-wrapper">
          <table className="tbl">
            <thead>
              <tr>
                <th>{L("vendor")}</th>
                <th>{L("telephone")}</th>
                <th>{L("credit_limit")}</th>
                <th>{L("current_balance")}</th>
                <th>{L("available_credit")}</th>
                <th>{L("active")}</th>
              </tr>
            </thead>
            <tbody>
              {vendors.length === 0 ? (
                <tr>
                  <td colSpan="6" className="empty">{L("none")}</td>
                </tr>
              ) : (
                vendors.map((v) => (
                  <tr
                    key={v.vendor_id}
                    onClick={() => viewVendorDetail(v)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{v.name_ar}</td>
                    <td>{v.tel || v.mobile || "-"}</td>
                    <td>{parseFloat(v.credit_limit).toLocaleString()}</td>
                    <td>{parseFloat(v.current_balance).toLocaleString()}</td>
                    <td
                      style={{
                        color: v.available_credit < 0 ? "var(--danger)" : "var(--ok)",
                        fontWeight: v.available_credit < 0 ? "bold" : "normal",
                      }}
                    >
                      {parseFloat(v.available_credit).toLocaleString()}
                    </td>
                    <td>{v.is_active ? "✓" : "✗"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}
