"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

// Month boundaries as YYYY-MM-DD strings (local), for the quick presets.
function monthRange(offset = 0) {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const last = new Date(now.getFullYear(), now.getMonth() + offset + 1, 0);
  const iso = (d) => d.toISOString().slice(0, 10);
  return { start: iso(first), end: iso(last) };
}

// Sales-rep commission calculator (حاسبة عمولة مندوب البيع): total each rep's
// net sales in a period, apply a percentage (with per-rep overrides), then post
// the payout as an auditable run.
export default function CommissionsPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const fmt = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });
  const nameOf = (r) => (lang === "ar" ? r.name_ar : r.name_en || r.name_ar) || `#${r.employee_id}`;

  const thisMonth = monthRange(0);
  const [start, setStart] = useState(thisMonth.start);
  const [end, setEnd] = useState(thisMonth.end);
  const [rate, setRate] = useState(5);

  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  // employee_id -> overridden rate_pct (staged, applied on post)
  const [overrides, setOverrides] = useState({});
  const [posting, setPosting] = useState(false);
  const [msg, setMsg] = useState("");

  const [runs, setRuns] = useState([]);
  const [openRun, setOpenRun] = useState(null);

  const loadRuns = useCallback(async () => {
    try {
      const r = await api.commissionRuns(branch);
      setRuns(r.runs || []);
    } catch {
      setRuns([]);
    }
  }, [branch]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  const calc = useCallback(async () => {
    setLoading(true);
    setErr("");
    setMsg("");
    try {
      const r = await api.commissionPreview(start, end, branch, rate);
      setPreview(r);
      setOverrides({});
    } catch (e) {
      setErr(e?.message || L("offline"));
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }, [start, end, branch, rate]);

  const effectiveRate = (r) =>
    overrides[r.employee_id] !== undefined ? Number(overrides[r.employee_id]) : Number(r.rate_pct);
  const commissionOf = (r) => (Number(r.sales_value) * effectiveRate(r)) / 100;

  const totals = useMemo(() => {
    if (!preview) return { sales: 0, commission: 0 };
    return {
      sales: preview.reps.reduce((a, r) => a + Number(r.sales_value), 0),
      commission: preview.reps.reduce((a, r) => a + commissionOf(r), 0),
    };
  }, [preview, overrides]);

  const post = async () => {
    if (!preview) return;
    setPosting(true);
    setMsg("");
    try {
      const rep_rates = Object.entries(overrides)
        .filter(([, v]) => v !== "" && v !== undefined)
        .map(([employee_id, rate_pct]) => ({ employee_id: Number(employee_id), rate_pct: Number(rate_pct) }));
      await api.postCommissionRun({
        period_start: start,
        period_end: end,
        branch_id: branch || null,
        default_rate_pct: Number(rate),
        rep_rates,
      });
      setMsg(L("comm_posted_ok"));
      await loadRuns();
    } catch (e) {
      setErr(e?.message || L("offline"));
    } finally {
      setPosting(false);
    }
  };

  const view = async (runId) => {
    try {
      setOpenRun(await api.commissionRun(runId));
    } catch {
      /* ignore */
    }
  };

  const voidRun = async (runId) => {
    try {
      await api.voidCommissionRun(runId);
      setMsg(L("comm_voided_ok"));
      await loadRuns();
      if (openRun?.run_id === runId) setOpenRun(await api.commissionRun(runId));
    } catch {
      /* ignore */
    }
  };

  const setPreset = (r) => {
    setStart(r.start);
    setEnd(r.end);
  };

  return (
    <Shell titleKey="nav_commissions">
      <div className="page">
        <h2 className="section-title">{L("comm_title")}</h2>
        <p className="muted" style={{ marginTop: -4, marginBottom: 12, maxWidth: 720 }}>{L("comm_subtitle")}</p>

        {/* Controls */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div>
              <label className="muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{L("comm_period_start")}</label>
              <input className="input" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </div>
            <div>
              <label className="muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{L("comm_period_end")}</label>
              <input className="input" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
            </div>
            <div>
              <label className="muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{L("comm_default_rate")}</label>
              <input className="input" type="number" min="0" step="0.5" style={{ width: 100 }} value={rate} onChange={(e) => setRate(Math.max(0, Number(e.target.value) || 0))} />
            </div>
            <div style={{ display: "inline-flex", gap: 4 }}>
              <button className="btn" onClick={() => setPreset(monthRange(0))}>{L("comm_this_month")}</button>
              <button className="btn" onClick={() => setPreset(monthRange(-1))}>{L("comm_last_month")}</button>
            </div>
            <button className="btn primary" onClick={calc} disabled={loading}>
              {loading ? "…" : L("comm_calc")}
            </button>
          </div>
          {err && <p className="badge danger" style={{ marginTop: 8, display: "inline-block" }}>{err}</p>}
        </div>

        {/* Preview table */}
        {preview && (
          <div className="card" style={{ marginBottom: 16 }}>
            {preview.reps.length === 0 ? (
              <p className="muted">{L("comm_no_data")}</p>
            ) : (
              <>
                <p className="muted" style={{ fontSize: 12, marginTop: 0, marginBottom: 8 }}>{L("comm_rate_hint")}</p>
                <div className="table-wrapper" style={{ boxShadow: "none", border: "none", background: "transparent" }}>
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>{L("comm_rep")}</th>
                        <th className="num">{L("comm_sales_value")}</th>
                        <th className="num">{L("comm_bills")}</th>
                        <th className="num">{L("comm_rate")}</th>
                        <th className="num">{L("comm_commission")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.reps.map((r) => (
                        <tr key={r.employee_id}>
                          <td>{nameOf(r)}</td>
                          <td className="num">{fmt(r.sales_value)}</td>
                          <td className="num">{fmt(r.bills_count)}</td>
                          <td className="num">
                            <input
                              className="input"
                              type="number"
                              min="0"
                              step="0.5"
                              style={{ width: 70, textAlign: "center" }}
                              value={overrides[r.employee_id] !== undefined ? overrides[r.employee_id] : r.rate_pct}
                              onChange={(e) =>
                                setOverrides((o) => ({ ...o, [r.employee_id]: e.target.value === "" ? "" : Math.max(0, Number(e.target.value) || 0) }))
                              }
                            />
                          </td>
                          <td className="num" style={{ fontWeight: 600 }}>{fmt(commissionOf(r))}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr style={{ fontWeight: 700 }}>
                        <td>{L("comm_total_sales")} / {L("comm_total_commission")}</td>
                        <td className="num">{fmt(totals.sales)}</td>
                        <td></td>
                        <td></td>
                        <td className="num">{fmt(totals.commission)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
                  <button className="btn primary" onClick={post} disabled={posting}>
                    {posting ? "…" : L("comm_post")}
                  </button>
                  {msg && <span className="badge ok">{msg}</span>}
                </div>
              </>
            )}
          </div>
        )}

        {/* Posted runs */}
        <div className="card">
          <h3 className="section-title" style={{ marginTop: 0 }}>{L("comm_runs")}</h3>
          {runs.length === 0 ? (
            <p className="muted">—</p>
          ) : (
            <div className="table-wrapper" style={{ boxShadow: "none", border: "none", background: "transparent" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>{L("comm_period")}</th>
                    <th className="num">{L("comm_total_sales")}</th>
                    <th className="num">{L("comm_total_commission")}</th>
                    <th>{L("comm_status")}</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.run_id}>
                      <td>{r.run_id}</td>
                      <td>{r.period_start} → {r.period_end}</td>
                      <td className="num">{fmt(r.total_sales)}</td>
                      <td className="num" style={{ fontWeight: 600 }}>{fmt(r.total_commission)}</td>
                      <td>
                        <span className={`badge ${r.status === "void" ? "danger" : "ok"}`}>
                          {r.status === "void" ? L("comm_status_void") : L("comm_status_posted")}
                        </span>
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button className="btn" onClick={() => view(r.run_id)}>{L("comm_view")}</button>
                        {r.status !== "void" && (
                          <button className="btn" style={{ marginInlineStart: 6 }} onClick={() => voidRun(r.run_id)}>{L("comm_void_btn")}</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Run detail */}
        {openRun && (
          <div className="card" style={{ marginTop: 16 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
              <h3 className="section-title" style={{ margin: 0 }}>#{openRun.run_id} · {openRun.period_start} → {openRun.period_end}</h3>
              <button className="btn" style={{ marginInlineStart: "auto" }} onClick={() => setOpenRun(null)}>✕</button>
            </div>
            <div className="table-wrapper" style={{ boxShadow: "none", border: "none", background: "transparent" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{L("comm_rep")}</th>
                    <th className="num">{L("comm_sales_value")}</th>
                    <th className="num">{L("comm_bills")}</th>
                    <th className="num">{L("comm_rate")}</th>
                    <th className="num">{L("comm_commission")}</th>
                  </tr>
                </thead>
                <tbody>
                  {openRun.lines.map((ln) => (
                    <tr key={ln.line_id}>
                      <td>{nameOf(ln)}</td>
                      <td className="num">{fmt(ln.sales_value)}</td>
                      <td className="num">{fmt(ln.bills_count)}</td>
                      <td className="num">{fmt(ln.rate_pct)}</td>
                      <td className="num" style={{ fontWeight: 600 }}>{fmt(ln.commission)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Shell>
  );
}
