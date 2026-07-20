"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

const METRICS = [
  { key: "egp_margin", labelKey: "inc_metric_egp" },
  { key: "margin_pct", labelKey: "inc_metric_pct" },
  { key: "profit_volume", labelKey: "inc_metric_vol" },
];

// CEO incentive builder: group the shelf by active ingredient, show the top
// 2-3 most-profitable brands of each (live-re-rankable across three metrics),
// tick the ones to push, set points, and write them into the incentive list
// the cashiers earn from.
export default function IncentivesPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const fmt = (n) => Number(n || 0).toLocaleString("en-US");
  const nameOf = (p) => (lang === "ar" ? p.name_ar : p.name_en || p.name_ar);

  const [metric, setMetric] = useState("egp_margin");
  const [topN, setTopN] = useState(3);
  const [search, setSearch] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  // product_id -> points to apply (staged, not yet saved)
  const [staged, setStaged] = useState({});
  const [defaultPts, setDefaultPts] = useState(10);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.incentiveCandidates(metric, topN, branch, search.trim());
      setData(r);
    } catch {
      setData({ error: true });
    } finally {
      setLoading(false);
    }
  }, [metric, topN, branch, search]);

  useEffect(() => {
    const id = setTimeout(load, search ? 250 : 0);
    return () => clearTimeout(id);
  }, [load, search]);

  const toggle = (p) =>
    setStaged((s) => {
      const next = { ...s };
      if (p.product_id in next) delete next[p.product_id];
      else next[p.product_id] = p.incentive_points > 0 ? p.incentive_points : defaultPts;
      return next;
    });

  const setPts = (pid, v) =>
    setStaged((s) => ({ ...s, [pid]: Math.max(0, Number(v) || 0) }));

  const stagedCount = Object.keys(staged).length;

  const apply = async () => {
    const items = Object.entries(staged).map(([pid, points]) => ({
      product_id: Number(pid),
      points: Number(points),
    }));
    if (items.length === 0) return;
    setSaving(true);
    setSavedMsg("");
    try {
      const r = await api.incentiveApply(items);
      setSavedMsg(`${L("inc_applied")}: +${r.set} / −${r.cleared}`);
      setStaged({});
      await load();
    } catch {
      setSavedMsg("✕");
    } finally {
      setSaving(false);
    }
  };

  const metricLabel = (key) => L(METRICS.find((mm) => mm.key === key).labelKey);

  return (
    <Shell titleKey="nav_incentives">
      <div className="page">
        <h2 className="section-title">{L("inc_title")}</h2>
        <p className="muted" style={{ marginTop: -4, marginBottom: 12, maxWidth: 720 }}>{L("inc_intro")}</p>

        {/* Controls */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <label className="muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{L("inc_metric")}</label>
              <div style={{ display: "inline-flex", gap: 4 }}>
                {METRICS.map((mm) => (
                  <button
                    key={mm.key}
                    className={`btn ${metric === mm.key ? "primary" : ""}`}
                    onClick={() => setMetric(mm.key)}
                  >
                    {L(mm.labelKey)}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{L("inc_topn")}</label>
              <select className="select" value={topN} onChange={(e) => setTopN(Number(e.target.value))}>
                {[2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <div style={{ flex: "1 1 220px" }}>
              <label className="muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{L("inc_search_ph")}</label>
              <input className="input" placeholder={L("inc_search_ph")} value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <div>
              <label className="muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{L("inc_default_points")}</label>
              <input className="input" type="number" min="0" style={{ width: 90 }} value={defaultPts} onChange={(e) => setDefaultPts(Math.max(0, Number(e.target.value) || 0))} />
            </div>
          </div>
          {data && !data.error && (
            <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              {fmt(data.ingredient_count)} {L("inc_ingredients_shown")} · {L("inc_on_list")}: {fmt(data.already_on_list)}
            </p>
          )}
        </div>

        {/* Sticky apply bar */}
        {stagedCount > 0 && (
          <div className="card" style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 12, position: "sticky", top: 8, zIndex: 10 }}>
            <span style={{ fontWeight: 600 }}>{stagedCount} {L("inc_brands")}</span>
            <span className="muted" style={{ fontSize: 12 }}>{L("inc_select_hint")}</span>
            <button className="btn primary" style={{ marginInlineStart: "auto" }} disabled={saving} onClick={apply}>
              {saving ? "…" : L("inc_apply")}
            </button>
            {savedMsg && <span className="badge ok">{savedMsg}</span>}
          </div>
        )}
        {stagedCount === 0 && savedMsg && (
          <p className="badge ok" style={{ display: "inline-block", marginBottom: 12 }}>{savedMsg}</p>
        )}

        {loading && <p className="muted">{L("loading")}</p>}
        {data?.error && <p className="badge danger">{L("offline")}</p>}

        {data && !data.error && data.groups.map((g) => (
          <div className="card" style={{ marginBottom: 12 }} key={g.ingredient}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
              <h3 className="section-title" style={{ margin: 0 }}>{g.ingredient}</h3>
              <span className="muted" style={{ fontSize: 12 }}>{g.brand_count} {L("inc_brands")}</span>
            </div>
            <div className="table-wrapper" style={{ boxShadow: "none", border: "none", background: "transparent" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th style={{ width: 34 }}></th>
                    <th>{L("product")}</th>
                    <th className="num">{L("inc_sell")}</th>
                    <th className="num">{L("inc_buy")}</th>
                    <th className="num">{L("inc_margin")}</th>
                    <th className="num">{L("inc_margin_pct")}</th>
                    <th className="num">{L("inc_sold90")}</th>
                    <th className="num">{L("inc_points")}</th>
                  </tr>
                </thead>
                <tbody>
                  {g.top.map((b, i) => {
                    const isStaged = b.product_id in staged;
                    const live = isStaged ? staged[b.product_id] : b.incentive_points;
                    const onList = b.incentive_points > 0;
                    return (
                      <tr key={b.product_id} style={i === 0 ? { fontWeight: 600 } : undefined}>
                        <td>
                          <input type="checkbox" checked={isStaged} onChange={() => toggle(b)} />
                        </td>
                        <td>
                          {nameOf(b)}
                          {onList && !isStaged && <span className="badge ok" style={{ marginInlineStart: 6, fontSize: 10 }}>{L("inc_on_list")}</span>}
                          {i === 0 && <span className="badge" style={{ marginInlineStart: 6, fontSize: 10 }}>★</span>}
                        </td>
                        <td className="num">{fmt(b.sell_price)}</td>
                        <td className="num">{fmt(b.buy_price)}</td>
                        <td className="num" style={{ color: "var(--ok)" }}>{fmt(b.egp_margin)}</td>
                        <td className="num">{b.margin_pct}%</td>
                        <td className="num muted">{fmt(b.sold_window)}</td>
                        <td className="num">
                          {isStaged ? (
                            <input
                              type="number"
                              min="0"
                              className="input"
                              style={{ width: 70, textAlign: "center" }}
                              value={live}
                              onChange={(e) => setPts(b.product_id, e.target.value)}
                            />
                          ) : (
                            onList ? fmt(b.incentive_points) : "—"
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ))}

        {data && !data.error && data.groups.length === 0 && (
          <p className="muted">—</p>
        )}
      </div>
    </Shell>
  );
}
