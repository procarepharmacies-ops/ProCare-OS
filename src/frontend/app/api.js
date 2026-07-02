// Thin API client for the ProCare backend. All calls are read-only except the
// POS endpoints. Base URL is configurable for deployment.
// Base URL for the backend. An empty string means "same origin" — used in the
// containerized deployment, where Next.js proxies /api to the backend
// server-side (see next.config.mjs), so the browser never needs the backend's
// address and there is no CORS hop. `??` (not `||`) so an explicit "" is kept.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

const SESSION_KEY = "procare.session";

// Session (token + employee) persistence — read by every request so
// authenticated calls carry the Bearer token automatically.
export const session = {
  get: () => {
    if (typeof window === "undefined") return null;
    try {
      const raw = localStorage.getItem(SESSION_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },
  set: (data) => localStorage.setItem(SESSION_KEY, JSON.stringify(data)),
  clear: () => localStorage.removeItem(SESSION_KEY),
};

async function http(path, options) {
  const token = session.get()?.token;
  const res = await fetch(`${API_BASE}/api${path}`, {
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    const err = new Error(typeof detail === "string" ? detail : detail?.message || "Request failed");
    err.detail = detail;
    throw err;
  }
  return res.json();
}

// Append branch_id only when a specific branch is selected (0 = consolidated).
function bq(branch, extra = "") {
  const p = new URLSearchParams();
  if (branch) p.set("branch_id", String(branch));
  if (extra) return `?${p.toString()}${p.toString() ? "&" : ""}${extra}`;
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const api = {
  get: async (path, params = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) qs.set(k, String(v));
    });
    const query = qs.toString();
    return http(`${path}${query ? "?" + query : ""}`);
  },

  health: () => http("/health"),
  branches: () => http("/branches"),
  etlStatus: () => http("/etl/status"),

  auth: {
    login: (username, password) =>
      http("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
    me: () => http("/auth/me"),
  },

  dashboardSummary: (branch) => http(`/dashboard/summary${bq(branch)}`),
  dailySales: (branch, days = 30) => http(`/dashboard/daily-sales${bq(branch, `days=${days}`)}`),
  topProducts: (branch, days = 30) => http(`/dashboard/top-products${bq(branch, `days=${days}`)}`),
  cashiers: (branch) => http(`/dashboard/cashiers${bq(branch)}`),

  products: (branch, search = "") =>
    http(`/inventory/products${bq(branch, search ? `search=${encodeURIComponent(search)}` : "")}`),
  customers: (debtors = false) => http(`/customers${debtors ? "?only_debtors=true" : ""}`),
  vendors: () => http("/vendors"),

  expiry: (branch, horizon = 90) => http(`/alerts/expiry${bq(branch, `horizon_days=${horizon}`)}`),
  lowStock: (branch) => http(`/alerts/low-stock${bq(branch)}`),
  reorder: (branch) => http(`/alerts/reorder${bq(branch)}`),

  recentSales: (branch) => http(`/sales/recent${bq(branch)}`),
  createSale: (payload) => http("/sales", { method: "POST", body: JSON.stringify(payload) }),

  chat: (query, branch, lang) =>
    http("/ai/chat", { method: "POST", body: JSON.stringify({ query, branch_id: branch || null, lang }) }),

  // Clinical drug advisory (read-only, advisory only — never blocks a sale).
  clinicalStatus: () => http("/clinical/status"),
  clinicalInteractions: (productIds, branch, lang, minSeverity = "moderate") =>
    http("/clinical/interactions", {
      method: "POST",
      body: JSON.stringify({ product_ids: productIds, branch_id: branch || null, lang, min_severity: minSeverity }),
    }),
  drugInfo: (productId, branch, lang) =>
    http(`/clinical/products/${productId}${bq(branch, `lang=${lang}`)}`),
  substitutions: (productId, branch, lang) =>
    http(`/clinical/products/${productId}/substitutions${bq(branch, `lang=${lang}`)}`),
  dose: (productId, age, lang) => http(`/clinical/products/${productId}/dose?age=${age}&lang=${lang}`),
};
