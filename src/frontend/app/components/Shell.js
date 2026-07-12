"use client";

import { usePathname, useRouter } from "next/navigation";
import { useUI } from "../providers";
import { t } from "../i18n";
import Icon from "./icons";
import Wordmark from "./Wordmark";

// `roles: null` = visible to everyone logged in. Otherwise the user's role
// must be in the list. Mirrors the backend's CEO-only gate on accounting /
// employees, plus a tighter POS-focused view for assistants.
// Grouped رئيسي/فرعي: section headers with their sub-screens, eStock-style.
const NAV_GROUPS = [
  {
    key: "navg_ops",
    items: [
      { href: "/", key: "nav_dashboard", ico: "dashboard", roles: null },
      { href: "/pos", key: "nav_pos", ico: "receipt", roles: null },
      { href: "/prescriptions", key: "nav_prescriptions", ico: "camera", roles: null },
      { href: "/tasks", key: "nav_tasks", ico: "clipboard", roles: null },
    ],
  },
  {
    key: "navg_inventory",
    items: [
      { href: "/inventory", key: "nav_inventory", ico: "pill", roles: null },
      { href: "/stocktaking", key: "nav_stocktaking", ico: "clipboard", roles: null },
      { href: "/shortages", key: "nav_shortages", ico: "sheet", roles: null },
      { href: "/transfers", key: "nav_transfers", ico: "transfer", roles: ["ceo", "manager"] },
      { href: "/alerts", key: "nav_alerts", ico: "bell", roles: null },
    ],
  },
  {
    key: "navg_purchasing",
    items: [
      { href: "/purchasing", key: "nav_purchasing", ico: "box", roles: ["ceo", "manager"] },
      { href: "/vendors", key: "nav_vendors", ico: "store", roles: ["ceo", "manager"] },
    ],
  },
  {
    key: "navg_money",
    items: [
      { href: "/treasury", key: "nav_treasury", ico: "safe", roles: ["ceo", "manager"] },
      { href: "/accounting", key: "nav_accounting", ico: "coins", roles: ["ceo"] },
      { href: "/audit", key: "nav_audit", ico: "scale", roles: ["ceo", "manager"] },
      { href: "/reports", key: "nav_reports", ico: "chart", roles: ["ceo", "manager"] },
    ],
  },
  {
    key: "navg_people",
    items: [
      { href: "/customers", key: "nav_customers", ico: "customers", roles: null },
      { href: "/marketing", key: "nav_marketing", ico: "megaphone", roles: ["ceo", "manager"] },
      { href: "/employees", key: "nav_employees", ico: "badge", roles: ["ceo"] },
    ],
  },
  {
    key: "navg_tools",
    items: [
      { href: "/clinical", key: "nav_clinical", ico: "mortar", roles: null },
      { href: "/assistant", key: "nav_assistant", ico: "sparkle", roles: null },
      { href: "/settings", key: "nav_settings", ico: "gear", roles: ["ceo", "manager"] },
    ],
  },
];

export default function Shell({ titleKey, children }) {
  const { lang, theme, branch, branches, online, user, setBranch, toggleLang, toggleTheme, logout } = useUI();
  const L = (k) => t(lang, k);
  const pathname = usePathname();
  const router = useRouter();

  const groups = NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((n) => !n.roles || n.roles.includes(user?.role)),
  })).filter((g) => g.items.length > 0);
  const userName = user ? (lang === "ar" ? user.name_ar : user.name_en || user.name_ar) : "";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">
            <Wordmark size={38} />
          </span>
          <span>
            {L("app")}
            <small>{L("tagline")}</small>
          </span>
        </div>
        {groups.map((g) => (
          <div key={g.key}>
            <div className="kpi-sub" style={{ padding: "10px 10px 2px", fontWeight: 700, opacity: 0.75 }}>
              {L(g.key)}
            </div>
            {g.items.map((n) => (
              <div
                key={n.href}
                className={`navlink ${pathname === n.href ? "active" : ""}`}
                onClick={() => router.push(n.href)}
              >
                <span className="ico">
                  <Icon name={n.ico} />
                </span>
                <span>{L(n.key)}</span>
              </div>
            ))}
          </div>
        ))}
        <div style={{ marginTop: "auto", paddingTop: 16, display: "flex", flexDirection: "column", gap: 10 }}>
          {user && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <div style={{ fontSize: 13 }}>
                <div style={{ fontWeight: 700 }}>{userName}</div>
                <div className="kpi-sub">{L(`role_${user.role}`)}</div>
              </div>
              <button className="btn icon" onClick={logout} title={L("logout")}>
                <Icon name="logout" size={15} />
              </button>
            </div>
          )}
          <div className="kpi-sub">
            <span
              className="dot"
              style={{ background: online ? "var(--ok)" : "var(--danger)", marginInlineEnd: 6 }}
            />
            {L("backend_status")}: {online ? L("online") : L("offline")}
          </div>
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
            <button className="btn icon" onClick={toggleTheme} title="theme / المظهر" style={{ display: "grid", placeItems: "center" }}>
              <Icon name={theme === "light" ? "moon" : "sun"} size={17} />
            </button>
          </div>
        </div>
        {children}
      </main>
    </div>
  );
}
