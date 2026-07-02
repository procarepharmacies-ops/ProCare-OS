"use client";

import { usePathname, useRouter } from "next/navigation";
import { useUI } from "../providers";
import { t } from "../i18n";
import Icon from "./icons";

// `roles: null` = visible to everyone logged in. Otherwise the user's role
// must be in the list. Mirrors the backend's CEO-only gate on accounting /
// employees, plus a tighter POS-focused view for assistants.
const NAV = [
  { href: "/", key: "nav_dashboard", ico: "dashboard", roles: null },
  { href: "/inventory", key: "nav_inventory", ico: "pill", roles: null },
  { href: "/pos", key: "nav_pos", ico: "receipt", roles: null },
  { href: "/customers", key: "nav_customers", ico: "customers", roles: null },
  { href: "/vendors", key: "nav_vendors", ico: "store", roles: ["ceo", "manager"] },
  { href: "/purchasing", key: "nav_purchasing", ico: "box", roles: ["ceo", "manager"] },
  { href: "/transfers", key: "nav_transfers", ico: "transfer", roles: ["ceo", "manager"] },
  { href: "/accounting", key: "nav_accounting", ico: "coins", roles: ["ceo"] },
  { href: "/employees", key: "nav_employees", ico: "badge", roles: ["ceo"] },
  { href: "/alerts", key: "nav_alerts", ico: "bell", roles: null },
  { href: "/clinical", key: "nav_clinical", ico: "mortar", roles: null },
  { href: "/assistant", key: "nav_assistant", ico: "sparkle", roles: null },
  { href: "/reports", key: "nav_reports", ico: "chart", roles: ["ceo", "manager"] },
  { href: "/settings", key: "nav_settings", ico: "gear", roles: ["ceo", "manager"] },
];

export default function Shell({ titleKey, children }) {
  const { lang, theme, branch, branches, online, user, setBranch, toggleLang, toggleTheme, logout } = useUI();
  const L = (k) => t(lang, k);
  const pathname = usePathname();
  const router = useRouter();

  const nav = NAV.filter((n) => !n.roles || n.roles.includes(user?.role));
  const userName = user ? (lang === "ar" ? user.name_ar : user.name_en || user.name_ar) : "";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">
            <Icon name="cross" size={22} strokeWidth={2} />
          </span>
          <span>
            {L("app")}
            <small>{L("tagline")}</small>
          </span>
        </div>
        {nav.map((n) => (
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
