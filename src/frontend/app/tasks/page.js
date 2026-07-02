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
  const [form, setForm] = useState({ title: "", details: "", assignee_id: "", due_date: "" });
  const [saving, setSaving] = useState(false);

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
      });
      setForm({ title: "", details: "", assignee_id: "", due_date: "" });
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

        <div className="table-wrapper">
          <table className="tbl">
            <thead>
              <tr>
                <th>{L("task_title")}</th>
                <th>{L("assignee")}</th>
                <th>{L("due_date_lbl")}</th>
                <th>{L("status")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {!tasks && (
                <tr><td colSpan="5" className="empty">{L("loading")}</td></tr>
              )}
              {tasks && tasks.length === 0 && (
                <tr><td colSpan="5" className="empty">{L("none")}</td></tr>
              )}
              {tasks?.map((task) => (
                <tr key={task.task_id} style={{ opacity: task.status === "done" ? 0.55 : 1 }}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{task.title}</div>
                    {task.details && <div className="muted" style={{ fontSize: 12 }}>{task.details}</div>}
                  </td>
                  <td>{task.assignee_name || L("unassigned")}</td>
                  <td>{task.due_date || "-"}</td>
                  <td>
                    <span className={`badge ${task.status === "done" ? "ok" : "warn"}`}>
                      {task.status === "done" ? L("mark_done") : L("pending_tasks")}
                    </span>
                  </td>
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
    </Shell>
  );
}
