"use client";

// Settings and escape hatches: branch, language, theme, the full desktop app,
// and sign out.

import { useUI } from "../../providers";
import { t } from "../../i18n";

export default function RXMorePage() {
  const { lang, theme, branch, branches, user, online, setBranch, toggleLang, toggleTheme, logout } =
    useUI();
  const L = (k) => t(lang, k);

  return (
    <div>
      <div className="rx-card">
        <b>{user?.name_ar || user?.username || "—"}</b>
        <div className="rx-muted">{user ? L(`role_${user.role}`) : ""}</div>
        <div style={{ height: 6 }} />
        <span className={`rx-chip ${online ? "ok" : "warn"}`}>
          {online ? L("online") : L("rx_offline")}
        </span>
      </div>

      <div className="rx-card">
        <div className="rx-muted">{L("branch")}</div>
        <select value={branch} onChange={(e) => setBranch(Number(e.target.value))}>
          <option value={0}>{L("all_branches")}</option>
          {(branches || []).map((b) => (
            <option key={b.branch_id} value={b.branch_id}>
              {lang === "ar" ? b.name_ar : b.name_en || b.name_ar}
            </option>
          ))}
        </select>
        <div style={{ height: 10 }} />
        <button className="rx-btn" onClick={toggleLang}>
          {lang === "ar" ? "English" : "العربية"}
        </button>
        <div style={{ height: 8 }} />
        <button className="rx-btn" onClick={toggleTheme}>
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
      </div>

      <div className="rx-card">
        {/* A full page load, not a client transition: leaving /rx also leaves
            the RX service-worker scope. */}
        <a className="rx-btn" href="/" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          {L("rx_open_full_app")}
        </a>
        <div style={{ height: 8 }} />
        <button className="rx-btn danger" onClick={logout}>
          {L("logout")}
        </button>
      </div>
    </div>
  );
}
