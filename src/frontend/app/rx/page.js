"use client";

// RX home: start a count, or resume an open one. Deliberately the shortest path
// to scanning — for the counter this is the app's front door.

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

// Cycle counts first, full count last. Small scoped counts beat an annual full
// count on both accuracy and staff time — and they are the ones that stay
// usable on a phone, where a 35k-line sheet is not.
const TYPES = [
  { value: "periodic", key: "stk_periodic" },
  { value: "stagnant", key: "stk_stagnant" },
  { value: "partial", key: "stk_partial" },
  { value: "full", key: "stk_full" },
];

export default function RXHome() {
  const router = useRouter();
  const { lang, branch, branches, user } = useUI();
  const L = (k) => t(lang, k);

  const [counts, setCounts] = useState(null);
  const [type, setType] = useState("periodic");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await api.stockCounts(branch);
      setCounts(r.counts || []);
    } catch {
      setCounts([]);
    }
  }, [branch]);

  useEffect(() => {
    load();
  }, [load]);

  async function create() {
    const branchId = Number(branch) || branches?.[0]?.branch_id || 1;
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.createStockCount({
        branch_id: branchId,
        count_type: type === "stagnant" ? "partial" : type,
        scope: type === "stagnant" ? "stagnant" : undefined,
        created_by: user?.employee_id ?? null,
      });
      router.push(`/rx/count/${r.count_id}`);
    } catch (e) {
      setMsg({ kind: "danger", text: e?.message || String(e) });
      setBusy(false);
    }
  }

  const open = (counts || []).filter((c) => c.status === "open");

  return (
    <div>
      <div className="rx-card">
        <b style={{ fontSize: 17 }}>{L("stk_new")}</b>
        <div style={{ height: 10 }} />
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {TYPES.map((tp) => (
            <option key={tp.value} value={tp.value}>
              {L(tp.key)}
            </option>
          ))}
        </select>
        <div style={{ height: 8 }} />
        <button className="rx-btn primary" disabled={busy} onClick={create}>
          {busy ? L("loading") : `📷 ${L("rx_start_counting")}`}
        </button>
        {msg && (
          <>
            <div style={{ height: 8 }} />
            <span className="rx-chip danger">{msg.text}</span>
          </>
        )}
      </div>

      <div className="rx-card">
        <b>{L("rx_open_sessions")}</b>
        {counts === null && <div className="rx-muted">{L("loading")}</div>}
        {counts !== null && open.length === 0 && (
          <div className="rx-muted">{L("stk_none_open")}</div>
        )}
        {open.map((c) => (
          <div
            key={c.count_id}
            className="rx-list-item"
            role="button"
            onClick={() => router.push(`/rx/count/${c.count_id}`)}
          >
            <div>
              <b>#{c.count_id}</b> · {c.branch}
              <div className="rx-muted">{L(`stk_${c.count_type}`)}</div>
            </div>
            <span className="rx-chip">
              {c.counted}/{c.lines}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
