// Tiny API client for the ProCare OS backend. The base URL defaults to the
// local FastAPI server; override with NEXT_PUBLIC_API_BASE.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export async function apiGet(path) {
  const r = await fetch(`${API_BASE}/api${path}`);
  if (!r.ok) throw new Error(`GET ${path} -> ${r.status}`);
  return r.json();
}

export async function apiPost(path, body) {
  const r = await fetch(`${API_BASE}/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) throw new Error(`POST ${path} -> ${r.status}`);
  return r.json();
}

// --- formatting -------------------------------------------------------------
export function money(v, lang) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  const s = n.toLocaleString(lang === "ar" ? "ar-EG" : "en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  return s;
}

export function num(v, lang) {
  if (v === null || v === undefined) return "—";
  return Number(v).toLocaleString(lang === "ar" ? "ar-EG" : "en-US");
}

export function pct(v) {
  if (v === null || v === undefined) return null;
  const n = Number(v);
  return (n > 0 ? "+" : "") + n.toFixed(1) + "%";
}

export function pickName(row, lang, prefix = "product_name") {
  const ar = row[`${prefix}_ar`];
  const en = row[`${prefix}_en`];
  return (lang === "ar" ? ar : en) || ar || en || "—";
}
