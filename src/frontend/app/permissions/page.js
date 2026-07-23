"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

// Permissions discovery (EMP_CONTROL parity): show the logged-in user exactly
// what they can and can't do — flags ON/OFF, limits, and role access.
export default function PermissionsPage() {
  const { lang, user } = useUI();
  const L = (k) => t(lang, k);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    // The token identifies the user server-side; pass employee_id too so it
    // still resolves when auth isn't enabled.
    api.myPermissions(user?.employee_id)
      .then((r) => alive && setData(r))
      .catch(() => alive && setData({ error: true }))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [user]);

  const label = (o) => (lang === "ar" ? o.ar : o.en);
  const name = data && (lang === "ar" ? data.name_ar : data.name_en || data.name_ar);
  const roleLabel = data && (lang === "ar" ? data.role_label_ar : data.role_label_en);

  return (
    <Shell titleKey="nav_permissions">
      <div className="page">
        <h2 className="section-title">{L("perm_title")}</h2>
        <p className="muted" style={{ marginTop: -4, marginBottom: 12, maxWidth: 720 }}>{L("perm_subtitle")}</p>

        {loading && <p className="muted">{L("loading")}</p>}
        {data?.error && <p className="badge danger">{L("offline")}</p>}

        {data && !data.error && (
          <>
            {/* Identity + role summary */}
            <div className="card" style={{ marginBottom: 16, display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 18 }}>{name}</div>
                <div className="muted" style={{ fontSize: 13 }}>
                  {L("perm_role")}: <span className="badge">{roleLabel}</span>
                  {!data.is_active && <span className="badge danger" style={{ marginInlineStart: 6 }}>{L("perm_inactive")}</span>}
                </div>
              </div>
              <div style={{ marginInlineStart: "auto", textAlign: "center" }}>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{data.granted_count}/{data.total_flags}</div>
                <div className="muted" style={{ fontSize: 12 }}>{L("perm_count")}</div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{Number(data.max_disc_per || 0)}%</div>
                <div className="muted" style={{ fontSize: 12 }}>{L("perm_max_disc")}</div>
              </div>
            </div>

            {/* Flag matrix */}
            <div className="card" style={{ marginBottom: 16 }}>
              <h3 className="section-title" style={{ marginTop: 0 }}>{L("perm_flags")}</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {data.flags.map((f) => (
                  <div
                    key={f.code}
                    style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 8, background: "var(--surface)" }}
                  >
                    <span className={`badge ${f.enabled ? "ok" : "danger"}`} style={{ minWidth: 78, textAlign: "center" }}>
                      {f.enabled ? "✓ " + L("perm_granted") : "✕ " + L("perm_denied")}
                    </span>
                    <span style={{ flex: 1 }}>
                      <strong>{lang === "ar" ? f.ar : f.en}</strong>
                      <span className="muted" style={{ marginInlineStart: 8, fontSize: 12 }}>
                        {lang === "ar" ? f.desc_ar : f.desc_en}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Role access */}
            <div className="card">
              <h3 className="section-title" style={{ marginTop: 0 }}>{L("perm_role_access")}</h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {data.role_access.map((a, i) => (
                  <span key={i} className="badge ok">{label(a)}</span>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </Shell>
  );
}
