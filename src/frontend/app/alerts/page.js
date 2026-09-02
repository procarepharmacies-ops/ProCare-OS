"use client";

import { useCallback, useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

export default function AlertsPage() {
  const { lang, branch, user } = useUI();
  const L = (k) => t(lang, k);
  const [expiry, setExpiry] = useState(null);
  const [reorder, setReorder] = useState(null);
  const [loss, setLoss] = useState(null);
  const [withZeroStock, setWithZeroStock] = useState(false);
  // Pricing is a manager action (it writes to product_changes with an audit trail).
  const canFixPrice = user && (user.role === "ceo" || user.role === "manager");

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

  // Also called after an inline price fix, to re-read the list the edit changed.
  const loadBelowCost = useCallback(async () => {
    try {
      setLoss(await api.belowCost(branch, withZeroStock));
    } catch {
      setLoss({ count: 0, total_exposure: 0, items: [] });
    }
  }, [branch, withZeroStock]);

  useEffect(() => {
    loadBelowCost();
  }, [loadBelowCost]);

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");
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

      {/* Selling below cost (البيع بأقل من التكلفة) */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h3 className="section-title" style={{ margin: 0 }}>{L("below_cost")}</h3>
          {loss && loss.count > 0 && (
            <span className="badge danger">
              {fmt(loss.total_exposure)} {L("egp")}
            </span>
          )}
          <label className="muted" style={{ marginInlineStart: "auto", fontSize: 13 }}>
            <input
              type="checkbox"
              checked={withZeroStock}
              onChange={(e) => setWithZeroStock(e.target.checked)}
              style={{ marginInlineEnd: 6 }}
            />
            {L("include_zero_stock")}
          </label>
        </div>
        <p className="muted" style={{ marginTop: 4 }}>{L("below_cost_hint")}</p>
        {loss && loss.items.length > 0 && (
          <table className="tbl">
            <thead>
              <tr>
                <th>{L("product")}</th>
                <th className="num">{L("sell_price")}</th>
                <th className="num">{L("cost")}</th>
                <th className="num">{L("loss_per_unit")}</th>
                <th className="num">{L("on_hand")}</th>
                <th className="num">{L("exposure")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loss.items.map((it) => (
                <BelowCostRow
                  key={it.product_id}
                  item={it}
                  lang={lang}
                  L={L}
                  fmt={fmt}
                  name={name}
                  canFixPrice={canFixPrice}
                  onSaved={loadBelowCost}
                />
              ))}
            </tbody>
          </table>
        )}
        {loss && loss.items.length === 0 && <p className="muted">{L("none")}</p>}
        {!loss && <p className="muted">{L("loading")}</p>}
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

/** One below-cost item, with an inline price fix for managers. The suggested
 *  new price is the cost itself — the minimum that stops the bleeding; the
 *  manager sets the real margin. */
function BelowCostRow({ item, lang, L, fmt, name, canFixPrice, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [price, setPrice] = useState(String(item.cost));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const save = async () => {
    const value = Number(price);
    if (!Number.isFinite(value) || value < 0) return;
    setSaving(true);
    setErr("");
    try {
      await api.updatePricing(item.product_id, { sell_price: value });
      setEditing(false);
      await onSaved();
    } catch (e) {
      setErr(e?.message || "error");
    } finally {
      setSaving(false);
    }
  };

  const reasonLabel = {
    below_cost: L("reason_below_cost"),
    zero_margin: L("reason_zero_margin"),
    unpriced: L("reason_unpriced"),
  }[item.reason];

  return (
    <tr>
      <td>
        {name(item)}{" "}
        <span className={`badge ${item.severity === "critical" ? "danger" : ""}`}>{reasonLabel}</span>
      </td>
      <td className="num">{fmt(item.sell_price)}</td>
      <td className="num">
        {fmt(item.cost)}
        {/* A gap here means the vendor raised the price and the list never caught up. */}
        {item.cost !== item.catalogue_buy_price && (
          <div className="muted" style={{ fontSize: 11 }}>
            {L("catalogue_price")} {fmt(item.catalogue_buy_price)}
          </div>
        )}
      </td>
      <td className="num" style={{ color: "var(--danger)" }}>{fmt(item.loss_per_unit)}</td>
      <td className="num">{fmt(item.on_hand)}</td>
      <td className="num">
        <strong>{fmt(item.exposure)}</strong>
      </td>
      <td>
        {canFixPrice && !editing && (
          <button className="btn" onClick={() => setEditing(true)}>
            {L("fix_price")}
          </button>
        )}
        {editing && (
          <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
            <input
              type="number"
              min="0"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && save()}
              style={{ width: 90 }}
              aria-label={L("new_price")}
              autoFocus
            />
            <button className="btn primary" onClick={save} disabled={saving}>
              {L("save")}
            </button>
            <button className="btn" onClick={() => setEditing(false)} disabled={saving}>
              {L("cancel")}
            </button>
            {err && <span className="badge danger">{err}</span>}
          </span>
        )}
      </td>
    </tr>
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
