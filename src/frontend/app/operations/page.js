"use client";

/* Operations Center — the pharmacy's daily command screen.
   Two jobs, one glance: (1) run today's task board (assign/complete), and
   (2) read staff performance. Built on the fast, always-live endpoints
   (/tasks, /dashboard/summary, /insights/productivity, /agents/status) so it
   never waits on the heavy analytics. Fully bilingual + RTL via the shared
   design system in globals.css. */

import { useEffect, useState, useCallback } from "react";
import { useUI } from "../providers";
import { t } from "../i18n";
import { apiFetch } from "../api";
import Icon from "../components/icons";

const money = (n) => (Number(n) || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });

// Group a task by its due date relative to the business "today" (YYYY-MM-DD).
function bucketOf(task, today) {
  if (task.status === "done") return "done";
  if (!task.due_date) return "upcoming";
  if (task.due_date < today) return "overdue";
  if (task.due_date === today) return "today";
  return "upcoming";
}

export default function OperationsPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);

  const [loading, setLoading] = useState(true);
  const [kpis, setKpis] = useState(null);
  const [today, setToday] = useState("");
  const [tasks, setTasks] = useState([]);
  const [perf, setPerf] = useState([]);
  const [agents, setAgents] = useState([]);
  const [team, setTeam] = useState(null);
  const [busyTask, setBusyTask] = useState(null);

  const bq = branch ? `?branch_id=${branch}` : "";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [summary, tasksRes, prod, agentsRes, teamRes] = await Promise.all([
        apiFetch(`/api/dashboard/summary${bq}`).catch(() => null),
        apiFetch(`/api/tasks${bq}`).catch(() => ({ tasks: [] })),
        apiFetch(`/api/insights/productivity`).catch(() => ({ employees: [] })),
        apiFetch(`/api/agents/status`).catch(() => ({ agents: [] })),
        apiFetch(`/api/employees/summary`).catch(() => null),
      ]);
      setKpis(summary?.kpis || null);
      setToday(summary?.as_of || "");
      setTasks(tasksRes?.tasks || []);
      setPerf((prod?.employees || []).filter((e) => e.bills > 0));
      setAgents(agentsRes?.agents || []);
      setTeam(teamRes || null);
    } finally {
      setLoading(false);
    }
  }, [bq]);

  useEffect(() => {
    load();
  }, [load]);

  async function setStatus(task, status) {
    setBusyTask(task.task_id);
    try {
      await apiFetch(`/api/tasks/${task.task_id}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      setTasks((ts) => ts.map((x) => (x.task_id === task.task_id ? { ...x, status } : x)));
    } catch (e) {
      // Fail-soft: surface, don't crash the board.
      console.error("task status update failed", e);
    } finally {
      setBusyTask(null);
    }
  }

  const groups = { overdue: [], today: [], upcoming: [], done: [] };
  for (const tk of tasks) groups[bucketOf(tk, today)].push(tk);

  const openCount = groups.overdue.length + groups.today.length + groups.upcoming.length;
  const maxRev = Math.max(1, ...perf.map((e) => e.revenue || 0));

  const kpiCards = [
    { label: L("ops_open_tasks"), value: openCount, ico: "clipboard", tone: "" },
    { label: L("ops_overdue"), value: groups.overdue.length, ico: "bell", tone: groups.overdue.length ? "danger" : "" },
    { label: L("ops_sales_today"), value: kpis ? money(kpis.sales_today) : "—", ico: "receipt", tone: "" },
    { label: L("ops_bills_today"), value: kpis ? kpis.bills_today : "—", ico: "coins", tone: "" },
    { label: L("ops_low_stock"), value: kpis ? kpis.low_stock : "—", ico: "pill", tone: kpis?.low_stock ? "warn" : "" },
    { label: L("ops_expiring"), value: kpis ? kpis.expiring_30 : "—", ico: "sheet", tone: kpis?.expiring_30 ? "warn" : "" },
    { label: L("ops_team_online"), value: team ? team.active_employees : "—", ico: "badge", tone: "" },
  ];

  return (
    <div className="page">
      <div className="topbar">
        <div>
          <h1 className="page-title">{L("ops_title")}</h1>
          <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>{L("ops_subtitle")}</div>
        </div>
        <div className="controls">
          {today && <span className="badge">{today}</span>}
          <button className="btn" onClick={load} disabled={loading}>
            <Icon name="chart" size={16} /> {L("ops_refresh")}
          </button>
        </div>
      </div>

      {/* Today's pulse */}
      <div className="kpi-row">
        {kpiCards.map((c, i) => (
          <div className="kpi-box" key={i}>
            <div className={`kpi-ico${c.tone ? " " + c.tone : ""}`} style={tone(c.tone)}>
              <Icon name={c.ico} size={18} />
            </div>
            <div className="kpi-label">{c.label}</div>
            <div className="kpi-value">{loading ? <span className="shimmer" style={{ display: "inline-block", width: 60, height: 24 }} /> : c.value}</div>
          </div>
        ))}
      </div>

      {/* Agent fleet strip */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon name="sparkle" size={16} /> {L("ops_fleet")}
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {agents.map((a) => (
            <div key={a.id} title={a.detail} style={agentChip(a.online)}>
              <span className="dot" style={{ background: a.online ? "var(--ok)" : "var(--danger)", animation: a.online ? undefined : "none" }} />
              <span style={{ fontWeight: 600 }}>{lang === "ar" ? a.label_ar : a.label}</span>
              <span className="muted" style={{ fontSize: 11.5 }}>· {a.online ? L("ops_online") : L("ops_offline")}</span>
            </div>
          ))}
          {agents.length === 0 && <span className="muted">—</span>}
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1.15fr 1fr" }}>
        {/* Task board */}
        <div className="card">
          <div className="section-title">{L("ops_tasks_board")}</div>
          {["overdue", "today", "upcoming", "done"].map((g) => (
            <TaskGroup
              key={g}
              title={L("ops_grp_" + g)}
              tone={g === "overdue" ? "danger" : g === "today" ? "ok" : ""}
              tasks={groups[g]}
              lang={lang}
              L={L}
              busyTask={busyTask}
              onDone={(tk) => setStatus(tk, "done")}
              onReopen={(tk) => setStatus(tk, "pending")}
              loading={loading}
            />
          ))}
        </div>

        {/* Performance leaderboard */}
        <div className="card">
          <div className="section-title">{L("ops_performance")}</div>
          <div className="table-wrapper" style={{ boxShadow: "none", border: "none", background: "transparent" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>{L("ops_emp")}</th>
                  <th className="num">{L("ops_bills")}</th>
                  <th className="num">{L("ops_revenue")}</th>
                  <th className="num">{L("ops_avg_bill")}</th>
                  <th className="num">{L("ops_peak_hour")}</th>
                </tr>
              </thead>
              <tbody>
                {perf.map((e, i) => (
                  <tr key={e.employee_id ?? i}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{e.name && e.name !== "—" ? e.name : L("ops_unassigned")}</div>
                      <div style={revBar(e.revenue, maxRev)} />
                    </td>
                    <td className="num">{e.bills}</td>
                    <td className="num">{money(e.revenue)}</td>
                    <td className="num">{money(e.avg_bill)}</td>
                    <td className="num">{String(e.peak_hour).padStart(2, "0")}:00</td>
                  </tr>
                ))}
                {perf.length === 0 && (
                  <tr><td colSpan={5} className="empty">{loading ? "…" : "—"}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function TaskGroup({ title, tone, tasks, lang, L, busyTask, onDone, onReopen, loading }) {
  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span className={`badge${tone ? " " + tone : ""}`}>{title}</span>
        <span className="muted" style={{ fontSize: 12 }}>{tasks.length}</span>
      </div>
      {tasks.length === 0 && !loading && (
        <div className="muted" style={{ fontSize: 13, padding: "2px 2px 8px" }}>{L("ops_no_tasks")}</div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {tasks.map((tk) => (
          <div key={tk.task_id} style={taskRow}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 14, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{tk.title}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <span>{tk.assignee_name || L("ops_unassigned")}</span>
                {tk.priority && tk.priority !== "normal" && (
                  <span className={`badge ${tk.priority === "high" ? "danger" : "warn"}`} style={{ fontSize: 10 }}>{tk.priority}</span>
                )}
                {tk.category && <span className="badge" style={{ fontSize: 10 }}>{tk.category}</span>}
              </div>
            </div>
            {tk.status === "done" ? (
              <button className="btn" style={{ fontSize: 12, padding: "5px 10px" }} disabled={busyTask === tk.task_id} onClick={() => onReopen(tk)}>
                {L("ops_reopen")}
              </button>
            ) : (
              <button className="btn primary" style={{ fontSize: 12, padding: "5px 10px" }} disabled={busyTask === tk.task_id} onClick={() => onDone(tk)}>
                ✓ {L("ops_mark_done")}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// --- inline style helpers (kept local; the heavy lifting is in globals.css) --
function tone(t) {
  if (t === "danger") return { color: "var(--danger)", background: "color-mix(in srgb, var(--danger) 12%, transparent)" };
  if (t === "warn") return { color: "var(--warning)", background: "color-mix(in srgb, var(--warning) 12%, transparent)" };
  return {};
}
const taskRow = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 10,
  padding: "10px 12px",
  borderRadius: 12,
  border: "1px solid var(--border)",
  background: "color-mix(in srgb, var(--surface-solid) 40%, transparent)",
};
function agentChip(online) {
  return {
    display: "flex",
    alignItems: "center",
    gap: 7,
    padding: "7px 12px",
    borderRadius: 999,
    fontSize: 13,
    border: `1px solid ${online ? "color-mix(in srgb, var(--ok) 45%, transparent)" : "var(--border)"}`,
    background: "var(--surface)",
  };
}
function revBar(rev, max) {
  return {
    marginTop: 5,
    height: 4,
    width: `${Math.max(3, ((rev || 0) / max) * 100)}%`,
    borderRadius: 999,
    background: "linear-gradient(90deg, var(--primary), var(--primary-2))",
  };
}
