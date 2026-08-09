"use client";

// Mobile stocktaking scan mode (الجرد بالباركود). Scan an item barcode with the
// phone camera, jump straight to its count line, key the physical quantity on a
// big numeric field, save, and scan the next item — instead of scrolling a sheet
// of hundreds of rows to find each item by hand.
//
// Uses the native `BarcodeDetector` (no external library, no CDN — the pharmacy
// LAN may have no internet). Egyptian packs carry a GS1 DataMatrix under the EDA
// track-and-trace mandate, so `data_matrix` is requested first: the backend
// parses the GS1 payload and pins the exact BATCH via the encoded expiry.
//
// Three capture tiers, all always available:
//   1. live camera  — needs a secure context (HTTPS or localhost)
//   2. snapshot     — <input capture>, works over plain HTTP on the LAN
//   3. manual entry — always
// Tier 2 matters: on a LAN IP `getUserMedia` is blocked, but the OS camera app
// still returns an image we can decode.

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

// Order matters only for readability; detection is format-agnostic.
const WANTED_FORMATS = [
  "data_matrix", // GS1 2D on pharma packs (GTIN + batch + expiry)
  "qr_code",
  "ean_13",
  "ean_8",
  "code_128",
  "code_39",
  "upc_a",
  "upc_e",
];

// `new BarcodeDetector({formats})` THROWS if any format is unknown to the
// device, which would kill scanning entirely. Always intersect with what the
// device actually reports.
async function makeDetector() {
  if (typeof window === "undefined" || !("BarcodeDetector" in window)) return null;
  let supported = [];
  try {
    supported = await window.BarcodeDetector.getSupportedFormats();
  } catch {
    return null;
  }
  const formats = WANTED_FORMATS.filter((f) => supported.includes(f));
  if (!formats.length) return null;
  try {
    return new window.BarcodeDetector({ formats });
  } catch {
    return null;
  }
}

export default function StockScanMode({ countId, lang, L, onSaved }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const detectorRef = useRef(null);
  const loopRef = useRef(null);
  const fileRef = useRef(null);

  const [scanning, setScanning] = useState(false);
  const [code, setCode] = useState("");
  const [match, setMatch] = useState(null);
  const [qty, setQty] = useState({});
  const [savedCount, setSavedCount] = useState(0);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  const stopCamera = useCallback(() => {
    if (loopRef.current) {
      clearInterval(loopRef.current);
      loopRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setScanning(false);
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  // Resolve a scanned/typed code against this count session.
  const lookup = useCallback(
    async (raw) => {
      const c = (raw || "").trim();
      if (!c || busy) return;
      setBusy(true);
      setMsg(null);
      try {
        const r = await api.scanStockCount(countId, c);
        if (r.result === "found") {
          setMatch(r);
          setQty({});
          // An expiry that matches no booked batch means a pack that isn't in
          // the books — worth flagging, never worth blocking the count.
          setMsg(r.expiry_mismatch ? { kind: "warn", text: L("stk_scan_expiry_mismatch") } : null);
        } else if (r.result === "not_in_count") {
          setMatch(r);
          setMsg({ kind: "warn", text: L("stk_scan_not_in_count") });
        } else {
          setMatch(null);
          setMsg({ kind: "danger", text: L("stk_scan_unknown") });
        }
      } catch (e) {
        setMsg({ kind: "danger", text: e?.message || String(e) });
      }
      setCode("");
      setBusy(false);
    },
    [countId, busy, L]
  );

  const onDetected = useCallback(
    (value) => {
      if (!value) return;
      if (navigator.vibrate) navigator.vibrate(60); // haptic: eyes stay on the shelf
      lookup(value);
    },
    [lookup]
  );

  // Tier 1 — live camera.
  const startCamera = useCallback(async () => {
    const detector = await makeDetector();
    if (!detector) {
      setMsg({ kind: "warn", text: L("stk_scan_unsupported") });
      return;
    }
    detectorRef.current = detector;
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
          if (codes && codes.length && codes[0].rawValue) {
            stopCamera();
            onDetected(codes[0].rawValue);
          }
        } catch {
          /* transient decode failure — keep polling */
        }
      }, 350);
    } catch {
      // Insecure context (LAN IP) or permission denied — tiers 2 and 3 remain.
      setMsg({ kind: "warn", text: L("stk_scan_camera_denied") });
      stopCamera();
    }
  }, [L, onDetected, stopCamera]);

  // Tier 2 — snapshot via the OS camera app. Works without a secure context.
  async function onSnapshot(e) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file
    if (!file) return;
    const detector = detectorRef.current || (await makeDetector());
    if (!detector) {
      setMsg({ kind: "warn", text: L("stk_scan_unsupported") });
      return;
    }
    detectorRef.current = detector;
    try {
      const bitmap = await createImageBitmap(file);
      const codes = await detector.detect(bitmap);
      bitmap.close?.();
      if (codes && codes.length && codes[0].rawValue) onDetected(codes[0].rawValue);
      else setMsg({ kind: "warn", text: L("stk_scan_no_code_in_photo") });
    } catch {
      setMsg({ kind: "warn", text: L("stk_scan_no_code_in_photo") });
    }
  }

  async function saveLine(line) {
    const v = qty[line.line_id];
    if (v === undefined || v === "") return;
    setBusy(true);
    setMsg(null);
    try {
      await api.saveStockCountLines(countId, [
        { line_id: line.line_id, counted_qty: Number(v) },
      ]);
      setSavedCount((n) => n + 1);
      setMsg({ kind: "ok", text: L("stk_saved") });
      setQty((q) => {
        const next = { ...q };
        delete next[line.line_id];
        return next;
      });
      setMatch(null); // clear the card so the next scan starts clean
      onSaved?.();
    } catch (e) {
      setMsg({ kind: "danger", text: e?.message || String(e) });
    }
    setBusy(false);
  }

  const label = (p) => (lang === "ar" ? p.name_ar : p.name_en || p.name_ar);
  const scan = match?.scan;

  return (
    <div className="card" style={{ display: "grid", gap: 14 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        {!scanning ? (
          <button className="btn primary" disabled={busy} onClick={startCamera}>
            {L("stk_scan_start")}
          </button>
        ) : (
          <button className="btn danger" onClick={stopCamera}>
            {L("stk_scan_stop")}
          </button>
        )}
        <button className="btn" disabled={busy} onClick={() => fileRef.current?.click()}>
          {L("stk_scan_photo")}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={onSnapshot}
          style={{ display: "none" }}
        />
        <span className="badge ok">
          {savedCount} {L("stk_scan_saved_count")}
        </span>
        {msg && (
          <span className={`badge ${msg.kind === "ok" ? "ok" : msg.kind === "warn" ? "warn" : "danger"}`}>
            {msg.text}
          </span>
        )}
      </div>

      {scanning && (
        <div
          style={{
            position: "relative",
            width: "100%",
            maxWidth: 420,
            margin: "0 auto",
            borderRadius: 12,
            overflow: "hidden",
            background: "#000",
          }}
        >
          <video ref={videoRef} playsInline muted style={{ width: "100%", display: "block" }} />
          <div
            style={{
              position: "absolute",
              top: "40%",
              insetInline: "8%",
              height: 2,
              background: "var(--accent, #0a7d5a)",
              boxShadow: "0 0 8px var(--accent, #0a7d5a)",
            }}
          />
        </div>
      )}

      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="input"
          inputMode="numeric"
          placeholder={L("stk_scan_placeholder")}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") lookup(code);
          }}
          style={{ flex: 1, fontSize: 16 }}
        />
        <button className="btn" disabled={busy || !code} onClick={() => lookup(code)}>
          🔍
        </button>
      </div>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        {L("stk_scan_hint")}
      </p>

      {match?.product && (
        <div className="card" style={{ border: "2px solid var(--accent, #0a7d5a)", display: "grid", gap: 12 }}>
          <div>
            <b style={{ fontSize: 18 }}>{label(match.product)}</b>
            {match.product.shelf_location && <span className="muted"> · {match.product.shelf_location}</span>}
            <div className="muted" style={{ fontSize: 13 }}>
              {match.product.code || match.product.fast_code}
              {match.product.unit_big ? ` · ${match.product.unit_big}` : ""}
            </div>
            {/* GS1 packs carry batch + expiry: show what was actually read. */}
            {scan?.kind === "gs1" && (
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                GS1
                {scan.expiry ? ` · ${L("stk_scan_exp")} ${scan.expiry}` : ""}
                {scan.lot ? ` · ${L("stk_scan_batch")} ${scan.lot}` : ""}
              </div>
            )}
          </div>

          {match.result === "not_in_count" ? (
            <span className="badge warn">{L("stk_scan_not_in_count")}</span>
          ) : (
            (match.lines || []).map((line) => (
              <div
                key={line.line_id}
                style={{
                  display: "grid",
                  gap: 8,
                  padding: 10,
                  borderRadius: 10,
                  background: "var(--bg-tertiary, rgba(0,0,0,0.04))",
                  // The batch the scanned expiry pinned — highlight it so the
                  // right row is obvious when a product has several batches.
                  outline: line.batch_match ? "2px solid var(--ok, #0a0)" : "none",
                }}
              >
                <div className="muted" style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                  <span>
                    {L("stk_scan_expected")}: <b>{line.expected_qty}</b>
                  </span>
                  {line.exp_date && (
                    <span>
                      {L("stk_scan_exp")}: {line.exp_date}
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    className="input"
                    type="number"
                    min="0"
                    step="any"
                    inputMode="decimal"
                    enterKeyHint="done"
                    autoFocus={line.batch_match !== false}
                    placeholder={L("stk_scan_qty")}
                    value={qty[line.line_id] ?? ""}
                    onChange={(e) => setQty((q) => ({ ...q, [line.line_id]: e.target.value }))}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveLine(line);
                    }}
                    style={{ flex: 1, fontSize: 24, textAlign: "center", padding: 12, minHeight: 56 }}
                  />
                  <button
                    className="btn primary"
                    disabled={busy || (qty[line.line_id] ?? "") === ""}
                    onClick={() => saveLine(line)}
                    style={{ fontSize: 16, padding: "12px 16px", minHeight: 56 }}
                  >
                    {L("stk_scan_save_next")}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
