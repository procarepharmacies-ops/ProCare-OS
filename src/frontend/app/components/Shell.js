"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";
import Icon from "./icons";
import Wordmark from "./Wordmark";

// Compact notification ribbon for the topbar: bell + unread badge + the
// highest-severity headline, scrolling to the full center on click. Fail-soft
// (renders just the bell when the feed can't load) so it never breaks a page.
function NotificationTicker({ branch, lang, onOpen }) {
  const [tick, setTick] = useState(null);
  useEffect(() => {
    let alive = true;
    const load = () => api.notificationTicker(branch, 12).then((r) => alive && setTick(r)).catch(() => {});
    load();
    const id = setInterval(load, 60000); // refresh once a minute
    return () => { alive = false; clearInterval(id); };
  }, [branch]);

  const total = tick?.total || 0;
  const top = tick?.items?.[0];
  const headline = top ? (lang === "ar" ? top.body_ar : top.body_en) : "";
  return (
    <button
      className="btn icon"
      onClick={onOpen}
      title={t(lang, "nav_notifications")}
      style={{ position: "relative", display: "inline-flex", alignItems: "center", gap: 6, width: "auto", padding: "0 10px", maxWidth: 320 }}
    >
      <Icon name="bell" size={16} />
      {total > 0 && (
        <span
          className="badge danger"
          style={{ fontSize: 11, padding: "0 6px", borderRadius: 10 }}
        >
          {total}
        </span>
      )}
      {headline && (
        <span className="muted" style={{ fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {headline}
        </span>
      )}
    </button>
  );
}

// `roles: null` = visible to everyone logged in. Otherwise the user's role
// must be in the list. Mirrors the backend's CEO-only gate on accounting /
// employees, plus a tighter POS-focused view for assistants.
// Grouped رئيسي/فرعي: section headers with their sub-screens, eStock-style.
const NAV_GROUPS = [
  {
    key: "navg_ops",
    items: [
      { href: "/", key: "nav_dashboard", ico: "dashboard", roles: null },
      { href: "/operations", key: "nav_operations", ico: "chart", roles: ["ceo", "manager"] },
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
      { href: "/notifications", key: "nav_notifications", ico: "bell", roles: null },
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
      { href: "/deep", key: "nav_deep", ico: "sparkle", roles: ["ceo", "manager"] },
      { href: "/reports-daily", key: "nav_reports_daily", ico: "sheet", roles: ["ceo", "manager"] },
      { href: "/reports-item", key: "nav_item_movement", ico: "sheet", roles: ["ceo", "manager"] },
    ],
  },
  {
    key: "navg_people",
    items: [
      { href: "/customers", key: "nav_customers", ico: "customers", roles: null },
      { href: "/marketing", key: "nav_marketing", ico: "megaphone", roles: ["ceo", "manager"] },
      { href: "/employees", key: "nav_employees", ico: "badge", roles: ["ceo"] },
      { href: "/incentives", key: "nav_incentives", ico: "megaphone", roles: ["ceo", "manager"] },
      { href: "/commissions", key: "nav_commissions", ico: "coins", roles: ["ceo", "manager"] },
    ],
  },
  {
    key: "navg_tools",
    items: [
      { href: "/clinical", key: "nav_clinical", ico: "mortar", roles: null },
      { href: "/assistant", key: "nav_assistant", ico: "sparkle", roles: null },
      { href: "/permissions", key: "nav_permissions", ico: "badge", roles: null },
      { href: "/settings", key: "nav_settings", ico: "gear", roles: ["ceo", "manager"] },
    ],
  },
  {
    key: "navg_agentic",
    items: [
      { href: "/cockpit", key: "nav_cockpit", ico: "dashboard", roles: ["ceo", "manager"] },
      { href: "/agents", key: "nav_agents", ico: "robot", roles: ["ceo", "manager"] },
      { href: "/knowledge", key: "nav_knowledge", ico: "book", roles: ["ceo", "manager", "assistant"] },
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
            <NotificationTicker branch={branch} lang={lang} onOpen={() => router.push("/notifications")} />
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
