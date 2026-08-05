"use client";

import { useCallback, useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

const SEV_BADGE = { critical: "danger", warning: "warn", info: "" };

// Notification center (News_bar / Flag parity): live expiry / low-stock /
// shortage events grouped by category, each dismissible (persisted).
export default function NotificationsPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await api.notifications(branch));
    } catch {
      setData({ total: 0, critical: 0, groups: [] });
    } finally {
      setLoading(false);
    }
  }, [branch]);

  useEffect(() => {
    load();
  }, [load]);

  const dismiss = async (keys) => {
    if (!keys.length) return;
    await api.dismissNotifications(keys, branch);
    await load();
  };

  const label = (g) => (lang === "ar" ? g.label_ar : g.label_en);
  const title = (it) => (lang === "ar" ? it.title_ar : it.title_en);
  const body = (it) => (lang === "ar" ? it.body_ar : it.body_en);

  return (
    <Shell titleKey="nav_notifications">
      <div className="page">
        <h2 className="section-title">{L("ntf_title")}</h2>
        <p className="muted" style={{ marginTop: -4, marginBottom: 12, maxWidth: 720 }}>{L("ntf_subtitle")}</p>

        {loading && <p className="muted">{L("loading")}</p>}

        {!loading && data && data.total === 0 && (
          <p className="badge ok" style={{ display: "inline-block" }}>{L("ntf_all_clear")}</p>
        )}

        {!loading && data && data.groups.filter((g) => g.count > 0).map((g) => (
          <div className="card" style={{ marginBottom: 12 }} key={g.category}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <h3 className="section-title" style={{ margin: 0 }}>{label(g)}</h3>
              <span className="muted" style={{ fontSize: 12 }}>({g.count})</span>
              <button
                className="btn"
                style={{ marginInlineStart: "auto" }}
                onClick={() => dismiss(g.items.map((it) => it.key))}
              >
                {L("ntf_dismiss_all")}
              </button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {g.items.map((it) => (
                <div
                  key={it.key}
                  style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 8, background: "var(--surface)" }}
                >
                  <span className={`badge ${SEV_BADGE[it.severity] || ""}`} style={{ minWidth: 64, textAlign: "center" }}>
                    {title(it)}
                  </span>
                  <span style={{ flex: 1 }}>{body(it)}</span>
                  <button className="btn" onClick={() => dismiss([it.key])}>{L("ntf_dismiss")}</button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Shell>
  );
}
