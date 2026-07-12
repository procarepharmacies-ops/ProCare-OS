"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

export default function SettingsPage() {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  const [health, setHealth] = useState(null);
  const [branches, setBranches] = useState([]);
  const [syncStatus, setSyncStatus] = useState(null);
  const [backups, setBackups] = useState(null);
  const [backupMsg, setBackupMsg] = useState(null);

  useEffect(() => {
    api.backupList().then(setBackups).catch(() => {});
  }, [backupMsg]);

  async function takeBackup() {
    setBackupMsg(null);
    try {
      const r = await api.backupNow();
      setBackupMsg(r.ok ? { kind: "ok", text: t(lang, "backup_done") } : { kind: "danger", text: r.error });
    } catch (e) {
      setBackupMsg({ kind: "danger", text: e?.message || String(e) });
    }
  }

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [h, b, s] = await Promise.all([
          api.health(),
          api.branches(),
          api.get("/sync/status"),
        ]);
        if (alive) {
          setHealth(h);
          setBranches(b.branches || []);
          setSyncStatus(s);
        }
      } catch {
        if (alive) setHealth({ error: true });
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (!health) return <Shell titleKey="nav_settings"><div className="page">{L("loading")}</div></Shell>;
  if (health.error) return <Shell titleKey="nav_settings"><div className="page badge danger">{L("offline")}</div></Shell>;

  const yn = (v) => (v ? L("yes") : L("no"));

  return (
    <Shell titleKey="nav_settings">
      <div className="page">
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 className="section-title">💾 {L("backup_now")}</h3>
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <button className="btn primary" onClick={takeBackup}>{L("backup_now")}</button>
            <span className="muted">
              {L("backup_last")}: {backups?.last_backup_at ? backups.last_backup_at.slice(0, 16).replace("T", " ") : "—"}
              {backups?.backups?.length ? ` · ${backups.backups.length} ${L("none") === "لا يوجد" ? "نسخة" : "backups"}` : ""}
            </span>
            {backupMsg && <span className={`badge ${backupMsg.kind === "ok" ? "ok" : "danger"}`}>{backupMsg.text}</span>}
          </div>
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3 className="section-title">{L("branches_stores")}</h3>
          <table className="tbl" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th>{L("branch")}</th>
                <th>{L("pilot_branch")}</th>
              </tr>
            </thead>
            <tbody>
              {branches.length === 0 ? (
                <tr>
                  <td colSpan="2" className="empty">{L("none")}</td>
                </tr>
              ) : (
                branches.map((b) => (
                  <tr key={b.branch_id || b.code}>
                    <td>{lang === "ar" ? b.name_ar : b.name_en}</td>
                    <td>{b.pilot ? "★" : "-"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div className="card">
            <h3 className="section-title">{L("system_status")}</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 14 }}>
              <div><strong>{L("data_source")}:</strong> {health.procare_db}</div>
              <div><strong>{L("config_source")}:</strong> {health.config_source}</div>
              <div><strong>{L("using_example")}:</strong> {health.using_example_config ? L("yes") : L("no")}</div>
              <div><strong>{L("ai_engine")}:</strong> {health.ai_assistant?.engine}</div>
              <div><strong>{L("ai_model")}:</strong> {health.ai_assistant?.model}</div>
            </div>
          </div>

          <div className="card">
            <h3 className="section-title">{L("sync_status")}</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 14 }}>
              <div><strong>{L("sync_enabled")}:</strong> {yn(syncStatus?.enabled)}</div>
              <div><strong>{L("sync_configured")}:</strong> {yn(syncStatus?.configured || health.databases_configured?.estock_source)}</div>
              <div><strong>{L("sync_interval")}:</strong> {syncStatus?.interval_seconds ?? "-"}</div>
              {syncStatus?.last_run_at && (
                <div><strong>{L("entry_date")}:</strong> {new Date(syncStatus.last_run_at).toLocaleString("en-US")}</div>
              )}
              {syncStatus?.last_status && (
                <div><strong>{L("status")}:</strong> {syncStatus.last_status}</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
