"use client";

// Stocktaking (الجرد) — eStock-style physical inventory counts.
// Sessions list → count sheet (book qty vs physical count) → post adjustments.
// Posting (ضبط الأصناف) is manager/CEO only; counting is open to all staff.

import { useCallback, useEffect, useMemo, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

export default function StocktakingPage() {
  const { lang, branch, branches, user } = useUI();
  const L = (k) => t(lang, k);
  const canPost = user && (user.role === "ceo" || user.role === "manager");

  const [counts, setCounts] = useState(null); // sessions list
  const [openId, setOpenId] = useState(null); // opened session
  const [sheet, setSheet] = useState(null); // count sheet detail
  const [drafts, setDrafts] = useState({}); // line_id -> input value
  const [varianceOnly, setVarianceOnly] = useState(false);
  const [newType, setNewType] = useState("full");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  const loadList = useCallback(async () => {
    try {
      const r = await api.stockCounts(branch);
      setCounts(r.counts);
    } catch {
      setCounts([]);
    }
  }, [branch]);

  const loadSheet = useCallback(async (id) => {
    try {
      const r = await api.stockCountDetail(id);
      setSheet(r);
      setDrafts({});
    } catch {
      setSheet(null);
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    if (openId) loadSheet(openId);
    else setSheet(null);
  }, [openId, loadSheet]);

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");

  async function createCount() {
    // Counting is per-branch: use the selected branch, or the first real one.
    const branchId = Number(branch) || branches?.[0]?.branch_id || 1;
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.createStockCount({
        branch_id: branchId,
        count_type: newType,
        created_by: user?.employee_id ?? null,
      });
      await loadList();
      setOpenId(r.count_id);
    } catch (e) {
      setMsg({ kind: "danger", text: e?.message || String(e) });
    }
    setBusy(false);
  }

  async function saveDrafts() {
    const entries = Object.entries(drafts)
      .filter(([, v]) => v !== "")
      .map(([line_id, v]) => ({ line_id: Number(line_id), counted_qty: Number(v) }));
    if (!entries.length) return;
    setBusy(true);
    setMsg(null);
    try {
      await api.saveStockCountLines(openId, entries);
      await loadSheet(openId);
      setMsg({ kind: "ok", text: L("stk_saved") });
    } catch (e) {
      setMsg({ kind: "danger", text: e?.message || String(e) });
    }
    setBusy(false);
  }

  async function postCount() {
    if (!window.confirm(L("stk_post_confirm"))) return;
    setBusy(true);
    setMsg(null);
    try {
      // Unsaved inputs are part of the operator's intent — save then post.
      const entries = Object.entries(drafts)
        .filter(([, v]) => v !== "")
        .map(([line_id, v]) => ({ line_id: Number(line_id), counted_qty: Number(v) }));
      if (entries.length) await api.saveStockCountLines(openId, entries);
      await api.postStockCount(openId, user?.employee_id ?? null);
      await loadSheet(openId);
      await loadList();
      setMsg({ kind: "ok", text: L("stk_posted") });
    } catch (e) {
      setMsg({ kind: "danger", text: e?.message || String(e) });
    }
    setBusy(false);
  }

  async function cancelCount() {
    setBusy(true);
    try {
      await api.cancelStockCount(openId);
      await loadList();
      setOpenId(null);
    } catch (e) {
      setMsg({ kind: "danger", text: e?.message || String(e) });
    }
    setBusy(false);
  }

  const lines = useMemo(() => {
    if (!sheet) return [];
    if (!varianceOnly) return sheet.lines;
    return sheet.lines.filter((l) => l.variance !== null && l.variance !== 0);
  }, [sheet, varianceOnly]);

  const statusBadge = (s) =>
    s === "open" ? (
      <span className="badge warn">{L("stk_open")}</span>
    ) : s === "posted" ? (
      <span className="badge ok">{L("stk_status_posted")}</span>
    ) : (
      <span className="badge">{L("stk_status_cancelled")}</span>
    );

  // ---- Sessions list view --------------------------------------------------
  if (!openId) {
    return (
      <Shell titleKey="nav_stocktaking">
        <div className="card" style={{ marginBottom: 16, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <select className="input" value={newType} onChange={(e) => setNewType(e.target.value)}>
            <option value="full">{L("stk_full")}</option>
            <option value="periodic">{L("stk_periodic")}</option>
            <option value="partial">{L("stk_partial")}</option>
          </select>
          <button className="btn primary" disabled={busy} onClick={createCount}>
            ＋ {L("stk_new")}
          </button>
          {msg && <span className={`badge ${msg.kind === "ok" ? "ok" : "danger"}`}>{msg.text}</span>}
        </div>

        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <h3 className="section-title" style={{ padding: "12px 16px 0" }}>{L("stk_sessions")}</h3>
          <table className="tbl">
            <thead>
              <tr>
                <th>#</th>
                <th>{L("branch")}</th>
                <th>{L("stk_type")}</th>
                <th>{L("status")}</th>
                <th className="num">{L("stk_lines")}</th>
                <th className="num">{L("stk_counted_of")}</th>
                <th>{L("date")}</th>
              </tr>
            </thead>
            <tbody>
              {counts?.map((c) => (
                <tr key={c.count_id} style={{ cursor: "pointer" }} onClick={() => setOpenId(c.count_id)}>
                  <td>{c.count_id}</td>
                  <td>{c.branch}</td>
                  <td>{L(`stk_${c.count_type}`)}</td>
                  <td>{statusBadge(c.status)}</td>
                  <td className="num">{c.lines}</td>
                  <td className="num">{c.counted}/{c.lines}</td>
                  <td className="muted">{(c.created_at || "").slice(0, 16).replace("T", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {counts && counts.length === 0 && <p className="muted" style={{ padding: 16 }}>{L("stk_none_open")}</p>}
          {!counts && <p className="muted" style={{ padding: 16 }}>{L("loading")}</p>}
        </div>
      </Shell>
    );
  }

  // ---- Count sheet view ----------------------------------------------------
  const s = sheet?.summary;
  return (
    <Shell titleKey="nav_stocktaking">
      <div className="card" style={{ marginBottom: 16, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <button className="btn" onClick={() => setOpenId(null)}>←</button>
        <b>{L("stk_sheet")} #{openId}</b>
        {sheet && statusBadge(sheet.status)}
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={varianceOnly} onChange={(e) => setVarianceOnly(e.target.checked)} />
          {L("stk_variance_only")}
        </label>
        <span style={{ flex: 1 }} />
        <button className="btn" onClick={() => window.print()}>{L("stk_print")}</button>
        {sheet?.status === "open" && (
          <>
            <button className="btn" disabled={busy} onClick={saveDrafts}>{L("stk_save")}</button>
            <button
              className="btn primary"
              disabled={busy || !canPost}
              title={canPost ? "" : L("stk_manager_only")}
              onClick={postCount}
            >
              ✓ {L("stk_post")}
            </button>
            <button className="btn danger" disabled={busy} onClick={cancelCount}>{L("stk_cancel")}</button>
          </>
        )}
        {msg && <span className={`badge ${msg.kind === "ok" ? "ok" : "danger"}`}>{msg.text}</span>}
      </div>

      {s && (
        <div className="grid" style={{ gridTemplateColumns: "repeat(4, 1fr)", marginBottom: 16 }}>
          <div className="card">
            <div className="muted">{L("stk_counted_of")}</div>
            <b>{s.counted_lines}/{s.total_lines}</b>
          </div>
          <div className="card">
            <div className="muted">{L("stk_variance")}</div>
            <b>{s.variance_lines}</b>
          </div>
          <div className="card">
            <div className="muted" style={{ color: "var(--danger, #c00)" }}>{L("stk_shortage")}</div>
            <b>{fmt(s.shortage_qty)} · {fmt(s.shortage_value)}</b>
          </div>
          <div className="card">
            <div className="muted" style={{ color: "var(--ok, #080)" }}>{L("stk_overage")}</div>
            <b>{fmt(s.overage_qty)} · {fmt(s.overage_value)}</b>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>{L("product")}</th>
              <th>{L("exp_date")}</th>
              <th className="num">{L("stk_expected")}</th>
              <th className="num">{L("stk_counted")}</th>
              <th className="num">{L("stk_variance")}</th>
              <th className="num">{L("stk_variance_value")}</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((l) => {
              const draft = drafts[l.line_id];
              const shown = draft !== undefined ? draft : l.counted_qty ?? "";
              return (
                <tr key={l.line_id}>
                  <td>
                    {lang === "ar" ? l.name_ar : l.name_en || l.name_ar}
                    {l.shelf_location && <span className="muted"> · {l.shelf_location}</span>}
                  </td>
                  <td className="muted">{l.exp_date || "—"}</td>
                  <td className="num">{fmt(l.expected_qty)}</td>
                  <td className="num">
                    {sheet.status === "open" ? (
                      <input
                        className="input"
                        type="number"
                        min="0"
                        step="any"
                        value={shown}
                        onChange={(e) => setDrafts((d) => ({ ...d, [l.line_id]: e.target.value }))}
                        style={{ width: 90, textAlign: "end" }}
                      />
                    ) : (
                      fmt(l.counted_qty)
                    )}
                  </td>
                  <td className="num">
                    {l.variance === null ? (
                      <span className="muted">—</span>
                    ) : l.variance < 0 ? (
                      <span className="badge danger">{fmt(l.variance)}</span>
                    ) : l.variance > 0 ? (
                      <span className="badge ok">+{fmt(l.variance)}</span>
                    ) : (
                      <span className="muted">0</span>
                    )}
                  </td>
                  <td className="num muted">{l.variance_value === null ? "—" : fmt(l.variance_value)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {sheet && lines.length === 0 && <p className="muted" style={{ padding: 16 }}>{L("none")}</p>}
        {!sheet && <p className="muted" style={{ padding: 16 }}>{L("loading")}</p>}
      </div>
    </Shell>
  );
}
