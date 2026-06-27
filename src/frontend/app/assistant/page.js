"use client";

import { useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

const EXAMPLES_AR = [
  "كام باعت الصيدلية النهارده؟",
  "إيه الأدوية اللي هتخلص الأسبوع الجاي؟",
  "اعملي طلب شراء للأصناف الناقصة",
  "مين العملاء اللي تجاوزوا حد الائتمان؟",
  "أكتر صنف مبيعاً الشهر ده",
  "ربح الشهر كام؟",
  "إيه بديل بانادول المتوفر؟",
];
const EXAMPLES_EN = [
  "How much did we sell today?",
  "Which drugs expire next week?",
  "Draft a purchase order for low-stock items",
  "Which customers are over their credit limit?",
  "Top-selling product this month",
  "What is this month's profit?",
  "What's an in-stock alternative to Panadol?",
];

export default function AssistantPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);

  const examples = lang === "ar" ? EXAMPLES_AR : EXAMPLES_EN;

  async function send(text) {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "you", text: q }]);
    setBusy(true);
    try {
      const r = await api.chat(q, branch, lang);
      setMessages((m) => [...m, { role: "assistant", text: r.answer, engine: r.engine, data: r.data, intent: r.intent }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: e.message, error: true }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell titleKey="nav_assistant">
      <div className="grid" style={{ gridTemplateColumns: "1fr 280px" }}>
        <div className="card" style={{ display: "flex", flexDirection: "column", minHeight: 480 }}>
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
            {messages.length === 0 && <p className="muted">{L("assistant_intro")}</p>}
            {messages.map((m, i) => (
              <div
                key={i}
                style={{
                  alignSelf: m.role === "you" ? "flex-end" : "flex-start",
                  maxWidth: "80%",
                  background: m.role === "you" ? "color-mix(in srgb, var(--accent) 16%, transparent)" : "var(--bg)",
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  padding: "10px 14px",
                }}
              >
                <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
                  {m.role === "you" ? L("you") : L("assistant")}
                  {m.engine ? ` · ${L("powered_by")}: ${m.engine}` : ""}
                </div>
                <div className={m.error ? "badge danger" : ""}>{m.text}</div>
                {Array.isArray(m.data) && m.data.length > 0 && (
                  <ul style={{ margin: "8px 0 0", paddingInlineStart: 18, fontSize: 13 }} className="muted">
                    {m.data.slice(0, 5).map((d, j) => (
                      <li key={j}>
                        {d.name_ar || d.name_en || d.cashier || JSON.stringify(d).slice(0, 60)}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {busy && <p className="muted">{L("loading")}</p>}
          </div>

          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <input
              className="input"
              style={{ flex: 1 }}
              value={input}
              placeholder={L("ask") + "…"}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
            />
            <button className="btn primary" onClick={() => send()} disabled={busy}>
              {L("ask")}
            </button>
          </div>
        </div>

        <div className="card">
          <h3 className="section-title">{L("examples")}</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {examples.map((ex) => (
              <button key={ex} className="btn" style={{ textAlign: "start" }} onClick={() => send(ex)}>
                {ex}
              </button>
            ))}
          </div>
        </div>
      </div>
    </Shell>
  );
}
