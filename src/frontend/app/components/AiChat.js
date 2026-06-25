"use client";

import { useState, useRef, useEffect } from "react";
import { useUI } from "../providers";
import { t } from "../i18n";
import { apiPost } from "../api";

const SUGGESTIONS = [
  "مبيعات النهاردة",
  "مبيعات امبارح",
  "الأصناف اللي هتخلص الأسبوع الجاي",
  "الأصناف الناقصة",
  "أكثر صنف مبيعاً",
  "العملاء اللي تجاوزوا الحد",
];

export default function AiChat({ branch }) {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  const [log, setLog] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  async function send(q) {
    const query = (q ?? input).trim();
    if (!query || busy) return;
    setInput("");
    setLog((l) => [...l, { who: "user", text: query }]);
    setBusy(true);
    try {
      const r = await apiPost("/ai/chat", { query, branch });
      setLog((l) => [...l, { who: "bot", text: r.answer, sql: r.sql, engine: r.engine }]);
    } catch (e) {
      setLog((l) => [...l, { who: "bot", text: "تعذّر الاتصال بالخادم." }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card panel">
      <h2>{L("assistant")} <span className="badge ok">{L("read_only")}</span></h2>
      <p className="panel-sub">{L("assistant_hint")}</p>

      {log.length > 0 && (
        <div className="chat-log">
          {log.map((m, i) => (
            <div key={i} className={`bubble ${m.who}`}>
              <div style={{ whiteSpace: "pre-wrap" }}>{m.text}</div>
              {m.sql && (
                <details>
                  <summary style={{ cursor: "pointer", fontSize: 11, color: "var(--muted)", marginTop: 6 }}>
                    {L("sql_used")}
                  </summary>
                  <div className="sql">{m.sql}</div>
                </details>
              )}
            </div>
          ))}
          <div ref={endRef} />
        </div>
      )}

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
        <span style={{ color: "var(--muted)", fontSize: 12, alignSelf: "center" }}>{L("try")}</span>
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chip" onClick={() => send(s)} disabled={busy}>{s}</button>
        ))}
      </div>

      <div className="chat-input">
        <input
          className="input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={L("assistant_hint")}
          disabled={busy}
        />
        <button className="btn primary" onClick={() => send()} disabled={busy}>
          {busy ? "…" : L("ask")}
        </button>
      </div>
    </div>
  );
}
