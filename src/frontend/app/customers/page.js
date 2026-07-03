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
                  <button className="btn" onClick={() => openStatement(c.customer_id)}>
                    {L("statement")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows && <p className="muted" style={{ padding: 16 }}>{L("loading")}</p>}
      </div>

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
