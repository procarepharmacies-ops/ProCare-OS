"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

export default function AlertsPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [expiry, setExpiry] = useState(null);
  const [reorder, setReorder] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [e, r] = await Promise.all([api.expiry(branch, 90), api.reorder(branch)]);
        if (alive) {
          setExpiry(e);
          setReorder(r.drafts);
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      alive = false;
    };
  }, [branch]);

  const fmt = (n) => Number(n || 0).toLocaleString(lang === "ar" ? "ar-EG" : "en-US");
  const name = (o) => (lang === "ar" ? o.name_ar : o.name_en || o.name_ar);

  return (
    <Shell titleKey="nav_alerts">
      {/* Expiry risk */}
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 className="section-title">{L("expiry_risk")}</h3>
        {expiry && (
          <>
            <div className="grid kpis" style={{ marginBottom: 14 }}>
              <Stat label={L("expired")} value={expiry.counts.expired} danger />
              <Stat label={L("in_7")} value={expiry.counts.d7} />
              <Stat label={L("in_30")} value={expiry.counts.d30} />
              <Stat label={L("expected_loss")} value={`${fmt(expiry.expected_loss_within_horizon)} ${L("egp")}`} />
            </div>
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("product")}</th>
                  <th>{L("branch")}</th>
                  <th className="num">{L("days_left")}</th>
                  <th className="num">{L("qty")}</th>
                  <th className="num">{L("expected_loss")}</th>
                </tr>
              </thead>
              <tbody>
                {[...expiry.buckets.expired, ...expiry.buckets.d7, ...expiry.buckets.d30]
                  .slice(0, 15)
                  .map((it, i) => (
                    <tr key={i}>
                      <td>{name(it)}</td>
                      <td className="muted">{it.branch}</td>
                      <td className="num">
                        {it.days_left <= 0 ? <span className="badge danger">{L("expired")}</span> : it.days_left}
                      </td>
                      <td className="num">{fmt(it.qty)}</td>
                      <td className="num">{fmt(it.expected_loss)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </>
        )}
        {!expiry && <p className="muted">{L("loading")}</p>}
      </div>

      {/* Reorder drafts */}
      <div className="card">
        <h3 className="section-title">{L("reorder")}</h3>
        <table className="tbl">
          <thead>
            <tr>
              <th>{L("product")}</th>
              <th className="num">{L("on_hand")}</th>
              <th className="num">{L("min")}</th>
              <th className="num">{L("shortfall")}</th>
              <th className="num">{L("suggested_qty")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {reorder?.map((r) => (
              <tr key={r.product_id}>
                <td>{name(r)}</td>
                <td className="num">{fmt(r.on_hand)}</td>
                <td className="num muted">{fmt(r.min_stock)}</td>
                <td className="num">{fmt(r.shortfall)}</td>
                <td className="num">
                  <strong>{fmt(r.suggested_qty)}</strong>
                </td>
                <td>{r.transfer_candidate && <span className="badge ok">{L("transfer_hint")}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {reorder && reorder.length === 0 && <p className="muted">{L("none")}</p>}
        {!reorder && <p className="muted">{L("loading")}</p>}
      </div>
    </Shell>
  );
}

function Stat({ label, value, danger }) {
  return (
    <div className="card">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value num" style={danger ? { color: "var(--danger)" } : undefined}>
        {value}
      </div>
    </div>
  );
}
