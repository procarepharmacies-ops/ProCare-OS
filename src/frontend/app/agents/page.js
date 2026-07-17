"use client";

import { useEffect, useState } from "react";
import { useUI } from "../providers";
import { t } from "../i18n";
import { apiFetch } from "../api";
import Icon from "../components/icons";

export default function AgentsPage() {
  const { lang, online } = useUI();
  const L = (k) => t(lang, k);
  const [status, setStatus] = useState({ agents: [] });
  const [runs, setRuns] = useState([]);
  const [task, setTask] = useState("");
  const [selectedAgent, setSelectedAgent] = useState("");
  const [dispatching, setDispatching] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [isDryRun, setIsDryRun] = useState(true);

  useEffect(() => {
    fetchStatus();
    fetchRuns();
  }, []);

  const fetchStatus = async () => {
    try {
      const data = await apiFetch("/api/agents/status");
      setStatus(data);
      if (data.agents.length > 0 && !selectedAgent) {
        setSelectedAgent(data.agents[0].id);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchRuns = async () => {
    try {
      const data = await apiFetch("/api/agents/runs");
      setRuns(data.runs || []);
    } catch (e) {
      console.error(e);
    }
  };

  const dispatch = async () => {
    if (!task.trim() || !selectedAgent) return;
    setDispatching(true);
    try {
      const res = await apiFetch(`/api/agents/${selectedAgent}/dispatch`, {
        method: "POST",
        body: JSON.stringify({
          task,
          confirm: !isDryRun,
          dry_run: isDryRun
        })
      });
      setLastResult(res);
      setTask("");
      fetchRuns();
    } catch (e) {
      alert("Dispatch failed: " + e.message);
    }
    setDispatching(false);
  };

  if (!online) return <div className="card pad tc">{L("offline")}</div>;

  return (
    <div className="pad-lg">
      <h2 style={{ marginBottom: 20 }}>{L("nav_agents")} — ProCare Agentic OS</h2>
      
      <div className="grid">
        <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
          <div className="card pad">
            <h3>Agent Fleet</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 15 }}>
              {status.agents.map((a) => (
                <div key={a.id} className="card pad" style={{ borderLeft: `4px solid ${a.online ? "var(--color-green)" : "var(--color-red)"}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <h4 style={{ margin: 0 }}>{lang === "ar" ? a.label_ar : a.label}</h4>
                      <small className="kpi-sub">{a.kind} • {a.detail}</small>
                    </div>
                    <div>
                      {a.online ? <span className="badge green">Online</span> : <span className="badge red">Offline</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card pad">
            <h3>Dispatch Task</h3>
            <div style={{ marginTop: 15 }}>
              <select 
                className="input" 
                value={selectedAgent} 
                onChange={(e) => setSelectedAgent(e.target.value)}
                style={{ width: "100%", marginBottom: 10 }}
              >
                {status.agents.map(a => (
                  <option key={a.id} value={a.id} disabled={!a.dispatchable}>
                    {lang === "ar" ? a.label_ar : a.label} {!a.dispatchable && "(Unavailable)"}
                  </option>
                ))}
              </select>
              <textarea 
                className="input"
                placeholder="Enter task description or prompt for the agent..."
                value={task}
                onChange={(e) => setTask(e.target.value)}
                rows={4}
                style={{ width: "100%", marginBottom: 10, resize: "vertical" }}
              />
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 15 }}>
                <input 
                  type="checkbox" 
                  id="dry_run" 
                  checked={isDryRun} 
                  onChange={(e) => setIsDryRun(e.target.checked)} 
                />
                <label htmlFor="dry_run">Dry Run (Do not execute side effects)</label>
              </div>
              <button className="btn primary" onClick={dispatch} disabled={dispatching || !task.trim()}>
                {dispatching ? "Dispatching..." : "Dispatch Task"}
              </button>
            </div>
            
            {lastResult && (
              <div style={{ marginTop: 20, padding: 15, background: "var(--color-bg-alt)", borderRadius: 8 }}>
                <h4>Result ({lastResult.status}) <small>{lastResult.latency_ms}ms</small></h4>
                <pre style={{ whiteSpace: "pre-wrap", maxHeight: 300, overflowY: "auto", fontSize: 13, marginTop: 10 }}>
                  {lastResult.output}
                </pre>
              </div>
            )}
          </div>
        </div>
        
        <div>
          <div className="card pad">
            <h3>Recent Runs</h3>
            <div style={{ marginTop: 15, display: "flex", flexDirection: "column", gap: 10 }}>
              {runs.map((r) => (
                <div key={r.run_id} style={{ borderBottom: "1px solid var(--color-border)", paddingBottom: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                    <strong>{r.agent}</strong>
                    <span className={`badge ${r.status === 'done' ? 'green' : r.status === 'error' ? 'red' : 'gray'}`}>
                      {r.status}
                    </span>
                  </div>
                  <div style={{ fontSize: 13, color: "var(--color-text-sub)" }}>{r.task}</div>
                  <div style={{ fontSize: 12, marginTop: 5 }}>{new Date(r.created_at).toLocaleString()}</div>
                </div>
              ))}
              {runs.length === 0 && <div className="tc kpi-sub">No recent runs</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
