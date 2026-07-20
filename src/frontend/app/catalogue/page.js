"use client";

import { useCallback, useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

// Catalogue correction review. Two jobs:
//  1. Enrichment — current eStock value vs the Titan / Drug-Eye proposal, per
//     field, approved or rejected individually or in bulk.
//  2. Duplicates — products entered twice, with the evidence (stock, sales,
//     last sale) needed to choose which copy to keep.
// eStock is never written here; approvals are staged for the reviewed export.
export default function CataloguePage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const fmt = (n) => Number(n || 0).toLocaleString("en-US");
  const nameOf = (p) => (lang === "ar" ? p.name_ar : p.name_en || p.name_ar);

  const [tab, setTab] = useState("enrich");
  const [onlyMissing, setOnlyMissing] = useState(true);
  const [enrich, setEnrich] = useState(null);
  const [dupes, setDupes] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [picked, setPicked] = useState({}); // "pid:field" -> diff
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === "enrich") {
        setEnrich(await api.catalogueEnrichment(onlyMissing, 300));
      } else {
        setDupes(await api.catalogueDuplicates(branch, 100));
      }
      setSummary(await api.catalogueDecisionSummary().catch(() => null));
    } catch {
      if (tab === "enrich") setEnrich({ error: true });
      else setDupes({ error: true });
    } finally {
      setLoading(false);
    }
  }, [tab, onlyMissing, branch]);

  useEffect(() => { load(); }, [load]);

  const keyOf = (pid, field) => `${pid}:${field}`;
  const toggle = (p, field, diff) =>
    setPicked((s) => {
      const k = keyOf(p.product_id, field);
      const next = { ...s };
      if (k in next) delete next[k];
      else next[k] = { product_id: p.product_id, field, new_value: String(diff.proposed),
                       old_value: diff.current == null ? null : String(diff.current),
                       source: diff.source };
      return next;
    });

  const decide = async (status, items) => {
    const list = (items || Object.values(picked)).map((i) => ({ ...i, status }));
    if (!list.length) return;
    setMsg("");
    try {
      const r = await api.catalogueDecide(list);
      setMsg(`${L("cat_saved")}: ✓${r.approved} ✕${r.rejected}`);
      setPicked({});
      await load();
    } catch {
      setMsg("✕");
    }
  };

  const pickedCount = Object.keys(picked).length;

  return (
    <Shell titleKey="nav_catalogue">
      <div className="page">
        <h2 className="section-title">{L("cat_title")}</h2>
        <p className="muted" style={{ marginTop: -4, marginBottom: 12, maxWidth: 760 }}>{L("cat_intro")}</p>

        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 14, flexWrap: "wrap" }}>
          <button className={`btn ${tab === "enrich" ? "primary" : ""}`} onClick={() => setTab("enrich")}>
            {L("cat_tab_enrich")}
          </button>
          <button className={`btn ${tab === "dupes" ? "primary" : ""}`} onClick={() => setTab("dupes")}>
            {L("cat_tab_dupes")}
          </button>
          {tab === "enrich" && (
            <label style={{ display: "inline-flex", gap: 6, alignItems: "center", fontSize: 13 }}>
              <input type="checkbox" checked={onlyMissing} onChange={(e) => setOnlyMissing(e.target.checked)} />
              {L("cat_only_missing")}
            </label>
          )}
          {summary && (
            <span className="muted" style={{ fontSize: 12, marginInlineStart: "auto" }}>
              ✓{fmt(summary.approved)} · ✕{fmt(summary.rejected)} · {L("cat_pending_export")}: {fmt(summary.pending_export)}
            </span>
          )}
        </div>

        {pickedCount > 0 && (
          <div className="card" style={{ marginBottom: 14, display: "flex", gap: 10, alignItems: "center",
                                          position: "sticky", top: 8, zIndex: 10 }}>
            <strong>{pickedCount}</strong>
            <button className="btn primary" onClick={() => decide("approved")}>{L("cat_approve_all")}</button>
            <button className="btn" onClick={() => decide("rejected")}>{L("cat_reject")}</button>
            {msg && <span className="badge ok">{msg}</span>}
          </div>
        )}
        {pickedCount === 0 && msg && <p className="badge ok" style={{ display: "inline-block", marginBottom: 10 }}>{msg}</p>}

        {loading && <p className="muted">{L("loading")}</p>}

        {/* ---------- Enrichment proposals ---------- */}
        {tab === "enrich" && enrich && !enrich.error && (
          <>
            <p className="muted" style={{ fontSize: 12 }}>
              {fmt(enrich.proposal_count)} · {Object.entries(enrich.by_field || {}).map(([k, v]) => `${k} ${v}`).join(" · ")}
            </p>
            {enrich.proposals.length === 0 && <p className="muted">{L("cat_no_proposals")}</p>}
            {enrich.proposals.map((p) => (
              <div className="card" style={{ marginBottom: 10 }} key={p.product_id}>
                <div style={{ display: "flex", gap: 8, alignItems: "baseline", marginBottom: 6 }}>
                  <strong>{nameOf(p)}</strong>
                  <span className="muted" style={{ fontSize: 12 }}>{p.code}</span>
                  {p.match_score != null && (
                    <span className="badge" style={{ fontSize: 10 }}>{p.match_method} {p.match_score}</span>
                  )}
                </div>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th style={{ width: 32 }}></th>
                      <th>{L("cat_field")}</th>
                      <th>{L("cat_current")}</th>
                      <th>{L("cat_proposed")}</th>
                      <th>{L("cat_source")}</th>
                      <th style={{ width: 150 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(p.diffs).map(([field, d]) => {
                      const k = keyOf(p.product_id, field);
                      return (
                        <tr key={field}>
                          <td><input type="checkbox" checked={k in picked} onChange={() => toggle(p, field, d)} /></td>
                          <td>{field}</td>
                          <td className="muted">{d.current === null || d.current === "" ? "—" : String(d.current).slice(0, 60)}</td>
                          <td style={{ color: "var(--ok)" }}>{String(d.proposed).slice(0, 90)}</td>
                          <td><span className="badge" style={{ fontSize: 10 }}>{d.source}</span></td>
                          <td>
                            <button className="btn" style={{ padding: "2px 8px" }}
                              onClick={() => decide("approved", [{ product_id: p.product_id, field,
                                new_value: String(d.proposed), old_value: d.current == null ? null : String(d.current),
                                source: d.source }])}>{L("cat_approve")}</button>
                            <button className="btn" style={{ padding: "2px 8px", marginInlineStart: 4 }}
                              onClick={() => decide("rejected", [{ product_id: p.product_id, field,
                                new_value: String(d.proposed), source: d.source }])}>{L("cat_reject")}</button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ))}
          </>
        )}

        {/* ---------- Duplicates ---------- */}
        {tab === "dupes" && dupes && !dupes.error && (
          <>
            <p className="muted" style={{ fontSize: 12 }}>
              {fmt(dupes.group_count)} · {L("cat_high_conf")}: {fmt(dupes.high_confidence)} ·
              {" "}{L("cat_review_conf")}: {fmt(dupes.needs_review)} · {L("cat_risk")}: {fmt(dupes.high_risk)}
            </p>
            <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>{L("cat_dupe_hint")}</p>
            {dupes.groups.map((g, i) => (
              <div className="card" style={{ marginBottom: 10 }} key={`${g.tier}-${g.key}-${i}`}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6, flexWrap: "wrap" }}>
                  <span className={`badge ${g.confidence === "high" ? "ok" : "warn"}`}>
                    {g.confidence === "high" ? L("cat_high_conf") : L("cat_review_conf")}
                  </span>
                  <span className={`badge ${g.risk === "high" ? "danger" : ""}`}>{L("cat_risk")}: {g.risk}</span>
                  <span className="muted" style={{ fontSize: 12 }}>{g.tier} · {g.size}</span>
                </div>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>{L("product")}</th>
                      <th className="num">{L("cat_onhand")}</th>
                      <th className="num">{L("cat_sold")}</th>
                      <th>{L("cat_last_sale")}</th>
                      <th className="num">{L("inc_sell")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.members.map((mem) => (
                      <tr key={mem.product_id} style={mem.product_id === g.suggested_survivor
                        ? { fontWeight: 700, background: "var(--hover, rgba(0,0,0,0.04))" } : undefined}>
                        <td>
                          {nameOf(mem)}
                          {mem.product_id === g.suggested_survivor && (
                            <span className="badge ok" style={{ marginInlineStart: 6, fontSize: 10 }}>{L("cat_survivor")}</span>
                          )}
                          <div className="muted" style={{ fontSize: 11 }}>#{mem.product_id} · {mem.code || "—"}</div>
                        </td>
                        <td className="num" style={mem.on_hand > 0 ? { color: "var(--danger)" } : undefined}>{fmt(mem.on_hand)}</td>
                        <td className="num">{fmt(mem.units_sold)}</td>
                        <td className="muted">{mem.last_sale ? String(mem.last_sale).slice(0, 10) : "—"}</td>
                        <td className="num">{fmt(mem.sell_price)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </>
        )}

        {((tab === "enrich" && enrich?.error) || (tab === "dupes" && dupes?.error)) && (
          <p className="badge danger">{L("offline")}</p>
        )}
      </div>
    </Shell>
  );
}
