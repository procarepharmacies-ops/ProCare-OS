"use client";

import { useCallback, useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

const AUDIENCES = ["all", "top", "debtors", "inactive"];

export default function MarketingPage() {
  const { lang } = useUI();
  const L = (k) => t(lang, k);

  const [status, setStatus] = useState(null);
  const [campaigns, setCampaigns] = useState(null);
  const [form, setForm] = useState({ name: "", message: "", audience: "all" });
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  // Per-campaign expanded links (click-to-chat delivery mode).
  const [linksFor, setLinksFor] = useState(null); // campaign_id
  const [links, setLinks] = useState([]);

  const load = useCallback(async () => {
    try {
      const r = await api.campaigns();
      setCampaigns(r.campaigns);
    } catch {
      setCampaigns([]);
    }
  }, []);

  useEffect(() => {
    load();
    api.crmStatus().then(setStatus).catch(() => {});
  }, [load]);

  async function createCampaign(e) {
    e.preventDefault();
    if (!form.name.trim() || !form.message.trim() || saving) return;
    setSaving(true);
    setResult(null);
    try {
      await api.createCampaign({ name: form.name, message: form.message, audience: form.audience });
      setForm({ name: "", message: "", audience: "all" });
      await load();
    } catch (e2) {
      setResult({ ok: false, msg: e2.message });
    } finally {
      setSaving(false);
    }
  }

  async function sendCampaign(c) {
    setResult(null);
    try {
      const r = await api.sendCampaign(c.campaign_id);
      setResult({
        ok: true,
        msg: r.api_configured
          ? `${L("campaign_sent")} ✓ · ${r.sent_via_api}/${r.recipients}`
          : `${L("campaign_sent")} ✓ · ${r.recipients} ${L("recipients")} — ${L("wa_api_off")}`,
      });
      if (!r.api_configured) await showLinks(c.campaign_id);
      await load();
    } catch (e) {
      setResult({ ok: false, msg: e.message });
    }
  }

  async function showLinks(campaignId) {
    if (linksFor === campaignId) {
      setLinksFor(null);
      return;
    }
    try {
      const r = await api.campaignLinks(campaignId);
      setLinks(r.links);
      setLinksFor(campaignId);
    } catch {
      /* ignore */
    }
  }

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");

  return (
    <Shell titleKey="nav_marketing">
      {status && (
        <p className={`badge ${status.whatsapp_api_configured ? "ok" : "warn"}`}
           style={{ marginBottom: 14, display: "inline-block", padding: 8 }}>
          {status.whatsapp_api_configured ? L("wa_api_on") : L("wa_api_off")}
        </p>
      )}

      <div className="grid" style={{ gridTemplateColumns: "1fr 1.4fr", alignItems: "start" }}>
        {/* New campaign */}
        <form className="card" onSubmit={createCampaign}>
          <h3 className="section-title">{L("create_campaign")}</h3>
          <input
            className="input"
            placeholder={L("campaign_name")}
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            style={{ width: "100%", marginBottom: 10 }}
          />
          <textarea
            className="input"
            placeholder={L("campaign_message")}
            value={form.message}
            onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))}
            rows={5}
            style={{ width: "100%", marginBottom: 10, resize: "vertical" }}
          />
          <label className="muted" style={{ fontSize: 13 }}>{L("audience")}</label>
          <select
            className="select"
            value={form.audience}
            onChange={(e) => setForm((f) => ({ ...f, audience: e.target.value }))}
            style={{ width: "100%", margin: "6px 0 12px" }}
          >
            {AUDIENCES.map((a) => (
              <option key={a} value={a}>{L(`aud_${a}`)}</option>
            ))}
          </select>
          <button className="btn primary" type="submit" disabled={saving || !form.name.trim() || !form.message.trim()} style={{ width: "100%" }}>
            {L("create_campaign")}
          </button>
          {result && (
            <p className={`badge ${result.ok ? "ok" : "danger"}`} style={{ marginTop: 10, display: "block", padding: 8 }}>
              {result.msg}
            </p>
          )}
        </form>

        {/* Campaign list */}
        <div className="card">
          <h3 className="section-title">{L("campaigns_title")}</h3>
          {campaigns === null && <p className="muted">…</p>}
          {campaigns?.length === 0 && <p className="muted">—</p>}
          {campaigns?.map((c) => (
            <div key={c.campaign_id} style={{ borderBottom: "1px solid var(--border)", padding: "10px 0" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <strong style={{ flex: 1 }}>{c.name}</strong>
                <span className="badge">{L(`aud_${c.audience}`)}</span>
                <span className="badge muted">{fmt(c.recipient_count)} {L("recipients")}</span>
                <span className={`badge ${c.status === "sent" ? "ok" : "warn"}`}>
                  {c.status === "sent" ? L("campaign_sent") : L("campaign_draft")}
                </span>
                {c.status !== "sent" && (
                  <button className="btn primary" onClick={() => sendCampaign(c)}>{L("send_campaign")}</button>
                )}
                <button className="btn" onClick={() => showLinks(c.campaign_id)}>{L("show_links")}</button>
              </div>
              <p className="muted" style={{ fontSize: 13, margin: "6px 0 0", whiteSpace: "pre-wrap" }}>{c.message}</p>
              {linksFor === c.campaign_id && (
                <div style={{ marginTop: 8, maxHeight: 260, overflowY: "auto" }}>
                  {links.length === 0 && <p className="muted">—</p>}
                  {links.map((l) => (
                    <a key={l.customer_id} className="btn" href={l.link} target="_blank" rel="noreferrer"
                       style={{ display: "inline-block", margin: "0 4px 6px 0" }}>
                      💬 {l.name}
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </Shell>
  );
}
