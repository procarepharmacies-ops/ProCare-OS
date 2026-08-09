"use client";

// Phone-first shell for ProCare RX. Deliberately NOT components/Shell.js: that
// is a desktop sidebar with a 7-group nav, a branch <select> and a ticker
// polling every 60s. Keeping them separate also keeps the desktop shell out of
// the RX bundle entirely.

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUI } from "../../providers";
import { t } from "../../i18n";

const TABS = [
  { href: "/rx", key: "rx_tab_count", ico: "📦", match: (p) => p === "/rx" || p.startsWith("/rx/count") },
  { href: "/rx/tasks", key: "rx_tab_tasks", ico: "✅", match: (p) => p.startsWith("/rx/tasks") },
  { href: "/rx/substitutes", key: "rx_tab_alts", ico: "💊", match: (p) => p.startsWith("/rx/substitutes") },
  { href: "/rx/more", key: "rx_tab_more", ico: "⚙️", match: (p) => p.startsWith("/rx/more") },
];

export default function RXShell({ children }) {
  const { lang, online, user } = useUI();
  const L = (k) => t(lang, k);
  const pathname = usePathname() || "/rx";

  return (
    <div className="rx">
      <div className="rx-topbar">
        <span style={{ fontSize: 20 }}>🏥</span>
        <span className="rx-title">ProCare RX</span>
        {user && <span className="rx-muted">{user.name_ar || user.username}</span>}
      </div>

      {/* The counter needs to know instantly, not discover it on a failed save. */}
      {!online && <div className="rx-offline">{L("rx_offline")}</div>}

      <main className="rx-main">{children}</main>

      <nav className="rx-tabs">
        {TABS.map((tab) => (
          <Link
            key={tab.href}
            href={tab.href}
            className="rx-tab"
            data-active={tab.match(pathname)}
          >
            <span className="ico">{tab.ico}</span>
            <span>{L(tab.key)}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
