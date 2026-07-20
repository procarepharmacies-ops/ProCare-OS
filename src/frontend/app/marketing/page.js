"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

const AUDIENCES = ["all", "top", "debtors", "inactive"];
const CHANNELS = ["fb", "ig", "wa-status", "tiktok", "linkedin"];
const CHANNEL_LABELS = { fb: "Facebook", ig: "Instagram", "wa-status": "WhatsApp Status", tiktok: "TikTok", linkedin: "LinkedIn" };

export default function MarketingPage() {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  const [tab, setTab] = useState("campaigns"); // campaigns, calendar, copywriter, offers, promos

  return (
    <Shell titleKey="nav_marketing">
      <div className="tabs" style={{ display: "flex", gap: 12, marginBottom: 20, borderBottom: "1px solid var(--border)", paddingBottom: 12 }}>
        {[
          ["campaigns", "📢 " + L("campaigns_title")],
          ["calendar", "📅 " + L("social_calendar")],
          ["copywriter", "✍️ " + L("social_copywriter")],
          ["offers", "🎨 " + L("social_offer_card")],
          ["promos", "🏷️ " + L("promo_list")],
        ].map(([t_id, label]) => (
          <button
            key={t_id}
            onClick={() => setTab(t_id)}
            style={{
              padding: "8px 12px",
              border: "none",
              background: tab === t_id ? "var(--primary)" : "transparent",
              color: tab === t_id ? "white" : "var(--text)",
              borderRadius: 4,
              cursor: "pointer",
              fontSize: 13,
              fontWeight: tab === t_id ? "bold" : "normal",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "campaigns" && <CampaignsTab L={L} />}
      {tab === "calendar" && <CalendarTab L={L} />}
      {tab === "copywriter" && <CopywriterTab L={L} />}
      {tab === "offers" && <OffersTab L={L} />}
      {tab === "promos" && <PromosTab L={L} />}
    </Shell>
  );
}

// ============ Campaigns Tab (Phase 3) ============

function CampaignsTab({ L }) {
  const [status, setStatus] = useState(null);
  const [campaigns, setCampaigns] = useState(null);
  const [form, setForm] = useState({ name: "", message: "", audience: "all" });
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [linksFor, setLinksFor] = useState(null);
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
    <>
      {status && (
        <p className={`badge ${status.whatsapp_api_configured ? "ok" : "warn"}`}
           style={{ marginBottom: 14, display: "inline-block", padding: 8 }}>
          {status.whatsapp_api_configured ? L("wa_api_on") : L("wa_api_off")}
        </p>
      )}

      <div className="grid" style={{ gridTemplateColumns: "1fr 1.4fr", alignItems: "start" }}>
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
    </>
  );
}

// ============ Content Calendar Tab (Phase 4) ============

function CalendarTab({ L }) {
  const [channel, setChannel] = useState("");
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [posts, setPosts] = useState(null);
  const [err, setErr] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await api.socialCalendar(channel, month);
      setPosts(r);
    } catch {
      setPosts({ posts_by_date: {} });
    }
  }, [channel, month]);

  useEffect(() => {
    load();
  }, [load]);

  async function approve(postId) {
    setErr(null);
    try {
      await api.approveSocialPost(postId);
      await load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function publish(postId) {
    setErr(null);
    try {
      await api.publishSocialPost(postId);
      await load();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div className="card">
      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        <select
          className="select"
          value={channel}
          onChange={(e) => setChannel(e.target.value)}
        >
          <option value="">{L("social_channel")} — {L("all_lbl")}</option>
          {CHANNELS.map((ch) => (
            <option key={ch} value={ch}>{CHANNEL_LABELS[ch]}</option>
          ))}
        </select>
        <select
          className="select"
          value={month}
          onChange={(e) => setMonth(Number(e.target.value))}
        >
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((m) => (
            <option key={m} value={m}>{new Date(2026, m - 1, 1).toLocaleDateString("en-US", { month: "long" })}</option>
          ))}
        </select>
      </div>

      {err && <p className="badge danger" style={{ display: "block", padding: 8, marginBottom: 10 }}>{err}</p>}
      {posts === null && <p className="muted">…</p>}
      {posts?.total_posts === 0 && <p className="muted">{L("social_no_posts")} — ✍️ {L("social_copywriter")}</p>}

      {posts?.posts_by_date && Object.keys(posts.posts_by_date).length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
          {Object.entries(posts.posts_by_date).sort().map(([date, items]) => (
            <div key={date} className="card" style={{ padding: 12, border: "1px solid var(--border)" }}>
              <h4 style={{ margin: "0 0 8px", fontSize: 14, fontWeight: "bold" }}>{date}</h4>
              {items.map((post) => (
                <div key={post.post_id} style={{ fontSize: 12, marginBottom: 8, paddingBottom: 8, borderBottom: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <span className="badge">{CHANNEL_LABELS[post.channel]}</span>
                    <span className={`badge ${post.status === "published" ? "ok" : post.status === "approved" ? "" : "warn"}`}>
                      {L(`social_${post.status}`) || post.status}
                    </span>
                    {post.promo_code && <span className="badge">🏷️ {post.promo_code}</span>}
                  </div>
                  {post.title && <p style={{ margin: "6px 0", fontWeight: "bold" }}>{post.title}</p>}
                  <p style={{ margin: "4px 0", color: "var(--text-muted)", direction: "rtl", textAlign: "start" }}>
                    {post.body_ar}
                  </p>
                  <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                    {post.status === "draft" && (
                      <button className="btn" style={{ fontSize: 11, padding: "3px 8px" }} onClick={() => approve(post.post_id)}>
                        ✓ {L("social_approve_post")}
                      </button>
                    )}
                    {(post.status === "approved" || post.status === "scheduled") && (
                      <button className="btn primary" style={{ fontSize: 11, padding: "3px 8px" }} onClick={() => publish(post.post_id)}>
                        🚀 {L("social_publish_post")}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============ AI Copywriter Tab (Phase 4) ============

function CopywriterTab({ L }) {
  const [context, setContext] = useState({ offer_name: "", discount: "", product_type: "", urgency: "" });
  const [brand, setBrand] = useState("بروكير / ProCare");
  const [bodyAr, setBodyAr] = useState("");
  const [bodyEn, setBodyEn] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  // Save-as-post: the generated (or hand-written) copy becomes a calendar draft.
  const [channel, setChannel] = useState("fb");
  const [scheduleDate, setScheduleDate] = useState(new Date().toISOString().split("T")[0]);
  const [promoCode, setPromoCode] = useState("");
  const [saving, setSaving] = useState(false);

  async function generate() {
    setLoading(true);
    setResult(null);
    try {
      const r = await api.generateSocialCopy(context, brand);
      setBodyAr(r.body_ar);
      setBodyEn(r.body_en);
      setResult({ ok: true, msg: L("social_copy_generated") });
    } catch (e) {
      setResult({ ok: false, msg: e.message });
    } finally {
      setLoading(false);
    }
  }

  async function saveAsPost() {
    if (!bodyAr.trim() || saving) return;
    setSaving(true);
    setResult(null);
    try {
      const post = await api.createSocialPost({
        channel,
        body_ar: bodyAr,
        body_en: bodyEn || null,
        title: context.offer_name || null,
        scheduled_at: new Date(scheduleDate + "T10:00:00").toISOString(),
        promo_code: promoCode.trim() ? promoCode.trim().toUpperCase() : null,
      });
      setResult({ ok: true, msg: `${L("social_create_post")} ✓ · #${post.post_id} · ${scheduleDate}` });
    } catch (e) {
      setResult({ ok: false, msg: e.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <div className="card">
        <h3 className="section-title">{L("social_context")}</h3>
        <div style={{ marginBottom: 12 }}>
          <label className="muted" style={{ fontSize: 12 }}>{L("offer_brand")}</label>
          <input
            className="input"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            style={{ width: "100%", marginBottom: 10 }}
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label className="muted" style={{ fontSize: 12 }}>اسم العرض / Offer name</label>
          <input
            className="input"
            value={context.offer_name}
            onChange={(e) => setContext({ ...context, offer_name: e.target.value })}
            style={{ width: "100%", marginBottom: 10 }}
            placeholder="Summer Sale / عرض صيفي"
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label className="muted" style={{ fontSize: 12 }}>نسبة الخصم / Discount</label>
          <input
            className="input"
            value={context.discount}
            onChange={(e) => setContext({ ...context, discount: e.target.value })}
            style={{ width: "100%", marginBottom: 10 }}
            placeholder="50% / 100 EGP"
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label className="muted" style={{ fontSize: 12 }}>نوع المنتج / Product type</label>
          <input
            className="input"
            value={context.product_type}
            onChange={(e) => setContext({ ...context, product_type: e.target.value })}
            style={{ width: "100%", marginBottom: 10 }}
            placeholder="Health & Wellness"
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <label className="muted" style={{ fontSize: 12 }}>الإلحاح / Urgency</label>
          <input
            className="input"
            value={context.urgency}
            onChange={(e) => setContext({ ...context, urgency: e.target.value })}
            style={{ width: "100%", marginBottom: 10 }}
            placeholder="This week only / فقط هذا الأسبوع"
          />
        </div>
        <button
          className="btn primary"
          onClick={generate}
          disabled={loading}
          style={{ width: "100%" }}
        >
          {loading ? "…" : L("social_generate_copy")}
        </button>
        {result && (
          <p className={`badge ${result.ok ? "ok" : "danger"}`} style={{ marginTop: 10, display: "block", padding: 8 }}>
            {result.msg}
          </p>
        )}
      </div>

      <div className="card">
        <h3 className="section-title">{L("social_body_ar")}</h3>
        <textarea
          className="input"
          value={bodyAr}
          onChange={(e) => setBodyAr(e.target.value)}
          rows={6}
          style={{ width: "100%", marginBottom: 16, resize: "vertical", direction: "rtl" }}
        />
        <h3 className="section-title">{L("social_body_en")}</h3>
        <textarea
          className="input"
          value={bodyEn}
          onChange={(e) => setBodyEn(e.target.value)}
          rows={6}
          style={{ width: "100%", marginBottom: 16, resize: "vertical" }}
        />

        {/* Save the copy into the content calendar as a scheduled draft */}
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: 14 }}>
          <h3 className="section-title">{L("social_create_post")}</h3>
          <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
            <select className="select" value={channel} onChange={(e) => setChannel(e.target.value)} style={{ flex: 1, minWidth: 120 }}>
              {CHANNELS.map((ch) => (
                <option key={ch} value={ch}>{CHANNEL_LABELS[ch]}</option>
              ))}
            </select>
            <input
              className="input"
              type="date"
              value={scheduleDate}
              onChange={(e) => setScheduleDate(e.target.value)}
              style={{ flex: 1, minWidth: 130 }}
            />
          </div>
          <input
            className="input"
            placeholder={L("social_promo_code")}
            value={promoCode}
            onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
            style={{ width: "100%", marginBottom: 10 }}
          />
          <button className="btn primary" onClick={saveAsPost} disabled={saving || !bodyAr.trim()} style={{ width: "100%" }}>
            {saving ? "…" : `📅 ${L("social_create_post")}`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============ Offer Card Generator Tab (Phase 4) ============

function OffersTab({ L }) {
  const [brand, setBrand] = useState("ProCare");
  const [discount, setDiscount] = useState("50%");
  const [validity, setValidity] = useState("2026-08-31");
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    // Clear canvas
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Brand gradient background
    const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    gradient.addColorStop(0, "#2196F3");
    gradient.addColorStop(1, "#1976D2");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Discount circle (big)
    ctx.fillStyle = "#FF6F00";
    ctx.beginPath();
    ctx.arc(canvas.width * 0.85, canvas.height * 0.25, 60, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 48px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(discount, canvas.width * 0.85, canvas.height * 0.25);

    // Brand name
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 48px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(brand, canvas.width / 2, canvas.height * 0.4);

    // "OFF" text
    ctx.font = "bold 32px Arial";
    ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
    ctx.fillText("خصم", canvas.width / 2, canvas.height * 0.6);

    // Validity
    ctx.font = "bold 20px Arial";
    ctx.fillStyle = "rgba(255, 255, 255, 0.8)";
    ctx.fillText(`صالح حتى ${validity}`, canvas.width / 2, canvas.height * 0.85);
  }, [brand, discount, validity]);

  function downloadImage() {
    const canvas = canvasRef.current;
    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = `offer-${Date.now()}.png`;
    link.click();
  }

  return (
    <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <div className="card">
        <h3 className="section-title">{L("offer_preview")}</h3>
        <canvas
          ref={canvasRef}
          width={400}
          height={300}
          style={{ width: "100%", border: "1px solid var(--border)", borderRadius: 4, marginBottom: 16 }}
        />
        <button className="btn primary" onClick={downloadImage} style={{ width: "100%" }}>
          {L("offer_download")}
        </button>
      </div>

      <div className="card">
        <h3 className="section-title">{L("offer_brand")}</h3>
        <input
          className="input"
          value={brand}
          onChange={(e) => setBrand(e.target.value)}
          style={{ width: "100%", marginBottom: 14 }}
        />
        <h3 className="section-title">{L("offer_discount")}</h3>
        <input
          className="input"
          value={discount}
          onChange={(e) => setDiscount(e.target.value)}
          style={{ width: "100%", marginBottom: 14 }}
          placeholder="50% / 100 EGP"
        />
        <h3 className="section-title">{L("offer_validity")}</h3>
        <input
          className="input"
          type="date"
          value={validity}
          onChange={(e) => setValidity(e.target.value)}
          style={{ width: "100%", marginBottom: 14 }}
        />
      </div>
    </div>
  );
}

// ============ Promo Codes Tab (Phase 4) ============

function PromosTab({ L }) {
  const [codes, setCodes] = useState(null);
  const [form, setForm] = useState({
    code: "",
    discount_type: "percentage",
    discount_value: 20,
    valid_from: new Date().toISOString().split("T")[0],
    valid_until: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
    max_uses: "",
  });
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await api.listPromoCodes();
      setCodes(r.codes);
    } catch {
      setCodes([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function create(e) {
    e.preventDefault();
    if (!form.code.trim() || saving) return;
    setSaving(true);
    setResult(null);
    try {
      await api.createPromoCode({
        code: form.code.toUpperCase(),
        discount_type: form.discount_type,
        discount_value: parseFloat(form.discount_value),
        valid_from: new Date(form.valid_from + "T00:00:00").toISOString(),
        valid_until: new Date(form.valid_until + "T23:59:59").toISOString(),
        max_uses: form.max_uses ? parseInt(form.max_uses) : null,
      });
      setForm({
        code: "",
        discount_type: "percentage",
        discount_value: 20,
        valid_from: new Date().toISOString().split("T")[0],
        valid_until: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
        max_uses: "",
      });
      await load();
      setResult({ ok: true, msg: L("promo_create") + " ✓" });
    } catch (e) {
      setResult({ ok: false, msg: e.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid" style={{ gridTemplateColumns: "1fr 1.4fr", gap: 16, alignItems: "start" }}>
      <form className="card" onSubmit={create}>
        <h3 className="section-title">{L("promo_create")}</h3>
        <input
          className="input"
          placeholder={L("promo_code")}
          value={form.code}
          onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
          style={{ width: "100%", marginBottom: 10 }}
        />
        <select
          className="select"
          value={form.discount_type}
          onChange={(e) => setForm({ ...form, discount_type: e.target.value })}
          style={{ width: "100%", marginBottom: 10 }}
        >
          <option value="percentage">{L("promo_percentage")}</option>
          <option value="fixed">EGP ({L("promo_fixed")})</option>
        </select>
        <input
          className="input"
          type="number"
          placeholder={L("offer_discount")}
          value={form.discount_value}
          onChange={(e) => setForm({ ...form, discount_value: parseFloat(e.target.value) || 0 })}
          style={{ width: "100%", marginBottom: 10 }}
        />
        <input
          className="input"
          type="date"
          value={form.valid_from}
          onChange={(e) => setForm({ ...form, valid_from: e.target.value })}
          style={{ width: "100%", marginBottom: 10 }}
        />
        <input
          className="input"
          type="date"
          value={form.valid_until}
          onChange={(e) => setForm({ ...form, valid_until: e.target.value })}
          style={{ width: "100%", marginBottom: 10 }}
        />
        <input
          className="input"
          type="number"
          placeholder={L("promo_max_uses") + " (optional)"}
          value={form.max_uses}
          onChange={(e) => setForm({ ...form, max_uses: e.target.value })}
          style={{ width: "100%", marginBottom: 10 }}
        />
        <button className="btn primary" type="submit" disabled={saving || !form.code.trim()} style={{ width: "100%" }}>
          {L("promo_create")}
        </button>
        {result && (
          <p className={`badge ${result.ok ? "ok" : "danger"}`} style={{ marginTop: 10, display: "block", padding: 8 }}>
            {result.msg}
          </p>
        )}
      </form>

      <div className="card">
        <h3 className="section-title">{L("promo_list")}</h3>
        {codes === null && <p className="muted">…</p>}
        {codes?.length === 0 && <p className="muted">—</p>}
        {codes?.map((c, idx) => (
          <div key={idx} style={{ borderBottom: "1px solid var(--border)", padding: "10px 0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <strong>{c.code}</strong>
              <span className="badge muted">
                {c.discount_type === "percentage" ? `${c.discount_value}%` : `${c.discount_value} EGP`}
              </span>
              <span className={`badge ${c.status === "active" ? "ok" : "muted"}`}>{c.status}</span>
              <span className="badge muted">{c.current_uses}/{c.max_uses || "∞"}</span>
            </div>
            <p className="muted" style={{ fontSize: 12, margin: "6px 0 0" }}>
              {c.description_ar || c.description_en || "—"}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
