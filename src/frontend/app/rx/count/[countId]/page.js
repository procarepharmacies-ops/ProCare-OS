"use client";

// The count screen — the whole point of ProCare RX.
//
// Scan a pack -> the matching count line opens with the book quantity shown ->
// key the physical count -> save -> the camera reopens for the next pack. No
// scrolling a sheet of hundreds of rows to find each item by hand.
//
// A GS1 DataMatrix additionally pins the exact BATCH via its encoded expiry,
// so a product with four expiries lands on one row instead of asking the
// counter to choose.

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useUI } from "../../../providers";
import { t } from "../../../i18n";
import { api } from "../../../api";
import { makeDetector, detectFromFile, cameraAvailable } from "../../../lib/scanner";
import { resolveOffline } from "../../../lib/gs1";
import { saveSheet, loadSheet as loadCachedSheet, saveScanIndex, loadScanIndex } from "../../../lib/rxdb";
import {
  queueCountLine,
  queueBarcodeLink,
  flush,
  startAutoFlush,
  onOutboxChange,
  outboxSummary,
} from "../../../lib/outbox";

// Keep the cached index in step with what was just entered, so re-scanning the
// same pack offline shows the counted value rather than a stale null.
function applyCountedLocally(index, lineId, countedQty) {
  if (!index?.items) return index;
  return {
    ...index,
    items: index.items.map((item) => ({
      ...item,
      lines: item.lines.map((l) =>
        l.line_id === lineId ? { ...l, counted_qty: countedQty } : l
      ),
    })),
  };
}

// A barcode linked while offline must resolve on the very next scan.
function applyLinkLocally(index, code, productId) {
  if (!index?.items) return index;
  return {
    ...index,
    items: index.items.map((item) =>
      item.product_id === productId && !(item.codes || []).includes(code)
        ? { ...item, codes: [...(item.codes || []), code] }
        : item
    ),
  };
}

export default function RXCountPage() {
  const { countId } = useParams();
  const router = useRouter();
  const { lang, user } = useUI();
  const L = (k) => t(lang, k);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const detectorRef = useRef(null);
  const loopRef = useRef(null);
  const fileRef = useRef(null);

  const [sheet, setSheet] = useState(null);
  const [index, setIndex] = useState(null); // cached code -> line index
  const [queue, setQueue] = useState({ pending: 0, failed: 0 });
  const [scanning, setScanning] = useState(false);
  const [code, setCode] = useState("");
  const [match, setMatch] = useState(null);
  const [qty, setQty] = useState("");
  const [activeLine, setActiveLine] = useState(null);
  const [saved, setSaved] = useState(0);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  // Network first, cache as we go, fall back to the cache when the shelf has
  // no signal. The counter should never be blocked by a dead spot.
  const loadSheet = useCallback(async () => {
    try {
      const fresh = await api.stockCountDetail(countId);
      setSheet(fresh);
      saveSheet(countId, fresh);
    } catch {
      const cached = await loadCachedSheet(countId);
      if (cached) setSheet(cached);
      else setMsg({ kind: "danger", text: L("rx_no_cached_sheet") });
    }
  }, [countId, L]);

  // The scan index is what makes scanning work offline: every code a product
  // can be scanned by, plus its per-batch lines.
  const loadIndex = useCallback(async () => {
    try {
      const fresh = await api.stockScanIndex(countId);
      setIndex(fresh);
      saveScanIndex(countId, fresh);
    } catch {
      setIndex(await loadScanIndex(countId));
    }
  }, [countId]);

  useEffect(() => {
    loadSheet();
    loadIndex();
  }, [loadSheet, loadIndex]);

  // Keep the queue badge honest, and drain whenever we plausibly reconnect.
  useEffect(() => {
    const off = onOutboxChange(setQueue);
    const stop = startAutoFlush();
    outboxSummary().then(setQueue);
    return () => {
      off();
      stop();
    };
  }, []);

  const stopCamera = useCallback(() => {
    if (loopRef.current) {
      clearInterval(loopRef.current);
      loopRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((tr) => tr.stop());
      streamRef.current = null;
    }
    setScanning(false);
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  const lookup = useCallback(
    async (raw) => {
      const c = (raw || "").trim();
      if (!c) return;
      setBusy(true);
      setMsg(null);
      try {
        let r;
        try {
          r = await api.scanStockCount(countId, c);
        } catch {
          // No signal: resolve against the cached index with the same parser
          // the server uses, so the result shape is identical either way.
          if (!index) throw new Error(L("rx_no_cached_index"));
          r = resolveOffline(index, c);
        }
        if (r.result === "unknown") {
          setMatch(r);
          setActiveLine(null);
          setMsg({ kind: "danger", text: L("stk_scan_unknown") });
        } else if (r.result === "not_in_count") {
          setMatch(r);
          setActiveLine(null);
          setMsg({ kind: "warn", text: L("stk_scan_not_in_count") });
        } else {
          setMatch(r);
          // A GS1 expiry pins one batch; otherwise start on the FEFO-first line.
          const line =
            r.lines.find((l) => l.line_id === r.matched_line_id) || r.lines[0];
          setActiveLine(line);
          setQty("");
          setMsg(
            r.expiry_mismatch ? { kind: "warn", text: L("stk_scan_expiry_mismatch") } : null
          );
        }
      } catch (e) {
        setMsg({ kind: "danger", text: e?.message || String(e) });
      }
      setCode("");
      setBusy(false);
    },
    [countId, L, index]
  );

  const onDetected = useCallback(
    (value) => {
      if (!value) return;
      if (navigator.vibrate) navigator.vibrate(60); // eyes stay on the shelf
      lookup(value);
    },
    [lookup]
  );

  const startCamera = useCallback(async () => {
    const detector = detectorRef.current || (await makeDetector());
    if (!detector) {
      setMsg({ kind: "warn", text: L("stk_scan_unsupported") });
      return;
    }
    detectorRef.current = detector;
    if (!cameraAvailable()) {
      // Plain-HTTP LAN address: getUserMedia is blocked, photo tier still works.
      setMsg({ kind: "warn", text: L("rx_camera_needs_https") });
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setScanning(true);
      loopRef.current = setInterval(async () => {
        if (!videoRef.current || !detectorRef.current) return;
        try {
          const codes = await detectorRef.current.detect(videoRef.current);
          if (codes?.length && codes[0].rawValue) {
            stopCamera();
            onDetected(codes[0].rawValue);
          }
        } catch {
          /* transient decode failure — keep polling */
        }
      }, 350);
    } catch {
      setMsg({ kind: "warn", text: L("stk_scan_camera_denied") });
      stopCamera();
    }
  }, [L, onDetected, stopCamera]);

  async function onPhoto(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const detector = detectorRef.current || (await makeDetector());
    if (!detector) {
      setMsg({ kind: "warn", text: L("stk_scan_unsupported") });
      return;
    }
    detectorRef.current = detector;
    const value = await detectFromFile(detector, file);
    if (value) onDetected(value);
    else setMsg({ kind: "warn", text: L("stk_scan_no_code_in_photo") });
  }

  // Optimistic: the count goes into the durable queue first, the UI moves on
  // immediately, and the badge shows ⏳ until the flush confirms. Writes are
  // absolute quantities, so a replay lands on the same number — that is what
  // makes queueing safe without any idempotency key.
  async function save() {
    if (!activeLine || qty === "") return;
    setBusy(true);
    setMsg(null);
    const counted = Number(qty);
    try {
      setQueue(await queueCountLine(countId, activeLine, counted));
      setSaved((n) => n + 1);

      // Reflect it locally so a re-scan of the same pack shows what we just
      // entered even while the request is still in flight (or offline).
      setIndex((prev) => applyCountedLocally(prev, activeLine.line_id, counted));

      setMatch(null);
      setActiveLine(null);
      setQty("");
      const summary = await flush();
      setQueue(summary);
      if (summary.paused) setMsg({ kind: "warn", text: L("rx_session_expired") });
      loadSheet();
      // Straight back to scanning: the flow is scan -> count -> scan.
      if (cameraAvailable()) startCamera();
    } catch (e) {
      setMsg({ kind: "danger", text: e?.message || String(e) });
    }
    setBusy(false);
  }

  async function linkBarcode(productId) {
    setBusy(true);
    const code = match.code;
    try {
      // Queued like a count: linking is idempotent server-side (unique GTIN
      // index), so replaying it can never create a duplicate mapping.
      setQueue(await queueBarcodeLink(countId, code, productId, user?.employee_id));
      // Teach the local index too, so the next scan resolves offline as well.
      setIndex((prev) => applyLinkLocally(prev, code, productId));
      setMsg({ kind: "ok", text: L("rx_link_saved") });
      setQueue(await flush());
      lookup(code); // resolve again, now that it is known
    } catch (e) {
      setMsg({ kind: "danger", text: e?.message || String(e) });
    }
    setBusy(false);
  }

  const s = sheet?.summary;
  const name = (p) => (lang === "ar" ? p.name_ar : p.name_en || p.name_ar);

  return (
    <div>
      <div className="rx-row" style={{ marginBottom: 12 }}>
        <button className="rx-btn" style={{ width: 64 }} onClick={() => router.push("/rx")}>
          ←
        </button>
        <div style={{ flex: 1 }}>
          <b>
            {L("stk_sheet")} #{countId}
          </b>
          <div className="rx-muted">
            {s ? `${s.counted_lines}/${s.total_lines} ${L("stk_counted_of")}` : L("loading")}
            {saved > 0 ? ` · ${saved} ${L("rx_this_session")}` : ""}
          </div>
        </div>
        {/* Truthful per-queue state: the counter can see what has actually
            reached the server versus what is still waiting. */}
        {queue.pending > 0 && (
          <span className="rx-chip warn">⏳ {queue.pending}</span>
        )}
        {queue.failed > 0 && (
          <span className="rx-chip danger">⚠ {queue.failed}</span>
        )}
        {queue.pending === 0 && queue.failed === 0 && saved > 0 && (
          <span className="rx-chip ok">✓</span>
        )}
      </div>

      {msg && (
        <div style={{ marginBottom: 10 }}>
          <span className={`rx-chip ${msg.kind === "ok" ? "ok" : msg.kind === "warn" ? "warn" : "danger"}`}>
            {msg.text}
          </span>
        </div>
      )}

      {scanning && (
        <div className="rx-scanbox" style={{ marginBottom: 12 }}>
          <video ref={videoRef} playsInline muted />
          <div className="rx-scanline" />
        </div>
      )}

      {/* Capture tiers: live camera, OS-camera photo, typed code. All three are
          always offered — the first needs HTTPS, the second does not. */}
      {!match && (
        <div className="rx-card">
          {!scanning ? (
            <button className="rx-btn primary" disabled={busy} onClick={startCamera}>
              {L("stk_scan_start")}
            </button>
          ) : (
            <button className="rx-btn danger" onClick={stopCamera}>
              {L("stk_scan_stop")}
            </button>
          )}
          <div style={{ height: 8 }} />
          <button className="rx-btn" disabled={busy} onClick={() => fileRef.current?.click()}>
            {L("stk_scan_photo")}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={onPhoto}
            style={{ display: "none" }}
          />
          <div style={{ height: 8 }} />
          <div className="rx-row">
            <input
              inputMode="numeric"
              enterKeyHint="search"
              placeholder={L("stk_scan_placeholder")}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && lookup(code)}
            />
            <button className="rx-btn" style={{ width: 72 }} disabled={busy || !code} onClick={() => lookup(code)}>
              🔍
            </button>
          </div>
        </div>
      )}

      {/* Unknown barcode -> teach the catalogue. The person holding the box is
          the one who knows what it is. */}
      {match?.result === "unknown" && (
        <UnknownBarcode
          L={L}
          lang={lang}
          busy={busy}
          onCancel={() => setMatch(null)}
          onPick={linkBarcode}
        />
      )}

      {match?.product && match.result !== "unknown" && (
        <div className="rx-card accent">
          <b style={{ fontSize: 19 }}>{name(match.product)}</b>
          <div className="rx-muted">
            {match.product.shelf_location ? `${match.product.shelf_location} · ` : ""}
            {match.product.code || match.product.fast_code}
            {match.product.unit_big ? ` · ${match.product.unit_big}` : ""}
          </div>
          {match.scan?.kind === "gs1" && (
            <div className="rx-muted" style={{ marginTop: 4 }}>
              GS1
              {match.scan.expiry ? ` · ${L("stk_scan_exp")} ${match.scan.expiry}` : ""}
              {match.scan.lot ? ` · ${L("stk_scan_batch")} ${match.scan.lot}` : ""}
            </div>
          )}

          {match.result === "not_in_count" ? (
            <>
              <div style={{ height: 10 }} />
              <button className="rx-btn" onClick={() => setMatch(null)}>
                {L("rx_back_to_scan")}
              </button>
            </>
          ) : (
            <>
              {/* Batch picker only when the scan didn't already pin one. */}
              {match.lines.length > 1 && (
                <>
                  <div style={{ height: 10 }} />
                  <div className="rx-muted">{L("rx_pick_batch")}</div>
                  {match.lines.map((l) => (
                    <button
                      key={l.line_id}
                      className="rx-btn"
                      style={{
                        marginTop: 6,
                        borderColor:
                          activeLine?.line_id === l.line_id ? "var(--accent, #0a7d5a)" : undefined,
                        borderWidth: activeLine?.line_id === l.line_id ? 2 : 1,
                      }}
                      onClick={() => setActiveLine(l)}
                    >
                      {l.exp_date || L("rx_no_expiry")} · {L("stk_scan_expected")} {l.expected_qty}
                      {l.batch_match ? " ✅" : ""}
                    </button>
                  ))}
                </>
              )}

              {activeLine && (
                <>
                  <div style={{ height: 12 }} />
                  <div className="rx-muted">
                    {L("stk_scan_expected")}: <b>{activeLine.expected_qty}</b>
                    {activeLine.exp_date ? ` · ${L("stk_scan_exp")} ${activeLine.exp_date}` : ""}
                  </div>
                  <div style={{ height: 6 }} />
                  <input
                    className="rx-qty"
                    type="number"
                    min="0"
                    step="any"
                    inputMode="decimal"
                    enterKeyHint="done"
                    autoFocus
                    placeholder={L("stk_scan_qty")}
                    value={qty}
                    onChange={(e) => setQty(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && save()}
                  />
                  <div style={{ height: 8 }} />
                  <button className="rx-btn primary" disabled={busy || qty === ""} onClick={save}>
                    {L("stk_scan_save_next")}
                  </button>
                  <div style={{ height: 6 }} />
                  <button className="rx-btn" onClick={() => setMatch(null)}>
                    {L("rx_back_to_scan")}
                  </button>
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// Search the catalogue and attach the scanned barcode to the right product, so
// the next person who scans this pack gets an instant hit.
function UnknownBarcode({ L, lang, busy, onCancel, onPick }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);

  async function search() {
    if (!q.trim()) return;
    setSearching(true);
    try {
      const r = await api.products(0, q.trim());
      setResults((r.products || []).slice(0, 12));
    } catch {
      setResults([]);
    }
    setSearching(false);
  }

  return (
    <div className="rx-card accent">
      <b>{L("rx_link_title")}</b>
      <div className="rx-muted">{L("rx_link_hint")}</div>
      <div style={{ height: 10 }} />
      <div className="rx-row">
        <input
          enterKeyHint="search"
          placeholder={L("search")}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
        />
        <button className="rx-btn" style={{ width: 72 }} disabled={searching} onClick={search}>
          🔍
        </button>
      </div>
      {results.map((p) => (
        <button
          key={p.product_id}
          className="rx-btn"
          style={{ marginTop: 6, textAlign: "start" }}
          disabled={busy}
          onClick={() => onPick(p.product_id)}
        >
          {lang === "ar" ? p.name_ar : p.name_en || p.name_ar}
        </button>
      ))}
      <div style={{ height: 8 }} />
      <button className="rx-btn" onClick={onCancel}>
        {L("rx_back_to_scan")}
      </button>
    </div>
  );
}
