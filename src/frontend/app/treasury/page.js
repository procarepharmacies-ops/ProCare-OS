"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

// Branch treasuries: live balances, pay/receive vouchers, cash transfers
// between branches, audited manual adjustments, and the movement statement.
export default function TreasuryPage() {
  const { lang, branch, branches } = useUI();
  const L = (k) => t(lang, k);
  const fmt = (n) => Number(n || 0).toLocaleString("en-US");
  const [balances, setBalances] = useState([]);
  const [movements, setMovements] = useState([]);
  const [transfers, setTransfers] = useState([]);
  const [msg, setMsg] = useState(null);
  // Voucher form
  const [vKind, setVKind] = useState("receive");
  const [vBranch, setVBranch] = useState("");
  const [vAmount, setVAmount] = useState("");
  const [vParty, setVParty] = useState("");
  const [vNote, setVNote] = useState("");
  // Transfer form
  const [tFrom, setTFrom] = useState("");
  const [tTo, setTTo] = useState("");
  const [tAmount, setTAmount] = useState("");
  const [tNote, setTNote] = useState("");
  // Adjust form
  const [aBranch, setABranch] = useState("");
  const [aDelta, setADelta] = useState("");
  const [aNote, setANote] = useState("");

  async function refresh() {
    try {
      const [b, mv, tr] = await Promise.all([
        api.treasuryBalances(),
        api.treasuryMovements(branch),
        api.treasuryTransfers(branch),
      ]);
      setBalances(b.branches || []);
      setMovements(mv.movements || []);
      setTransfers(tr.transfers || []);
    } catch {
      /* offline / role-gated */
    }
  }
  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branch]);

  const act = async (fn, reset) => {
    setMsg(null);
    try {
      await fn();
      setMsg({ ok: true, msg: L("voucher_done") });
      reset?.();
      refresh();
    } catch (e) {
      setMsg({ ok: false, msg: e.message });
    }
  };

  const branchName = (b) => (lang === "ar" ? b.name_ar : b.name_en || b.name_ar);

  return (
    <Shell titleKey="nav_treasury">
      {/* Balances */}
      <h3 className="section-title">{L("treasury_balances")}</h3>
      <div className="kpi-row">
        {balances.map((b) => (
          <div className="kpi-box" key={b.branch_id}>
            <div className="kpi-value num">{fmt(b.balance)}</div>
            <div className="kpi-label">{branchName(b)} ({L("egp")})</div>
            <div className="kpi-sub muted" style={{ fontSize: 11 }}>
              {L("cash_in")}: {fmt(b.cash_in)} · {L("cash_out")}: {fmt(b.cash_out)}
            </div>
          </div>
        ))}
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginTop: 16, alignItems: "start" }}>
        {/* Voucher */}
        <div className="card">
          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <button className={`btn ${vKind === "receive" ? "primary" : ""}`} onClick={() => setVKind("receive")} style={{ flex: 1 }}>
              {L("receive_voucher")}
            </button>
            <button className={`btn ${vKind === "pay" ? "primary" : ""}`} onClick={() => setVKind("pay")} style={{ flex: 1 }}>
              {L("pay_voucher")}
            </button>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <select className="select" value={vBranch} onChange={(e) => setVBranch(e.target.value)}>
              <option value="">{L("branch")}…</option>
              {branches.map((b) => <option key={b.branch_id} value={b.branch_id}>{branchName(b)}</option>)}
            </select>
            <input className="input" type="number" min={0} placeholder={L("amount_lbl")} value={vAmount} onChange={(e) => setVAmount(e.target.value)} />
            <input className="input" placeholder={L("party_lbl")} value={vParty} onChange={(e) => setVParty(e.target.value)} />
            <input className="input" placeholder={L("note_lbl")} value={vNote} onChange={(e) => setVNote(e.target.value)} />
            <button
              className="btn primary"
              disabled={!vBranch || !(Number(vAmount) > 0)}
              onClick={() =>
                act(
                  () =>
                    (vKind === "receive" ? api.treasuryReceive : api.treasuryPay)({
                      branch_id: Number(vBranch),
                      amount: Number(vAmount),
                      party: vParty || null,
                      note: vNote || null,
                    }),
                  () => { setVAmount(""); setVParty(""); setVNote(""); }
                )
              }
            >
              {vKind === "receive" ? L("receive_voucher") : L("pay_voucher")}
            </button>
          </div>
        </div>

        {/* Transfer between branches */}
        <div className="card">
          <h3 className="section-title">{L("transfer_money")}</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <select className="select" value={tFrom} onChange={(e) => setTFrom(e.target.value)}>
              <option value="">{L("from_branch")}…</option>
              {branches.map((b) => <option key={b.branch_id} value={b.branch_id}>{branchName(b)}</option>)}
            </select>
            <select className="select" value={tTo} onChange={(e) => setTTo(e.target.value)}>
              <option value="">{L("to_branch")}…</option>
              {branches.filter((b) => String(b.branch_id) !== tFrom).map((b) => (
                <option key={b.branch_id} value={b.branch_id}>{branchName(b)}</option>
              ))}
            </select>
            <input className="input" type="number" min={0} placeholder={L("amount_lbl")} value={tAmount} onChange={(e) => setTAmount(e.target.value)} />
            <input className="input" placeholder={L("note_lbl")} value={tNote} onChange={(e) => setTNote(e.target.value)} />
            <button
              className="btn primary"
              disabled={!tFrom || !tTo || !(Number(tAmount) > 0)}
              onClick={() =>
                act(
                  () =>
                    api.treasuryTransfer({
                      from_branch_id: Number(tFrom),
                      to_branch_id: Number(tTo),
                      amount: Number(tAmount),
                      note: tNote || null,
                    }),
                  () => { setTAmount(""); setTNote(""); }
                )
              }
            >
              {L("transfer_money")}
            </button>
          </div>
        </div>

        {/* Adjust */}
        <div className="card">
          <h3 className="section-title">{L("adjust_balance")}</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <select className="select" value={aBranch} onChange={(e) => setABranch(e.target.value)}>
              <option value="">{L("branch")}…</option>
              {branches.map((b) => <option key={b.branch_id} value={b.branch_id}>{branchName(b)}</option>)}
            </select>
            <input className="input" type="number" placeholder={`${L("amount_lbl")} (${L("adjust_delta_hint")})`} value={aDelta} onChange={(e) => setADelta(e.target.value)} />
            <input className="input" placeholder={L("note_lbl")} value={aNote} onChange={(e) => setANote(e.target.value)} />
            <button
              className="btn primary"
              disabled={!aBranch || !Number(aDelta) || !aNote.trim()}
              onClick={() =>
                act(
                  () => api.treasuryAdjust({ branch_id: Number(aBranch), delta: Number(aDelta), note: aNote }),
                  () => { setADelta(""); setANote(""); }
                )
              }
            >
              {L("adjust_balance")}
            </button>
          </div>
        </div>
      </div>

      {msg && (
        <p className={`badge ${msg.ok ? "ok" : "danger"}`} style={{ marginTop: 12, display: "inline-block", padding: 10 }}>
          {msg.msg}
        </p>
      )}

      <div className="grid" style={{ gridTemplateColumns: "1.4fr 1fr", gap: 16, marginTop: 16, alignItems: "start" }}>
        {/* Movements */}
        <div className="card">
          <h3 className="section-title">{L("movements_lbl")}</h3>
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("bill_date")}</th>
                  <th>{L("branch")}</th>
                  <th className="num">{L("cash_in")}</th>
                  <th className="num">{L("cash_out")}</th>
                  <th>{L("note_lbl")}</th>
                </tr>
              </thead>
              <tbody>
                {movements.length === 0 ? (
                  <tr><td colSpan="5" className="empty">{L("none")}</td></tr>
                ) : (
                  movements.map((mv) => (
                    <tr key={mv.entry_id}>
                      <td className="muted">{mv.entry_date ? new Date(mv.entry_date).toLocaleDateString() : "—"}</td>
                      <td>{balances.find((b) => b.branch_id === mv.branch_id) ? branchName(balances.find((b) => b.branch_id === mv.branch_id)) : mv.branch_id}</td>
                      <td className="num" style={{ color: mv.debit > 0 ? "var(--ok)" : undefined }}>{mv.debit > 0 ? fmt(mv.debit) : ""}</td>
                      <td className="num" style={{ color: mv.credit > 0 ? "var(--danger)" : undefined }}>{mv.credit > 0 ? fmt(mv.credit) : ""}</td>
                      <td className="muted" style={{ fontSize: 12 }}>{mv.note || mv.ref_type}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Transfers */}
        <div className="card">
          <h3 className="section-title">{L("transfers_lbl")}</h3>
          <div className="table-wrapper">
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("from_branch")}</th>
                  <th>{L("to_branch")}</th>
                  <th className="num">{L("amount_lbl")}</th>
                  <th>{L("bill_date")}</th>
                </tr>
              </thead>
              <tbody>
                {transfers.length === 0 ? (
                  <tr><td colSpan="4" className="empty">{L("none")}</td></tr>
                ) : (
                  transfers.map((tr) => (
                    <tr key={tr.transfer_id}>
                      <td>{tr.from_branch_name}</td>
                      <td>{tr.to_branch_name}</td>
                      <td className="num">{fmt(tr.amount)}</td>
                      <td className="muted">{tr.created_at ? new Date(tr.created_at).toLocaleDateString() : "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Shell>
  );
}
