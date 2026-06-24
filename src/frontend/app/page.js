"use client";

import { useEffect, useState } from "react";
import { useUI } from "./providers";
import { t } from "./i18n";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export default function Dashboard() {
  const { lang, theme, toggleLang, toggleTheme } = useUI();
  const [health, setHealth] = useState(null);
  const [branches, setBranches] = useState([]);
  const [branch, setBranch] = useState("ALL");
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [h, b] = await Promise.all([
          fetch(`${API_BASE}/api/health`).then((r) => r.json()),
          fetch(`${API_BASE}/api/branches`).then((r) => r.json()),
        ]);
        if (!alive) return;
        setHealth(h);
        setBranches(b.branches || []);
        setError(false);
      } catch {
        if (alive) setError(true);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const L = (k) => t(lang, k);
  const online = Boolean(health) && !error;
  const kpis = ["sales_today", "sales_month", "low_stock", "expiring_30", "debtors"];

  return (
    <main style={S.main}>
      <header style={S.header}>
        <div>
          <h1 style={S.h1}>{L("app")}</h1>
          <p style={S.tagline}>
            {L("tagline")} · {L("phase0")}
          </p>
        </div>
        <div style={S.controls}>
          <label style={S.field}>
            <span style={S.fieldLabel}>{L("branch")}</span>
            <select
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              style={S.select}
            >
              <option value="ALL">{L("all_branches")}</option>
              {branches.map((b) => (
                <option key={b.code} value={b.code}>
                  {(lang === "ar" ? b.name_ar : b.name_en) + (b.pilot ? " ★" : "")}
                </option>
              ))}
            </select>
          </label>
          <button onClick={toggleLang} style={S.btn} title="language / اللغة">
            {lang === "ar" ? "EN" : "ع"}
          </button>
          <button onClick={toggleTheme} style={S.btn} title="theme / المظهر">
            {theme === "light" ? "🌙" : "☀️"}
          </button>
        </div>
      </header>

      <section style={S.statusRow}>
        <span
          style={{ ...S.dot, background: online ? "var(--ok)" : "var(--danger)" }}
        />
        <strong>{L("backend_status")}:</strong>
        <span>{online ? L("online") : L("offline")}</span>
        {health?.using_example_config && (
          <span style={S.badge}>{L("using_example")}</span>
        )}
      </section>

      <section style={S.grid}>
        {kpis.map((k) => (
          <div key={k} style={S.card}>
            <div style={S.cardLabel}>{L(k)}</div>
            <div style={S.cardValue}>—</div>
            <div style={S.cardNote}>{L("not_wired")}</div>
          </div>
        ))}
      </section>
    </main>
  );
}

// Inline styles keyed to the CSS variables in globals.css — themable + RTL-safe
// (logical properties), with zero extra dependencies for the skeleton.
const S = {
  main: { maxWidth: 1100, margin: "0 auto", padding: "32px 24px" },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 16,
    flexWrap: "wrap",
  },
  h1: { margin: 0, fontSize: 30, color: "var(--primary)" },
  tagline: { margin: "4px 0 0", color: "var(--muted)", fontSize: 14 },
  controls: { display: "flex", alignItems: "flex-end", gap: 10, flexWrap: "wrap" },
  field: { display: "flex", flexDirection: "column", gap: 4 },
  fieldLabel: { fontSize: 12, color: "var(--muted)" },
  select: {
    padding: "8px 10px",
    borderRadius: 8,
    border: "1px solid var(--border)",
    background: "var(--surface)",
    color: "var(--text)",
  },
  btn: {
    padding: "8px 14px",
    borderRadius: 8,
    border: "1px solid var(--border)",
    background: "var(--surface)",
    color: "var(--text)",
    cursor: "pointer",
    fontSize: 16,
    lineHeight: 1,
  },
  statusRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    margin: "24px 0",
    padding: "12px 16px",
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    boxShadow: "var(--shadow)",
  },
  dot: { width: 10, height: 10, borderRadius: "50%", display: "inline-block" },
  badge: {
    marginInlineStart: "auto",
    fontSize: 12,
    color: "var(--warning)",
    border: "1px solid var(--warning)",
    borderRadius: 999,
    padding: "2px 10px",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
    gap: 16,
  },
  card: {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: 18,
    boxShadow: "var(--shadow)",
  },
  cardLabel: { color: "var(--muted)", fontSize: 13 },
  cardValue: { fontSize: 30, fontWeight: 700, margin: "6px 0" },
  cardNote: { fontSize: 11, color: "var(--muted)" },
};
