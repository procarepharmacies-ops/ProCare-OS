"use client";

import { useEffect, useState } from "react";
import { useUI } from "../providers";
import Shell from "../components/Shell";
import { t } from "../i18n";
import { api } from "../api";

export default function VendorsPage() {
  const { lang, branch, branches, user } = useUI();
  const L = (k) => t(lang, k);
  const [vendors, setVendors] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selectedVendor, setSelectedVendor] = useState(null);
  const [vendorPurchases, setVendorPurchases] = useState([]);
  const [statement, setStatement] = useState(null);
  const [payAmount, setPayAmount] = useState("");
  const [payMsg, setPayMsg] = useState(null);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const canPay = user && (user.role === "ceo" || user.role === "manager");

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [vendorsRes, sumRes] = await Promise.all([
          api.get("/vendors/list"),
          api.get("/vendors/summary"),
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
      const [detailRes, purchasesRes, stmtRes] = await Promise.all([
        api.get(`/vendors/${vendor.vendor_id}`),
        api.get(`/vendors/${vendor.vendor_id}/purchases`),
        api.vendorStatement(vendor.vendor_id).catch(() => null),
      ]);
      setSelectedVendor(detailRes);
      setVendorPurchases(purchasesRes.purchases || []);
      setStatement(stmtRes);
      setPayAmount("");
      setPayMsg(null);
    } catch (e) {
      console.error(e);
    }
  };

  async function payVendor() {
    setPayMsg(null);
    const branchId = Number(branch) || branches?.[0]?.branch_id || 1;
    try {
      const r = await api.payVendor(selectedVendor.vendor_id, {
        branch_id: branchId,
        amount: Number(payAmount),
        employee_id: user?.employee_id ?? null,
      });
      setPayMsg({ ok: true, text: `${L("pay_vendor")} ✓ · ${L("current_balance")}: ${r.new_balance}` });
      setPayAmount("");
      viewVendorDetail({ vendor_id: selectedVendor.vendor_id });
      setReload((n) => n + 1);
    } catch (e) {
      setPayMsg({ ok: false, text: e?.message || L("error") });
    }
  }

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
            <div className="kpi-value">{summary?.available_credit?.toLocaleString("en-US") || "0"}</div>
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
              {L("go_back")}
            </button>
            <h3>{lang === "ar" ? selectedVendor.name_ar : selectedVendor.name_en || selectedVendor.name_ar}</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
              <div>
                <strong>{L("telephone")}:</strong> {selectedVendor.tel || selectedVendor.mobile || "-"}
              </div>
              <div>
                <strong>{L("credit_limit")}:</strong> {parseFloat(selectedVendor.credit_limit).toLocaleString("en-US")}
              </div>
              <div>
                <strong>{L("current_balance")}:</strong> {parseFloat(selectedVendor.current_balance).toLocaleString("en-US")}
              </div>
              <div>
                <strong>{L("available_credit")}:</strong> {parseFloat(selectedVendor.available_credit).toLocaleString("en-US")}
              </div>
              <div>
                <strong>{L("purchase_count")}:</strong> {selectedVendor.purchase_count}
              </div>
              <div>
                <strong>{L("total_spent")}:</strong> {parseFloat(selectedVendor.total_spent).toLocaleString("en-US")}
              </div>
              <div>
                <strong>{L("avg_discount")}:</strong> {selectedVendor.avg_discount_pct ?? 0}%
              </div>
            </div>

            {/* صرف / سداد للمورد */}
            {canPay && (
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 16, padding: 10, background: "var(--surface)", borderRadius: 8 }}>
                <strong>{L("pay_vendor")}:</strong>
                <input
                  className="input"
                  type="number"
                  min={0}
                  placeholder="0.00"
                  value={payAmount}
                  onChange={(e) => setPayAmount(e.target.value)}
                  style={{ width: 130 }}
                />
                <button className="btn primary" disabled={!(Number(payAmount) > 0)} onClick={payVendor}>
                  💵 {L("pay_vendor")}
                </button>
                {payMsg && <span className={`badge ${payMsg.ok ? "ok" : "danger"}`}>{payMsg.text}</span>}
              </div>
            )}

            {/* كشف حساب المورد */}
            {statement && statement.rows && (
              <>
                <h4>{L("vendor_statement")}</h4>
                <table className="tbl" style={{ width: "100%", marginBottom: 16 }}>
                  <thead>
                    <tr>
                      <th>{L("date")}</th>
                      <th>{L("type") || "النوع"}</th>
                      <th>{L("bill_number")}</th>
                      <th>مدين</th>
                      <th>دائن</th>
                      <th>{L("current_balance")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {statement.rows.length === 0 ? (
                      <tr><td colSpan="6" className="empty">{L("none")}</td></tr>
                    ) : (
                      statement.rows.map((r, i) => (
                        <tr key={i}>
                          <td className="muted">{r.date ? r.date.slice(0, 10) : "-"}</td>
                          <td>{r.kind}</td>
                          <td className="muted">{r.ref}</td>
                          <td>{r.debit ? parseFloat(r.debit).toLocaleString("en-US") : "-"}</td>
                          <td>{r.credit ? parseFloat(r.credit).toLocaleString("en-US") : "-"}</td>
                          <td style={{ fontWeight: 600 }}>{parseFloat(r.balance).toLocaleString("en-US")}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </>
            )}

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
                      <td>{p.bill_date ? new Date(p.bill_date).toLocaleDateString("en-US") : "-"}</td>
                      <td>{parseFloat(p.total_gross).toLocaleString("en-US")}</td>
                      <td>{parseFloat(p.total_discount).toLocaleString("en-US")}</td>
                      <td>{parseFloat(p.total_tax).toLocaleString("en-US")}</td>
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
                    <td>{lang === "ar" ? v.name_ar : v.name_en || v.name_ar}</td>
                    <td>{v.tel || v.mobile || "-"}</td>
                    <td>{parseFloat(v.credit_limit).toLocaleString("en-US")}</td>
                    <td>{parseFloat(v.current_balance).toLocaleString("en-US")}</td>
                    <td
                      style={{
                        color: v.available_credit < 0 ? "var(--danger)" : "var(--ok)",
                        fontWeight: v.available_credit < 0 ? "bold" : "normal",
                      }}
                    >
                      {parseFloat(v.available_credit).toLocaleString("en-US")}
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
