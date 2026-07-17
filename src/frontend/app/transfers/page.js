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
  const [reload, setReload] = useState(0);
  const [actionMsg, setActionMsg] = useState(null);

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
  }, [branch, statusFilter, reload]);

  // Receive-review modal state: the in-transit transfer + per-line confirmations.
  const [receiving, setReceiving] = useState(null); // { transfer, lines: {line_id: {amount, exp_date}} }

  async function act(transferId, kind) {
    try {
      if (kind === "approve") await api.approveTransfer(transferId);
      else if (kind === "ship") await api.shipTransfer(transferId);
      else await api.rejectTransfer(transferId);
      const label = kind === "approve" ? L("approved") : kind === "ship" ? L("tr_shipped") : L("rejected");
      setActionMsg({ ok: true, text: `#${transferId}: ${label}` });
      setReload((n) => n + 1);
    } catch (e) {
      setActionMsg({ ok: false, text: e?.message || L("error") });
    }
  }

  async function openReceive(tr) {
    // Load full detail (shipped lines with expiry) and seed confirmations.
    try {
      const detail = await api.get(`/transfers/${tr.transfer_id}`);
      const lines = {};
      (detail.lines || []).forEach((l) => {
        lines[l.line_id] = { amount: l.amount, exp_date: l.exp_date || "" };
      });
      setReceiving({ transfer: detail, lines });
    } catch (e) {
      setActionMsg({ ok: false, text: e?.message || L("error") });
    }
  }

  async function confirmReceive() {
    const { transfer, lines } = receiving;
    try {
      const payload = Object.entries(lines).map(([line_id, v]) => ({
        line_id: Number(line_id),
        amount: Number(v.amount),
        exp_date: v.exp_date || null,
      }));
      await api.receiveTransfer(transfer.transfer_id, payload);
      setActionMsg({ ok: true, text: `#${transfer.transfer_id}: ${L("status_received")}` });
      setReceiving(null);
      setReload((n) => n + 1);
    } catch (e) {
      setActionMsg({ ok: false, text: e?.message || L("error") });
    }
  }

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

        {receiving && (
          <div className="card" style={{ marginBottom: 16, borderColor: "var(--accent, #2a7)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <h3 style={{ margin: 0 }}>{L("tr_receive_title")} #{receiving.transfer.transfer_id}</h3>
              <button className="btn icon" onClick={() => setReceiving(null)}>✕</button>
            </div>
            <p className="muted" style={{ fontSize: 13 }}>{L("tr_receive_hint")}</p>
            <table className="tbl" style={{ width: "100%" }}>
              <thead>
                <tr>
                  <th>{L("product")}</th>
                  <th>{L("qty")} (مشحون)</th>
                  <th>{L("tr_received_qty")}</th>
                  <th>{L("expiry_date")}</th>
                </tr>
              </thead>
              <tbody>
                {(receiving.transfer.lines || []).map((l) => (
                  <tr key={l.line_id}>
                    <td>{l.product_name}</td>
                    <td className="muted">{parseFloat(l.amount).toLocaleString("en-US")}</td>
                    <td>
                      <input
                        className="input"
                        type="number"
                        min={0}
                        step="any"
                        value={receiving.lines[l.line_id]?.amount ?? ""}
                        onChange={(e) =>
                          setReceiving((r) => ({
                            ...r,
                            lines: { ...r.lines, [l.line_id]: { ...r.lines[l.line_id], amount: e.target.value } },
                          }))
                        }
                        style={{ width: 90 }}
                      />
                    </td>
                    <td>
                      <input
                        className="input"
                        type="date"
                        value={(receiving.lines[l.line_id]?.exp_date || "").slice(0, 10)}
                        onChange={(e) =>
                          setReceiving((r) => ({
                            ...r,
                            lines: { ...r.lines, [l.line_id]: { ...r.lines[l.line_id], exp_date: e.target.value } },
                          }))
                        }
                        style={{ width: 150 }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: 10 }}>
              <button className="btn primary" onClick={confirmReceive}>✓ {L("tr_confirm_receipt")}</button>
            </div>
          </div>
        )}

        {actionMsg && (
          <div className="card" style={{ marginBottom: 12, color: actionMsg.ok ? "var(--ok)" : "var(--danger)" }}>
            {actionMsg.text}
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
                <th>{L("actions")}</th>
              </tr>
            </thead>
            <tbody>
              {transfers.length === 0 ? (
                <tr><td colSpan="8" className="empty">{L("none")}</td></tr>
              ) : (
                transfers.map((tr) => (
                  <tr key={tr.transfer_id} style={{ cursor: "pointer" }}>
                    <td onClick={() => setSelectedTransfer(tr)}>#{tr.transfer_id}</td>
                    <td onClick={() => setSelectedTransfer(tr)}>{tr.from_branch_name}</td>
                    <td onClick={() => setSelectedTransfer(tr)}>{tr.to_branch_name}</td>
                    <td onClick={() => setSelectedTransfer(tr)}>
                      <span className={`badge ${tr.status === "requested" ? "warn" : tr.status === "received" ? "ok" : ""}`}>
                        {L(`status_${tr.status}`) || tr.status}
                      </span>
                    </td>
                    <td onClick={() => setSelectedTransfer(tr)}>{tr.created_at ? new Date(tr.created_at).toLocaleDateString("en-US") : "-"}</td>
                    <td onClick={() => setSelectedTransfer(tr)}>{tr.shipped_at ? new Date(tr.shipped_at).toLocaleDateString("en-US") : "-"}</td>
                    <td onClick={() => setSelectedTransfer(tr)}>{tr.received_at ? new Date(tr.received_at).toLocaleDateString("en-US") : "-"}</td>
                    <td>
                      {tr.status === "requested" ? (
                        <span style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                          <button className="btn" style={{ padding: "2px 8px" }} onClick={() => act(tr.transfer_id, "ship")}>
                            🚚 {L("tr_ship")}
                          </button>
                          <button className="btn" style={{ padding: "2px 8px" }} onClick={() => act(tr.transfer_id, "approve")} title={L("approve")}>
                            ✓
                          </button>
                          <button className="btn" style={{ padding: "2px 8px" }} onClick={() => act(tr.transfer_id, "reject")}>
                            ✕ {L("reject")}
                          </button>
                        </span>
                      ) : tr.status === "in_transit" ? (
                        <button className="btn primary" style={{ padding: "2px 8px" }} onClick={() => openReceive(tr)}>
                          📥 {L("tr_receive")}
                        </button>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
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
