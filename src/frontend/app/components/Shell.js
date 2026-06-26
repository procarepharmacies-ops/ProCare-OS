"use client";

import { usePathname, useRouter } from "next/navigation";
import { useUI } from "../providers";
import { t } from "../i18n";

const NAV = [
  { href: "/", key: "nav_dashboard", ico: "📊" },
  { href: "/inventory", key: "nav_inventory", ico: "💊" },
  { href: "/pos", key: "nav_pos", ico: "🧾" },
  { href: "/customers", key: "nav_customers", ico: "👥" },
  { href: "/alerts", key: "nav_alerts", ico: "🔔" },
  { href: "/assistant", key: "nav_assistant", ico: "🤖" },
];

export default function Shell({ titleKey, children }) {
  const { lang, theme, branch, branches, online, setBranch, toggleLang, toggleTheme } = useUI();
  const L = (k) => t(lang, k);
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          {L("app")}
          <small>{L("tagline")}</small>
        </div>
        {NAV.map((n) => (
          <div
            key={n.href}
            className={`navlink ${pathname === n.href ? "active" : ""}`}
            onClick={() => router.push(n.href)}
          >
            <span className="ico">{n.ico}</span>
            <span>{L(n.key)}</span>
          </div>
        ))}
        <div style={{ marginTop: "auto", paddingTop: 16 }} className="kpi-sub">
          <span
            className="dot"
            style={{ background: online ? "var(--ok)" : "var(--danger)", marginInlineEnd: 6 }}
          />
          {L("backend_status")}: {online ? L("online") : L("offline")}
        </div>
      </aside>

      <main className="content">
        <div className="topbar">
          <h1 className="page-title">{L(titleKey)}</h1>
          <div className="controls">
            <select
              className="select"
              value={branch}
              onChange={(e) => setBranch(Number(e.target.value))}
              title={L("branch")}
            >
              <option value={0}>{L("all_branches")}</option>
              {branches.map((b) => (
                <option key={b.branch_id} value={b.branch_id}>
                  {(lang === "ar" ? b.name_ar : b.name_en) + (b.pilot ? " ★" : "")}
                </option>
              ))}
            </select>
            <button className="btn icon" onClick={toggleLang} title="language / اللغة">
              {lang === "ar" ? "EN" : "ع"}
            </button>
            <button className="btn icon" onClick={toggleTheme} title="theme / المظهر">
              {theme === "light" ? "🌙" : "☀️"}
            </button>
          </div>
        </div>
        {children}
      </main>
    </div>
  );
}
