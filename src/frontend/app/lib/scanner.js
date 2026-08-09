// Barcode capture helpers shared by the desktop scan mode and the RX app.
//
// Native BarcodeDetector only — no library, no CDN. The pharmacy LAN may have
// no internet, and a scanner that needs a CDN is a scanner that stops working
// on the day the line drops.

// data_matrix first: Egyptian pharma packs carry a GS1 DataMatrix (GTIN +
// batch + expiry) under the EDA track-and-trace mandate, which is what lets a
// scan pin the exact batch rather than just the product.
export const WANTED_FORMATS = [
  "data_matrix",
  "qr_code",
  "ean_13",
  "ean_8",
  "code_128",
  "code_39",
  "upc_a",
  "upc_e",
];

/**
 * Build a BarcodeDetector for the formats this device actually supports.
 *
 * `new BarcodeDetector({formats})` THROWS if any requested format is unknown to
 * the device, so passing a fixed list would kill scanning outright on handsets
 * that lack one of them. Returns null when scanning isn't available at all
 * (no API, or no Google Play Services on Android) — callers fall back to the
 * photo or manual-entry tiers.
 */
export async function makeDetector() {
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

/**
 * Decode a still image (from <input type="file" capture="environment">).
 *
 * This tier matters: getUserMedia needs a secure context, so the live camera is
 * blocked when staff reach the app over a plain-HTTP LAN address. A file input
 * hands off to the OS camera app instead, so it keeps working there.
 */
export async function detectFromFile(detector, file) {
  if (!detector || !file) return null;
  try {
    const bitmap = await createImageBitmap(file);
    const codes = await detector.detect(bitmap);
    bitmap.close?.();
    return codes?.[0]?.rawValue || null;
  } catch {
    return null;
  }
}

/** True when the live camera can work here (secure context required). */
export function cameraAvailable() {
  if (typeof window === "undefined") return false;
  return Boolean(window.isSecureContext && navigator.mediaDevices?.getUserMedia);
}
