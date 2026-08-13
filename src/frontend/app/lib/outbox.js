// Outbox replay for ProCare RX.
//
// Lives in the PAGE, not in a service worker, for two reasons:
//  1. Scope. /api/* sits under the root worker's scope "/", not /rx/ — a fetch
//     handler in the RX worker would silently never fire for API calls.
//  2. Honesty. Intercepting means handing the UI a synthetic 202 for a question
//     it actually asked, so it can no longer tell "saved on the server" from
//     "sitting in a queue". For الجرد, where the point is trusting the number,
//     that distinction IS the product — so each line shows pending / synced /
//     failed truthfully.
//
// Only absolute-state writes are queued (a counted quantity, a task status, a
// barcode link). Every one of them is idempotent server-side, which is why no
// idempotency-key machinery is needed. Creating a count and POSTING a count are
// deliberately online-only: the first needs a server-assigned id and snapshot,
// the second applies deltas against live stock and is a manager's decision
// against current data.

import { API_BASE, session } from "../api";
import { allQueued, enqueue, removeQueued, updateQueued } from "./rxdb";

const MAX_BACKOFF_MS = 5 * 60 * 1000;

let flushing = false;
let paused = false; // set on 401 until the user logs in again
const listeners = new Set();

export function onOutboxChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

async function notify() {
  const rows = await allQueued();
  const summary = {
    pending: rows.filter((r) => r.state !== "failed").length,
    failed: rows.filter((r) => r.state === "failed").length,
    paused,
    rows,
  };
  listeners.forEach((fn) => {
    try {
      fn(summary);
    } catch {
      /* a bad listener must not break the queue */
    }
  });
  return summary;
}

export async function queueCountLine(countId, line, countedQty) {
  await enqueue({
    kind: "count_line",
    // One queued row per LINE, so repeated edits collapse instead of stacking.
    dedupe_key: `count:${countId}:line:${line.line_id}`,
    count_id: Number(countId),
    url: `/stocktaking/${countId}/lines`,
    body: {
      entries: [
        {
          line_id: line.line_id,
          counted_qty: Number(countedQty),
          // What this device believed the server held, so a colleague counting
          // the same shelf comes back as a reported conflict rather than a
          // silent overwrite.
          base_counted_qty: line.counted_qty ?? null,
        },
      ],
    },
    label: line.label || null,
  });
  return notify();
}

export async function queueTaskStatus(taskId, status) {
  await enqueue({
    kind: "task_status",
    dedupe_key: `task:${taskId}`,
    count_id: null,
    url: `/tasks/${taskId}/status`,
    body: { status },
  });
  return notify();
}

export async function queueBarcodeLink(countId, code, productId, employeeId) {
  await enqueue({
    kind: "gtin_link",
    dedupe_key: `gtin:${code}`,
    count_id: Number(countId),
    url: `/stocktaking/${countId}/scan/link`,
    body: { code, product_id: productId, employee_id: employeeId ?? null },
  });
  return notify();
}

async function send(row) {
  const token = session.get()?.token;
  return fetch(`${API_BASE}/api${row.url}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(row.body),
  });
}

/**
 * Drain the queue, oldest first, one request at a time.
 *
 * Retry classification follows etl.py's discipline — only the network class is
 * retried, never a data error — but deliberately NOT its 3-attempt cap: an ETL
 * can abandon a chunk and re-pull next cycle, whereas this queue may hold the
 * only copy of a count someone physically walked a shelf to produce.
 */
export async function flush() {
  if (flushing || paused) return notify();
  if (typeof navigator !== "undefined" && navigator.onLine === false) return notify();
  flushing = true;
  try {
    const rows = (await allQueued())
      .filter((r) => r.state !== "failed")
      .sort((a, b) => (a.id || 0) - (b.id || 0));
    const now = Date.now();
    for (const row of rows) {
      if (row.next_attempt_at && row.next_attempt_at > now) continue;
      let res;
      try {
        res = await send(row);
      } catch {
        // Offline or DNS/TLS failure — retry with backoff, keep the row.
        await backoff(row, null, "network");
        break; // no point hammering the rest while the link is down
      }
      if (res.ok) {
        await removeQueued(row.id);
        continue;
      }
      if (res.status === 401) {
        // The 12h token expired mid-shift (there is no refresh token). Do not
        // burn attempts or mark anything failed — hold everything and let the
        // UI prompt for a re-login.
        paused = true;
        break;
      }
      if (res.status >= 400 && res.status < 500) {
        // Terminal: count_closed (a manager posted while we were offline),
        // validation, a vanished line. A human has to look at these.
        let detail = null;
        try {
          detail = (await res.json()).detail;
        } catch {
          /* body may not be JSON */
        }
        await updateQueued({
          ...row,
          state: "failed",
          last_status: res.status,
          last_error:
            (typeof detail === "string" ? detail : detail?.message) || `HTTP ${res.status}`,
        });
        continue;
      }
      await backoff(row, res.status, `HTTP ${res.status}`);
      break;
    }
  } finally {
    flushing = false;
  }
  return notify();
}

async function backoff(row, status, message) {
  const attempts = (row.attempts || 0) + 1;
  await updateQueued({
    ...row,
    attempts,
    // Persisted, so a reload cannot reset the backoff and start hammering.
    next_attempt_at: Date.now() + Math.min(2 ** attempts * 2000, MAX_BACKOFF_MS),
    last_status: status,
    last_error: message,
  });
}

/** Call after a successful re-login to resume a queue paused by a 401. */
export function resumeAfterLogin() {
  paused = false;
  return flush();
}

export function isPaused() {
  return paused;
}

/**
 * Flush on the events that actually mean "we might be back": regaining
 * connectivity, returning to the app, and a slow heartbeat while in the
 * foreground. Returns a cleanup function.
 */
export function startAutoFlush(intervalMs = 30000) {
  if (typeof window === "undefined") return () => {};
  const onOnline = () => flush();
  const onVisible = () => {
    if (document.visibilityState === "visible") flush();
  };
  window.addEventListener("online", onOnline);
  document.addEventListener("visibilitychange", onVisible);
  const timer = setInterval(() => {
    if (document.visibilityState === "visible") flush();
  }, intervalMs);
  flush();
  return () => {
    window.removeEventListener("online", onOnline);
    document.removeEventListener("visibilitychange", onVisible);
    clearInterval(timer);
  };
}

export const outboxSummary = notify;
