"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

export default function CustomersPage() {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  const [debtorsOnly, setDebtorsOnly] = useState(false);
  const [rows, setRows] = useState(null);
  // Account statement (eStock's Gedo_customers ledger) for the opened customer.
  const [statement, setStatement] = useState(null);
  const [statementFor, setStatementFor] = useState(null);
  // Loyalty points panel for the opened customer.
  const [loyaltyData, setLoyaltyData] = useState(null);
  const [loyaltyFor, setLoyaltyFor] = useState(null);
  // Customer 360 profile panel.
  const [profile, setProfile] = useState(null);
  const [profileFor, setProfileFor] = useState(null);
  const [addrDraft, setAddrDraft] = useState("");
  const [redeemPts, setRedeemPts] = useState("");
  const [profMsg, setProfMsg] = useState(null);

  async function openProfile(customerId) {
    if (profileFor === customerId) {
      setProfileFor(null);
      setProfile(null);
      return;
    }
    setProfileFor(customerId);
    setProfile(null);
    setProfMsg(null);
    try {
      const p = await api.customerProfile(customerId);
      setProfile(p);
      setAddrDraft(p.address || "");
    } catch {
      setProfileFor(null);
    }
  }

  async function saveAddress() {
    try {
      await api.updateCustomer(profileFor, { address: addrDraft });
      setProfile((p) => ({ ...p, address: addrDraft }));
      setProfMsg({ ok: true, text: "✓" });
    } catch (e) {
      setProfMsg({ ok: false, text: e?.message || "error" });
    }
  }

  async function redeem() {
    const pts = Number(redeemPts);
    if (!(pts > 0)) return;
    try {
      // Negative adjustment = redemption.
      await api.adjustLoyalty(profileFor, { points: -Math.abs(pts), note: "استبدال نقاط" });
      const p = await api.customerProfile(profileFor);
      setProfile(p);
      setRedeemPts("");
      setProfMsg({ ok: true, text: L("cust_redeem") + " ✓" });
    } catch (e) {
      setProfMsg({ ok: false, text: e?.message || "error" });
    }
  }

  function sendMessage() {
    // Open WhatsApp with the customer's number — works without a configured
    // Cloud API token (pharmacist sends from their own WhatsApp).
    const mobile = (profile?.mobile || "").replace(/[^0-9]/g, "");
    if (!mobile) return;
    const intl = mobile.startsWith("0") ? "2" + mobile : mobile; // Egypt country code
    window.open(`https://wa.me/${intl}`, "_blank");
  }

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api.customers(debtorsOnly);
        if (alive) setRows(r.customers);
      } catch {
        if (alive) setRows([]);
      }
    })();
    return () => {
      alive = false;
    };
  }, [debtorsOnly]);

  async function openStatement(customerId) {
    if (statementFor === customerId) {
      setStatementFor(null);
      setStatement(null);
      return;
    }
    setStatementFor(customerId);
    setStatement(null);
    try {
      setStatement(await api.customerStatement(customerId));
    } catch {
      setStatementFor(null);
    }
  }

  async function openLoyalty(customerId) {
    if (loyaltyFor === customerId) {
      setLoyaltyFor(null);
      setLoyaltyData(null);
      return;
    }
    setLoyaltyFor(customerId);
    setLoyaltyData(null);
    try {
      setLoyaltyData(await api.loyalty(customerId));
    } catch {
      setLoyaltyFor(null);
    }
  }

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");

  return (
    <Shell titleKey="nav_customers">
      <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <input type="checkbox" checked={debtorsOnly} onChange={(e) => setDebtorsOnly(e.target.checked)} />
        {L("debtors_only")}
      </label>
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>{L("customer")}</th>
              <th>{L("mobile")}</th>
              <th className="num">{L("credit_limit")}</th>
              <th className="num">{L("balance")}</th>
              <th className="num">{L("available_credit")}</th>
              <th></th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows?.map((c) => (
              <tr key={c.customer_id}>
                <td>{lang === "ar" ? c.name_ar : c.name_en || c.name_ar}</td>
                <td className="muted">{c.mobile || "—"}</td>
                <td className="num">{fmt(c.credit_limit)}</td>
                <td className="num">{fmt(c.current_balance)}</td>
                <td className="num">{fmt(c.available_credit)}</td>
                <td>{c.over_limit && <span className="badge danger">{L("over_limit")}</span>}</td>
                <td>
                  <button className="btn" onClick={() => openProfile(c.customer_id)}>
                    👤 {L("cust_profile")}
                  </button>{" "}
                  <button className="btn" onClick={() => openStatement(c.customer_id)}>
                    {L("statement")}
                  </button>{" "}
                  <button className="btn" onClick={() => openLoyalty(c.customer_id)}>
                    ⭐ {L("loyalty_title")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows && <p className="muted" style={{ padding: 16 }}>{L("loading")}</p>}
      </div>

      {profileFor && (
        <div className="card" style={{ marginTop: 16 }}>
          {!profile && <p className="muted">{L("loading")}</p>}
          {profile && (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 className="section-title" style={{ margin: 0 }}>
                  👤 {lang === "ar" ? profile.name_ar : profile.name_en || profile.name_ar}
                </h3>
                <button className="btn icon" onClick={() => { setProfileFor(null); setProfile(null); }}>✕</button>
              </div>
              {/* KPIs */}
              <div className="grid" style={{ gridTemplateColumns: "repeat(4,1fr)", gap: 10, margin: "10px 0" }}>
                <div className="card"><div className="muted">{L("cust_points")}</div><b>{fmt(profile.loyalty_points)}</b></div>
                <div className="card"><div className="muted">{L("cust_total_spent")}</div><b>{fmt(profile.total_spent)}</b></div>
                <div className="card"><div className="muted">{L("cust_visits")}</div><b>{profile.visit_count}</b></div>
                <div className="card"><div className="muted">{L("balance")}</div><b>{fmt(profile.current_balance)}</b></div>
              </div>
              {/* Address + contact + actions */}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
                <span className="muted">{L("cust_address")}:</span>
                <input className="input" value={addrDraft} onChange={(e) => setAddrDraft(e.target.value)} style={{ minWidth: 240 }} />
                <button className="btn" onClick={saveAddress}>{L("cust_save")}</button>
                <span className="muted">📞 {profile.mobile || "—"}</span>
                {profile.mobile && <button className="btn" onClick={sendMessage}>💬 {L("cust_message")}</button>}
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
                <span className="muted">{L("cust_redeem")}:</span>
                <input className="input" type="number" min={1} placeholder={L("cust_points")} value={redeemPts} onChange={(e) => setRedeemPts(e.target.value)} style={{ width: 120 }} />
                <button className="btn primary" disabled={!(Number(redeemPts) > 0)} onClick={redeem}>⭐ {L("cust_redeem")}</button>
                {profMsg && <span className={`badge ${profMsg.ok ? "ok" : "danger"}`}>{profMsg.text}</span>}
              </div>
              {/* Medicines they take */}
              <h4>{L("cust_medicines")}</h4>
              <table className="tbl" style={{ marginBottom: 16 }}>
                <thead><tr><th>{L("product")}</th><th className="num">{L("cust_times")}</th><th className="num">{L("qty")}</th><th>{L("cust_last")}</th></tr></thead>
                <tbody>
                  {profile.medicines.length === 0 ? (
                    <tr><td colSpan="4" className="empty">{L("none")}</td></tr>
                  ) : profile.medicines.map((med) => (
                    <tr key={med.product_id}>
                      <td>{lang === "ar" ? med.name_ar : med.name_en || med.name_ar}</td>
                      <td className="num">{med.times_bought}</td>
                      <td className="num">{fmt(med.total_qty)}</td>
                      <td className="muted">{med.last_bought ? med.last_bought.slice(0, 10) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {/* Purchase history */}
              <h4>{L("cust_history")}</h4>
              <table className="tbl">
                <thead><tr><th>#</th><th>{L("date")}</th><th className="num">{L("total")}</th></tr></thead>
                <tbody>
                  {profile.history.length === 0 ? (
                    <tr><td colSpan="3" className="empty">{L("none")}</td></tr>
                  ) : profile.history.map((h) => (
                    <tr key={h.sale_id}>
                      <td>#{h.sale_id}{h.is_return ? " ↩" : ""}</td>
                      <td className="muted">{h.date ? h.date.slice(0, 10) : "—"}</td>
                      <td className="num">{fmt(h.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {loyaltyFor && (
        <div className="card" style={{ marginTop: 16 }}>
          {!loyaltyData && <p className="muted">{L("loading")}</p>}
          {loyaltyData && (
            <>
              <h3 className="section-title">
                ⭐ {L("loyalty_title")} — {loyaltyData.customer}
              </h3>
              <p style={{ fontSize: 18, fontWeight: 700 }}>
                {fmt(loyaltyData.points)} {L("points")}{" "}
                <span className="muted" style={{ fontSize: 14, fontWeight: 400 }}>
                  ≈ {fmt(loyaltyData.value_egp)} {L("egp")}
                </span>
              </p>
              {loyaltyData.history.length === 0 && <p className="muted">{L("no_entries")}</p>}
              {loyaltyData.history.length > 0 && (
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>{L("date")}</th>
                      <th>{L("note")}</th>
                      <th className="num">{L("points")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loyaltyData.history.map((h) => (
                      <tr key={h.id}>
                        <td className="muted">{h.at ? new Date(h.at).toLocaleDateString() : "—"}</td>
                        <td>{h.note || h.kind}</td>
                        <td className="num" style={{ color: h.points >= 0 ? "var(--ok, green)" : "var(--danger, red)" }}>
                          {h.points >= 0 ? "+" : ""}{fmt(h.points)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      )}

      {statementFor && (
        <div className="card" style={{ marginTop: 16 }}>
          {!statement && <p className="muted">{L("loading")}</p>}
          {statement && (
            <>
              <h3 className="section-title">
                {L("statement")} — {lang === "ar" ? statement.name_ar : statement.name_en || statement.name_ar}
              </h3>
              <p className="muted" style={{ fontSize: 13 }}>
                {L("opening_balance")}: <span className="num">{fmt(statement.opening_balance)}</span> ·{" "}
                {L("balance")}: <span className="num">{fmt(statement.current_balance)}</span> ·{" "}
                {L("credit_limit")}: <span className="num">{fmt(statement.credit_limit)}</span>
              </p>
              {statement.entries.length === 0 && <p className="muted">{L("no_entries")}</p>}
              {statement.entries.length > 0 && (
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>{L("date")}</th>
                      <th>{L("note")}</th>
                      <th className="num">{L("debit")}</th>
                      <th className="num">{L("credit")}</th>
                      <th className="num">{L("balance_after")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {statement.entries.map((e) => (
                      <tr key={e.entry_id}>
                        <td className="muted">{new Date(e.date).toLocaleDateString()}</td>
                        <td>{e.note || e.ref_type || "—"}</td>
                        <td className="num">{e.debit ? fmt(e.debit) : "—"}</td>
                        <td className="num">{e.credit ? fmt(e.credit) : "—"}</td>
                        <td className="num">{fmt(e.balance_after)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      )}
    </Shell>
  );
}
