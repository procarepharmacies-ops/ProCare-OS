"use client";

// My tasks, phone-sized: tap to complete. Marking done sets absolute state
// server-side, so a repeated tap is harmless — which is also what will make
// this safe to queue offline later.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useUI } from "../../providers";
import { t } from "../../i18n";
import { api } from "../../api";

// Same buckets as the desktop tasks screen. Computed on the device clock, so a
// phone with the wrong date buckets wrong — acceptable for an ordering hint.
function group(tasks) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const weekEnd = new Date(today);
  weekEnd.setDate(weekEnd.getDate() + 7);
  const buckets = { overdue: [], today: [], week: [], later: [] };
  for (const task of tasks) {
    const due = task.due_date ? new Date(task.due_date + "T00:00:00") : null;
    if (task.status === "pending" && due && due < today) buckets.overdue.push(task);
    else if (due && +due === +today) buckets.today.push(task);
    else if (due && due <= weekEnd) buckets.week.push(task);
    else buckets.later.push(task);
  }
  return buckets;
}

export default function RXTasksPage() {
  const { lang, branch, user } = useUI();
  const L = (k) => t(lang, k);
  const [tasks, setTasks] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    try {
      const params = { status: "pending" };
      if (branch) params.branch_id = branch;
      if (user?.employee_id) params.assignee_id = user.employee_id;
      const r = await api.get("/tasks", params);
      setTasks(r.tasks || []);
    } catch {
      setTasks([]);
    }
  }, [branch, user]);

  useEffect(() => {
    load();
  }, [load]);

  async function complete(task) {
    setBusy(task.task_id);
    try {
      await api.post(`/tasks/${task.task_id}/status`, { status: "done" });
      await load();
    } catch {
      /* leave it pending; the list reload will show the truth */
    }
    setBusy(null);
  }

  const buckets = useMemo(() => group(tasks || []), [tasks]);
  const SECTIONS = [
    ["overdue", "tasks_overdue", "danger"],
    ["today", "tasks_today", "warn"],
    ["week", "tasks_week", ""],
    ["later", "tasks_later", ""],
  ];

  if (tasks === null) return <div className="rx-muted">{L("loading")}</div>;
  if (!tasks.length) return <div className="rx-card rx-muted">{L("rx_no_tasks")}</div>;

  return (
    <div>
      {SECTIONS.map(([key, labelKey, tone]) =>
        buckets[key].length ? (
          <div className="rx-card" key={key}>
            <span className={`rx-chip ${tone}`}>
              {L(labelKey)} · {buckets[key].length}
            </span>
            {buckets[key].map((task) => (
              <div className="rx-list-item" key={task.task_id}>
                <div style={{ flex: 1 }}>
                  <div>{task.title}</div>
                  {task.due_date && <div className="rx-muted">{task.due_date}</div>}
                </div>
                <button
                  className="rx-btn primary"
                  style={{ width: 92 }}
                  disabled={busy === task.task_id}
                  onClick={() => complete(task)}
                >
                  ✓
                </button>
              </div>
            ))}
          </div>
        ) : null
      )}
    </div>
  );
}
