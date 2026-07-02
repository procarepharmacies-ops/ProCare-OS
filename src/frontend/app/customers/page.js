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
              </tr>
            ))}
          </tbody>
        </table>
        {!rows && <p className="muted" style={{ padding: 16 }}>{L("loading")}</p>}
      </div>
    </Shell>
  );
}
