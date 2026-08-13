"use client";

// "لم يُرفع" — everything still queued or rejected.
//
// This screen exists because the queue is honest rather than silent: a count
// that never reached the server must be visible and actionable, not quietly
// dropped. Terminal failures (a manager posted the count while you were
// offline, a line that vanished in a sync) need a human, so they are shown
// with their reason rather than retried forever.

import { useCallback, useEffect, useState } from "react";
import { useUI } from "../../providers";
import { t } from "../../i18n";
import { flush, onOutboxChange, outboxSummary } from "../../lib/outbox";
import { clearFailed } from "../../lib/rxdb";

export default function RXUnsentPage() {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  const [summary, setSummary] = useState({ pending: 0, failed: 0, rows: [] });
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => setSummary(await outboxSummary()), []);

  useEffect(() => {
    const off = onOutboxChange(setSummary);
    refresh();
    return off;
  }, [refresh]);

  async function retryAll() {
    setBusy(true);
    setSummary(await flush());
    setBusy(false);
  }

  async function discardFailed() {
    if (!window.confirm(L("rx_discard_confirm"))) return;
    setBusy(true);
    await clearFailed();
    await refresh();
    setBusy(false);
  }

  const rows = summary.rows || [];

  return (
    <div>
      <div className="rx-card">
        <b>{L("rx_unsent_title")}</b>
        <div className="rx-muted">{L("rx_unsent_hint")}</div>
        <div style={{ height: 10 }} />
        <div className="rx-row">
          <span className="rx-chip warn">⏳ {summary.pending}</span>
          <span className="rx-chip danger">⚠ {summary.failed}</span>
          {summary.paused && <span className="rx-chip danger">{L("rx_session_expired")}</span>}
        </div>
        <div style={{ height: 10 }} />
        <button className="rx-btn primary" disabled={busy || !rows.length} onClick={retryAll}>
          {L("rx_retry_now")}
        </button>
        {summary.failed > 0 && (
          <>
            <div style={{ height: 8 }} />
            <button className="rx-btn danger" disabled={busy} onClick={discardFailed}>
              {L("rx_discard_failed")}
            </button>
          </>
        )}
      </div>

      {rows.length === 0 && <div className="rx-card rx-muted">{L("rx_all_synced")}</div>}

      {rows.map((row) => (
        <div className="rx-card" key={row.id}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
            <b>{L(`rx_kind_${row.kind}`)}</b>
            <span className={`rx-chip ${row.state === "failed" ? "danger" : "warn"}`}>
              {row.state === "failed" ? "⚠" : "⏳"}
            </span>
          </div>
          <div className="rx-muted">{row.url}</div>
          {row.last_error && <div className="rx-muted">{row.last_error}</div>}
          {row.attempts > 0 && (
            <div className="rx-muted">
              {L("rx_attempts")}: {row.attempts}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
