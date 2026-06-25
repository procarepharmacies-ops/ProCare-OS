"use client";

import { useUI } from "../providers";
import { t } from "../i18n";

export default function Header({ branches, branch, setBranch, health, online, onRefresh }) {
  const { lang, theme, toggleLang, toggleTheme } = useUI();
  const L = (k) => t(lang, k);

  return (
    <header className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
      <div className="grow">
        <h1 style={{ margin: 0, fontSize: 28, color: "var(--primary)" }}>{L("app")}</h1>
        <p style={{ margin: "3px 0 0", color: "var(--muted)", fontSize: 13 }}>
          {L("tagline")} · {L("phase")}
        </p>
        <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ display: "inline-flex", gap: 6, alignItems: "center", fontSize: 13 }}>
            <span className="dot" style={{ background: online ? "var(--ok)" : "var(--danger)" }} />
            <strong>{L("backend_status")}:</strong>
            <span>{online ? L("online") : L("offline")}</span>
          </span>
          {online && health?.data_backend === "demo" && (
            <span className="badge warn">{L("demo_badge")}</span>
          )}
          {online && (
            <span className="badge">
              {health?.ai_engine === "llm" ? L("engine_llm") : L("engine_rules")}
            </span>
          )}
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <select
          className="select"
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          aria-label={L("branch")}
        >
          <option value="ALL">{L("all_branches")}</option>
          {branches.map((b) => (
            <option key={b.code} value={b.code}>
              {(lang === "ar" ? b.name_ar : b.name_en) + (b.pilot ? " ★" : "")}
            </option>
          ))}
        </select>
        <button className="btn" onClick={onRefresh} title={L("refresh")}>⟳</button>
        <button className="btn" onClick={toggleLang} title="language / اللغة">
          {lang === "ar" ? "EN" : "ع"}
        </button>
        <button className="btn" onClick={toggleTheme} title="theme / المظهر">
          {theme === "light" ? "🌙" : "☀️"}
        </button>
      </div>
    </header>
  );
}
