"use client";

import { useEffect, useState } from "react";
import { useUI } from "../providers";
import { t } from "../i18n";
import { apiFetch } from "../api";
import Icon from "../components/icons";

export default function CockpitPage() {
  const { lang, online } = useUI();
  const L = (k) => t(lang, k);
  
  const [agents, setAgents] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [runningBrief, setRunningBrief] = useState(false);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const [agentsRes, tasksRes, alertsRes] = await Promise.all([
        apiFetch("/api/agents/status"),
        apiFetch("/api/tasks/list?status=pending"),
        apiFetch("/api/alerts")
      ]);
      setAgents(agentsRes.agents || []);
      setTasks(tasksRes.tasks || []);
      setAlerts(alertsRes.alerts || []);
    } catch (e) {
      console.error("Failed to load cockpit data", e);
    }
  };

  const runMorningBrief = async () => {
    setRunningBrief(true);
    // Dispatch to Claude or Gemini to summarize the morning status
    const dispatchable = agents.find(a => a.dispatchable);
    if (dispatchable) {
      try {
        await apiFetch(`/api/agents/${dispatchable.id}/dispatch`, {
          method: "POST",
          body: JSON.stringify({
            task: "Generate a morning brief for the pharmacy owner based on current pending tasks and active alerts.",
            confirm: true
          })
        });
        alert("Morning brief dispatched to " + dispatchable.label);
      } catch (e) {
        alert("Failed to run morning brief: " + e.message);
      }
    } else {
      alert("No dispatchable agents available for the morning brief.");
    }
    setRunningBrief(false);
  };

  if (!online) return <div className="card pad tc">{L("offline")}</div>;

  return (
    <div className="pad-lg">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0 }}>{L("nav_cockpit")} — Operations Center</h2>
        <button className="btn primary" onClick={runMorningBrief} disabled={runningBrief}>
          <Icon name="sparkle" /> {runningBrief ? "Running..." : "Run Morning Brief"}
        </button>
      </div>

      {/* Agent Fleet Strip */}
      <div className="card pad" style={{ marginBottom: 20, display: "flex", gap: 15, overflowX: "auto" }}>
        {agents.map((a) => (
          <div key={a.id} style={{ minWidth: 200, display: "flex", alignItems: "center", gap: 10, padding: 10, borderRadius: 8, background: "var(--color-bg-alt)", border: `1px solid ${a.online ? "var(--color-green)" : "var(--color-red)"}` }}>
            <div style={{ width: 10, height: 10, borderRadius: "50%", background: a.online ? "var(--color-green)" : "var(--color-red)" }} />
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{lang === "ar" ? a.label_ar : a.label}</div>
              <div style={{ fontSize: 12, color: "var(--color-text-sub)" }}>{a.online ? "Online" : "Offline"}</div>
            </div>
          </div>
        ))}
        {agents.length === 0 && <div className="kpi-sub">Loading agents...</div>}
      </div>

      <div className="grid">
        {/* Pending Tasks */}
        <div className="card pad">
          <h3>Pending Operations</h3>
          <div style={{ marginTop: 15, display: "flex", flexDirection: "column", gap: 10 }}>
            {tasks.slice(0, 10).map((t) => (
              <div key={t.task_id} style={{ display: "flex", justifyContent: "space-between", paddingBottom: 10, borderBottom: "1px solid var(--color-border)" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{t.title}</div>
                  <div style={{ fontSize: 12, color: "var(--color-text-sub)" }}>Assignee: {t.assignee_id || t.assigned_agent || "Unassigned"}</div>
                </div>
                <span className={`badge ${t.priority === 'high' ? 'red' : 'gray'}`}>{t.priority}</span>
              </div>
            ))}
            {tasks.length === 0 && <div className="tc kpi-sub">No pending tasks</div>}
          </div>
        </div>

        {/* Alerts */}
        <div className="card pad">
          <h3>Active Alerts</h3>
          <div style={{ marginTop: 15, display: "flex", flexDirection: "column", gap: 10 }}>
            {alerts.slice(0, 10).map((a, i) => (
              <div key={i} style={{ display: "flex", gap: 10, paddingBottom: 10, borderBottom: "1px solid var(--color-border)" }}>
                <Icon name="bell" color="var(--color-red)" />
                <div>
                  <div style={{ fontWeight: 600 }}>{a.title}</div>
                  <div style={{ fontSize: 12, color: "var(--color-text-sub)" }}>{a.message}</div>
                </div>
              </div>
            ))}
            {alerts.length === 0 && <div className="tc kpi-sub">No active alerts</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
