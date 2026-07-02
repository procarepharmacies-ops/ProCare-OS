"use client";

import { useEffect, useState } from "react";
import { useUI } from "../providers";
import Shell from "../components/Shell";
import { t } from "../i18n";
import { api } from "../api";

export default function TransfersPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [transfers, setTransfers] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selectedTransfer, setSelectedTransfer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [transfersRes, sumRes] = await Promise.all([
          api.get("/transfers/list", {
            branch_id: branch || undefined,
            status: statusFilter || undefined,
          }),
          api.get("/transfers/summary", { branch_id: branch || undefined }),
        ]);
        setTransfers(transfersRes.transfers || []);
        setSummary(sumRes);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [branch, statusFilter]);

  if (loading) return <Shell titleKey="nav_transfers"><div className="page">{L("loading")}</div></Shell>;

  return (
    <Shell titleKey="nav_transfers">
      <div className="page">
        <div className="kpi-row">
          <div className="kpi-box">
            <div className="kpi-value">{summary?.pending_transfers || "0"}</div>
            <div className="kpi-label">{L("pending_transfers")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{summary?.completed_transfers || "0"}</div>
            <div className="kpi-label">{L("completed_transfers")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{summary?.total_transfers || "0"}</div>
            <div className="kpi-label">{L("transfers")}</div>
          </div>
        </div>

        <div style={{ marginBottom: 16, padding: "8px 16px", background: "var(--surface)", borderRadius: 8 }}>
          <label>
            {L("filter_status")}:{" "}
            <select className="select" value={statusFilter || ""} onChange={(e) => setStatusFilter(e.target.value || null)}>
              <option value="">{L("all")}</option>
              <option value="requested">{L("status_requested")}</option>
              <option value="in_transit">{L("status_in_transit")}</option>
              <option value="received">{L("status_received")}</option>
              <option value="cancelled">{L("status_cancelled")}</option>
            </select>
          </label>
        </div>

        {selectedTransfer && (
          <div className="card" style={{ marginBottom: 16 }}>
            <button className="btn" onClick={() => setSelectedTransfer(null)} style={{ marginBottom: 12 }}>
              {L("go_back")}
            </button>
            <h3>{L("transfer")} #{selectedTransfer.transfer_id}</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
              <div><strong>{L("from_branch")}:</strong> {selectedTransfer.from_branch_name}</div>
              <div><strong>{L("to_branch")}:</strong> {selectedTransfer.to_branch_name}</div>
              <div><strong>{L("status")}:</strong> {selectedTransfer.status}</div>
              <div><strong>{L("requested_at")}:</strong> {selectedTransfer.created_at ? new Date(selectedTransfer.created_at).toLocaleDateString("en-US") : "-"}</div>
            </div>

            <h4>{L("product")}</h4>
            <table className="tbl" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>{L("product")}</th>
                  <th>{L("qty")}</th>
                  <th>{L("buy_price")}</th>
                  <th>{L("expiry_date")}</th>
                </tr>
              </thead>
              <tbody>
                {selectedTransfer.lines && selectedTransfer.lines.length > 0 ? (
                  selectedTransfer.lines.map((line) => (
                    <tr key={line.line_id}>
                      <td>{line.product_name}</td>
                      <td>{parseFloat(line.amount).toLocaleString("en-US")}</td>
                      <td>{parseFloat(line.buy_price).toLocaleString("en-US")}</td>
                      <td>{line.exp_date ? new Date(line.exp_date).toLocaleDateString("en-US") : "-"}</td>
                    </tr>
                  ))
                ) : (
                  <tr><td colSpan="4" className="empty">{L("none")}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        <div className="table-wrapper">
          <table className="tbl">
            <thead>
              <tr>
                <th>ID</th>
                <th>{L("from_branch")}</th>
                <th>{L("to_branch")}</th>
                <th>{L("status")}</th>
                <th>{L("requested_at")}</th>
                <th>{L("shipped_at")}</th>
                <th>{L("received_at")}</th>
              </tr>
            </thead>
            <tbody>
              {transfers.length === 0 ? (
                <tr><td colSpan="7" className="empty">{L("none")}</td></tr>
              ) : (
                transfers.map((tr) => (
                  <tr key={tr.transfer_id} onClick={() => setSelectedTransfer(tr)} style={{ cursor: "pointer" }}>
                    <td>#{tr.transfer_id}</td>
                    <td>{tr.from_branch_name}</td>
                    <td>{tr.to_branch_name}</td>
                    <td>{tr.status}</td>
                    <td>{tr.created_at ? new Date(tr.created_at).toLocaleDateString("en-US") : "-"}</td>
                    <td>{tr.shipped_at ? new Date(tr.shipped_at).toLocaleDateString("en-US") : "-"}</td>
                    <td>{tr.received_at ? new Date(tr.received_at).toLocaleDateString("en-US") : "-"}</td>
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
