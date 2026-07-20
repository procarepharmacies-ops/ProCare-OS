"use client";

import { useCallback, useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

export default function TasksPage() {
  const { lang, branch, user } = useUI();
  const L = (k) => t(lang, k);
  const canAssign = user?.role === "ceo" || user?.role === "manager";

  const [tasks, setTasks] = useState(null);
  const [summary, setSummary] = useState({ pending: 0, done_today: 0 });
  const [assignees, setAssignees] = useState([]);
  const [mineOnly, setMineOnly] = useState(!canAssign);
  const [form, setForm] = useState({ title: "", details: "", assignee_id: "", due_date: "", priority: "normal", category: "general" });
  const [saving, setSaving] = useState(false);

  const PRIORITY_CLASS = { high: "danger", normal: "warn", low: "" };

  const load = useCallback(async () => {
    try {
      const r = await api.get("/tasks", {
        branch_id: branch || undefined,
        assignee_id: mineOnly && user ? user.employee_id : undefined,
      });
      setTasks(r.tasks);
      setSummary(r.summary);
    } catch {
      setTasks([]);
    }
  }, [branch, mineOnly, user]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (canAssign) api.get("/tasks/assignees").then((r) => setAssignees(r.assignees)).catch(() => {});
  }, [canAssign]);

  async function addTask(e) {
    e.preventDefault();
    if (!form.title.trim() || saving) return;
    setSaving(true);
    try {
      await api.post("/tasks", {
        title: form.title,
        details: form.details || null,
        assignee_id: form.assignee_id ? Number(form.assignee_id) : null,
        branch_id: branch || null,
        due_date: form.due_date || null,
        priority: form.priority,
        category: form.category,
      });
      setForm({ title: "", details: "", assignee_id: "", due_date: "", priority: "normal", category: "general" });
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function toggle(task) {
    await api.post(`/tasks/${task.task_id}/status`, { status: task.status === "done" ? "pending" : "done" });
    await load();
  }

  return (
    <Shell titleKey="nav_tasks">
      <div className="page">
        <div className="kpi-row">
          <div className="kpi-box">
            <div className="kpi-value">{summary.pending}</div>
            <div className="kpi-label">{L("pending_tasks")}</div>
          </div>
          <div className="kpi-box">
            <div className="kpi-value">{summary.done_today}</div>
            <div className="kpi-label">{L("done_today")}</div>
          </div>
        </div>

        {canAssign && (
          <form onSubmit={addTask} className="card" style={{ marginBottom: 16, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "end" }}>
            <label style={{ flex: "2 1 200px", display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              <span className="muted">{L("task_title")}</span>
              <input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </label>
            <label style={{ flex: "2 1 200px", display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              <span className="muted">{L("task_details")}</span>
              <input className="input" value={form.details} onChange={(e) => setForm({ ...form, details: e.target.value })} />
            </label>
            <label style={{ flex: "1 1 150px", display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              <span className="muted">{L("assignee")}</span>
              <select className="select" value={form.assignee_id} onChange={(e) => setForm({ ...form, assignee_id: e.target.value })}>
                <option value="">{L("unassigned")}</option>
                {assignees.map((a) => (
                  <option key={a.employee_id} value={a.employee_id}>
                    {lang === "ar" ? a.name_ar : a.name_en || a.name_ar}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ flex: "1 1 140px", display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              <span className="muted">{L("due_date_lbl")}</span>
              <input className="input" type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
            </label>
            <label style={{ flex: "1 1 120px", display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              <span className="muted">{L("priority")}</span>
              <select className="select" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                <option value="high">{L("priority_high")}</option>
                <option value="normal">{L("priority_normal")}</option>
                <option value="low">{L("priority_low")}</option>
              </select>
            </label>
            <label style={{ flex: "1 1 130px", display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
              <span className="muted">{L("category")}</span>
              <select className="select" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {["general", "opening", "closing", "inventory", "ordering", "cleaning", "approval"].map((c) => (
                  <option key={c} value={c}>{L(`cat_${c}`)}</option>
                ))}
              </select>
            </label>
            <button className="btn primary" type="submit" disabled={!form.title.trim() || saving}>
              {L("add_task")}
            </button>
          </form>
        )}

        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 13 }}>
            <input type="checkbox" checked={mineOnly} onChange={(e) => setMineOnly(e.target.checked)} /> {L("my_tasks")}
          </label>
        </div>

        {!tasks && <p className="muted">{L("loading")}</p>}
        {tasks && tasks.length === 0 && <p className="empty">{L("none")}</p>}
        {tasks && tasks.length > 0 && groupTasks(tasks).map((grp) => (
          grp.items.length === 0 ? null : (
            <div key={grp.key} style={{ marginBottom: 18 }}>
              <h3 className="section-title" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                {L(grp.key)}
                <span className="badge">{grp.items.length}</span>
              </h3>
              <div className="table-wrapper">
                <table className="tbl">
                  <tbody>
                    {grp.items.map((task) => (
                      <tr key={task.task_id} style={{ opacity: task.status === "done" ? 0.5 : 1 }}>
                        <td style={{ width: 8, background: task.status === "pending" && task.priority === "high" ? "var(--danger)" : "transparent" }} />
                        <td>
                          <div style={{ fontWeight: 600, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                            {task.priority !== "normal" && (
                              <span className={`badge ${PRIORITY_CLASS[task.priority] || ""}`} style={{ fontSize: 10 }}>
                                {L(`priority_${task.priority}`)}
                              </span>
                            )}
                            {task.category && task.category !== "general" && (
                              <span className="badge" style={{ fontSize: 10 }}>{L(`cat_${task.category}`)}</span>
                            )}
                            <span>{task.title}</span>
                          </div>
                          {task.details && <div className="muted" style={{ fontSize: 12 }}>{task.details}</div>}
                        </td>
                        <td className="muted" style={{ whiteSpace: "nowrap" }}>{task.assignee_name || L("unassigned")}</td>
                        <td className="muted" style={{ whiteSpace: "nowrap" }}>{task.due_date || "-"}</td>
                        <td>
                          <button className="btn" onClick={() => toggle(task)}>
                            {task.status === "done" ? L("reopen") : L("mark_done")}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )
        ))}
      </div>
    </Shell>
  );
}

// Group tasks into Overdue / Today / This week / Later buckets (pending
// overdue/today first — that's the daily plan the staff work from).
function groupTasks(tasks) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const weekEnd = new Date(today);
  weekEnd.setDate(weekEnd.getDate() + 7);
  const buckets = { overdue: [], today: [], week: [], later: [] };
  for (const t of tasks) {
    const due = t.due_date ? new Date(t.due_date + "T00:00:00") : null;
    if (t.status === "pending" && due && due < today) buckets.overdue.push(t);
    else if (due && +due === +today) buckets.today.push(t);
    else if (due && due <= weekEnd) buckets.week.push(t);
    else buckets.later.push(t);
  }
  return [
    { key: "tasks_overdue", items: buckets.overdue },
    { key: "tasks_today", items: buckets.today },
    { key: "tasks_week", items: buckets.week },
    { key: "tasks_later", items: buckets.later },
  ];
}
