"use client";

import { usePathname, useRouter } from "next/navigation";
import { useUI } from "../providers";
import { t } from "../i18n";
import Icon from "./icons";

const NAV = [
  { href: "/", key: "nav_dashboard", ico: "dashboard" },
  { href: "/inventory", key: "nav_inventory", ico: "pill" },
  { href: "/pos", key: "nav_pos", ico: "receipt" },
  { href: "/customers", key: "nav_customers", ico: "customers" },
  { href: "/vendors", key: "nav_vendors", ico: "store" },
  { href: "/purchasing", key: "nav_purchasing", ico: "box" },
  { href: "/transfers", key: "nav_transfers", ico: "transfer" },
  { href: "/accounting", key: "nav_accounting", ico: "coins" },
  { href: "/employees", key: "nav_employees", ico: "badge" },
  { href: "/alerts", key: "nav_alerts", ico: "bell" },
  { href: "/clinical", key: "nav_clinical", ico: "mortar" },
  { href: "/assistant", key: "nav_assistant", ico: "sparkle" },
  { href: "/reports", key: "nav_reports", ico: "chart" },
  { href: "/settings", key: "nav_settings", ico: "gear" },
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
          <span className="logo">
            <Icon name="cross" size={22} strokeWidth={2} />
          </span>
          <span>
            {L("app")}
            <small>{L("tagline")}</small>
          </span>
        </div>
        {NAV.map((n) => (
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
