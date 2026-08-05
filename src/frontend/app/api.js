// Thin API client for the ProCare backend. All calls are read-only except the
// POS endpoints. Base URL is configurable for deployment.
// Base URL for the backend. An empty string means "same origin" — used in the
// containerized deployment, where Next.js proxies /api to the backend
// server-side (see next.config.mjs), so the browser never needs the backend's
// address and there is no CORS hop. `??` (not `||`) so an explicit "" is kept.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8100";

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

// Generic fetch helper for pages that pass the FULL path including the `/api`
// prefix (e.g. apiFetch("/api/agents/status")). Unlike `http()` above it does
// NOT prepend `/api`, so the two never collide. Same auth/error semantics.
export async function apiFetch(path, options) {
  const token = session.get()?.token;
  const res = await fetch(`${API_BASE}${path}`, {
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
  post: (path, body) => http(path, { method: "POST", body: JSON.stringify(body) }),

  health: () => http("/health"),
  branches: () => http("/branches"),
  etlStatus: () => http("/etl/status"),

  auth: {
    login: (username, password) =>
      http("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
    me: () => http("/auth/me"),
    forgotPassword: (username) =>
      http("/auth/forgot-password", { method: "POST", body: JSON.stringify({ username }) }),
    resetPassword: (username, code, new_password) =>
      http("/auth/reset-password", { method: "POST", body: JSON.stringify({ username, code, new_password }) }),
  },

  dashboardSummary: (branch) => http(`/dashboard/summary${bq(branch)}`),
  dailySales: (branch, days = 30) => http(`/dashboard/daily-sales${bq(branch, `days=${days}`)}`),
  topProducts: (branch, days = 30) => http(`/dashboard/top-products${bq(branch, `days=${days}`)}`),
  productInsight: (productId, branch) => http(`/inventory/products/${productId}/insight${bq(branch)}`),
  cashiers: (branch) => http(`/dashboard/cashiers${bq(branch)}`),

  products: (branch, search = "") =>
    http(`/inventory/products${bq(branch, search ? `search=${encodeURIComponent(search)}` : "")}`),
  customers: (debtors = false) => http(`/customers${debtors ? "?only_debtors=true" : ""}`),
  customerStatement: (customerId) => http(`/customers/${customerId}/statement`),
  vendors: () => http("/vendors"),

  expiry: (branch, horizon = 90) => http(`/alerts/expiry${bq(branch, `horizon_days=${horizon}`)}`),
  lowStock: (branch) => http(`/alerts/low-stock${bq(branch)}`),
  reorder: (branch) => http(`/alerts/reorder${bq(branch)}`),

  recentSales: (branch) => http(`/sales/recent${bq(branch)}`),
  createSale: (payload) => http("/sales", { method: "POST", body: JSON.stringify(payload) }),
  productBatches: (productId, branch) => http(`/inventory/products/${productId}/batches${bq(branch)}`),
  // Hold / park invoice (parked carts).
  holdInvoice: (payload) => http("/sales/hold", { method: "POST", body: JSON.stringify(payload) }),
  heldInvoices: (branch) => http(`/sales/held${bq(branch)}`),
  resumeHeld: (heldId) => http(`/sales/held/${heldId}/resume`),
  discardHeld: (heldId) => http(`/sales/held/${heldId}/discard`, { method: "POST" }),
  returnable: (saleId) => http(`/sales/${saleId}/returnable`),
  returnSale: (saleId, payload = {}) =>
    http(`/sales/${saleId}/return`, { method: "POST", body: JSON.stringify(payload) }),
  profitLoss: (branch, days = 30) => http(`/accounting/profit-loss${bq(branch, `days=${days}`)}`),
  salesByCustomer: (branch, days = 30) => http(`/accounting/sales-by-customer${bq(branch, `days=${days}`)}`),

  // Performance over time (5-year), post-sync audit, supplier purchasing.
  perfOverview: (branch, years = 5) => http(`/performance/overview${bq(branch, `years=${years}`)}`),
  perfAudit: (branch) => http(`/performance/audit${bq(branch)}`),
  perfVendor: (branch, query = "pharmaoverseas", years = 5) =>
    http(`/performance/vendor${bq(branch, `query=${encodeURIComponent(query)}&years=${years}`)}`),
  perfDeep: (branch, years = 5, lang = "en") =>
    http(`/performance/deep${bq(branch, `years=${years}&lang=${lang}`)}`),

  cashShift: (branchId) => http(`/cashdesk/current?branch_id=${branchId}`),
  openShift: (payload) => http("/cashdesk/open", { method: "POST", body: JSON.stringify(payload) }),
  closeShift: (payload) => http("/cashdesk/close", { method: "POST", body: JSON.stringify(payload) }),

  createPurchase: (payload) =>
    http("/purchasing/purchases", { method: "POST", body: JSON.stringify(payload) }),
  adjustStock: (payload) => http("/inventory/adjust", { method: "POST", body: JSON.stringify(payload) }),
  setLocation: (productId, shelf_location) =>
    http(`/inventory/products/${productId}/location`, { method: "POST", body: JSON.stringify({ shelf_location }) }),
  employeeGoals: (employeeId) => http(`/employees/${employeeId}/goals`),
  createGoal: (employeeId, payload) =>
    http(`/employees/${employeeId}/goals`, { method: "POST", body: JSON.stringify(payload) }),
  setGoalStatus: (goalId, status) =>
    http(`/employees/goals/${goalId}/status`, { method: "POST", body: JSON.stringify({ status }) }),

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

  // Dashboard views: month series, branch comparison, custom date range.
  monthlySales: (branch, months = 12) => http(`/dashboard/monthly${bq(branch, `months=${months}`)}`),
  byBranch: (dateFrom, dateTo) =>
    http(`/dashboard/by-branch${dateFrom && dateTo ? `?date_from=${dateFrom}&date_to=${dateTo}` : ""}`),
  rangeSummary: (branch, dateFrom, dateTo) =>
    http(`/dashboard/range${bq(branch, `date_from=${dateFrom}&date_to=${dateTo}`)}`),
  saleDetail: (saleId) => http(`/sales/${saleId}`),

  // Treasury: vouchers, branch money transfers, balances.
  treasuryBalances: () => http("/treasury/balances"),
  treasuryMovements: (branch) => http(`/treasury/movements${bq(branch)}`),
  treasuryTransfers: (branch) => http(`/treasury/transfers${bq(branch)}`),
  treasuryReceive: (payload) => http("/treasury/receive", { method: "POST", body: JSON.stringify(payload) }),
  treasuryPay: (payload) => http("/treasury/pay", { method: "POST", body: JSON.stringify(payload) }),
  treasuryTransfer: (payload) => http("/treasury/transfer", { method: "POST", body: JSON.stringify(payload) }),
  treasuryAdjust: (payload) => http("/treasury/adjust", { method: "POST", body: JSON.stringify(payload) }),

  // Prescription reader + doctor habits.
  rxStatus: () => http("/prescriptions/status"),
  rxAnalyze: (payload) => http("/prescriptions/analyze", { method: "POST", body: JSON.stringify(payload) }),
  rxCreate: (payload) => http("/prescriptions", { method: "POST", body: JSON.stringify(payload) }),
  rxList: (branch) => http(`/prescriptions${bq(branch)}`),
  rxHabits: (branch, days = 180) => http(`/prescriptions/doctor-habits${bq(branch, `days=${days}`)}`),
  rxResolve: (id, branch) => http(`/prescriptions/${id}/resolve${bq(branch)}`),
  rxReview: (id, payload) => http(`/prescriptions/${id}/review`, { method: "POST", body: JSON.stringify(payload) }),
  rxCart: (id, branch) => http(`/prescriptions/${id}/cart${bq(branch)}`),
  rxDispensed: (id) => http(`/prescriptions/${id}/dispensed`, { method: "POST" }),

  // Shortage sheet.
  shortages: (branch, status) =>
    http(`/shortages${bq(branch, status ? `status=${status}` : "")}`),
  createShortage: (payload) => http("/shortages", { method: "POST", body: JSON.stringify(payload) }),
  setShortageStatus: (id, status) =>
    http(`/shortages/${id}/status`, { method: "POST", body: JSON.stringify({ status }) }),

  // Predictive purchasing + returns.
  purchaseBudget: (branch) => http(`/purchasing/budget${bq(branch)}`),
  autoProposal: (branch) => http(`/purchasing/auto-proposal${bq(branch)}`),
  autoGenerate: (branchId) => http(`/purchasing/auto-generate?branch_id=${branchId}`, { method: "POST" }),
  purchaseDetail: (purchaseId) => http(`/purchasing/purchases/${purchaseId}`),
  returnPurchase: (purchaseId, payload = {}) =>
    http(`/purchasing/purchases/${purchaseId}/return`, { method: "POST", body: JSON.stringify(payload) }),
  purchaseDrafts: (branch) => http(`/purchasing/drafts${bq(branch)}`),
  approveDraft: (draftId) => http(`/purchasing/drafts/${draftId}/approve`, { method: "POST" }),
  rejectDraft: (draftId) => http(`/purchasing/drafts/${draftId}/reject`, { method: "POST" }),

  // Inter-branch transfer requests + approval workflow.
  transfersList: (branch, status) =>
    http(`/transfers/list${bq(branch, status ? `status=${status}` : "")}`),
  requestTransfer: (payload) =>
    http("/transfers/request", { method: "POST", body: JSON.stringify(payload) }),
  approveTransfer: (transferId) => http(`/transfers/${transferId}/approve`, { method: "POST" }),
  rejectTransfer: (transferId) => http(`/transfers/${transferId}/reject`, { method: "POST" }),
  shipTransfer: (transferId) => http(`/transfers/${transferId}/ship`, { method: "POST" }),
  receiveTransfer: (transferId, lines) =>
    http(`/transfers/${transferId}/receive`, { method: "POST", body: JSON.stringify({ lines }) }),

  // Catalogue management + classification filters.
  productFilters: () => http("/inventory/filters"),
  createProduct: (payload) => http("/inventory/products", { method: "POST", body: JSON.stringify(payload) }),
  productsFiltered: (branch, params = {}) => {
    const extra = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null && v !== "")
      .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
      .join("&");
    return http(`/inventory/products${bq(branch, extra)}`);
  },

  // Purchase planning (كشكول النواقص): priority + transfer-first + consolidated.
  purchasePlan: (branchId) => http(`/purchasing/plan?branch_id=${branchId}`),
  purchasePlanConsolidated: () => http("/purchasing/plan/consolidated"),

  // Vendor account (كشف حساب مورد + سداد).
  vendorStatement: (vendorId) => http(`/vendors/${vendorId}/statement`),
  payVendor: (vendorId, payload) => http(`/vendors/${vendorId}/pay`, { method: "POST", body: JSON.stringify(payload) }),

  // Backups (نسخ احتياطية).
  backupNow: () => http("/backup", { method: "POST" }),
  backupList: () => http("/backup"),

  // Stagnant items (الأصناف الراكدة): stocked, no sale in N days.
  stagnant: (branch, days = 90) => http(`/inventory/stagnant${bq(branch, `days=${days}`)}`),

  // Stocktaking (الجرد): count sessions, count sheet, posting adjustments.
  stockCounts: (branch) => http(`/stocktaking${bq(branch)}`),
  stockCountDetail: (countId) => http(`/stocktaking/${countId}`),
  createStockCount: (payload) => http("/stocktaking", { method: "POST", body: JSON.stringify(payload) }),
  saveStockCountLines: (countId, entries) =>
    http(`/stocktaking/${countId}/lines`, { method: "POST", body: JSON.stringify({ entries }) }),
  postStockCount: (countId, employee_id) =>
    http(`/stocktaking/${countId}/post`, { method: "POST", body: JSON.stringify({ employee_id }) }),
  cancelStockCount: (countId) => http(`/stocktaking/${countId}/cancel`, { method: "POST" }),

  // In-system cash-flow & inventory audit.
  auditReport: (months = 3, vendor = "") =>
    http(`/audit/cash-report?months=${months}${vendor ? `&vendor=${encodeURIComponent(vendor)}` : ""}`),

  // Stock reports (JSON; append ?format=csv server-side for raw export).
  stockReport: (branch) => http(`/reports/stock${bq(branch)}`),
  stockBatches: (branch) => http(`/reports/stock/batches${bq(branch)}`),
  stockMovements: (branch, days = 30) => http(`/reports/stock/movements${bq(branch, `days=${days}`)}`),
  stockValuation: () => http("/reports/stock/valuation"),
  // Item sales-movement report (eStock حركة مبيعات صنف في فترة): per-day
  // opening/purchases/sales/returns/adjust/closing for one product.
  itemMovement: (productId, branch, days = 30) =>
    http(`/reports/item-movement${bq(branch, `product_id=${productId}&days=${days}`)}`),

  // Employee incentives (OTC "push the most profitable brand" list).
  incentiveCandidates: (metric, topN, branch, search = "") =>
    http(`/incentives/candidates${bq(branch, `metric=${metric}&top_n=${topN}${search ? `&search=${encodeURIComponent(search)}` : ""}`)}`),
  incentiveApply: (items) => http("/incentives/apply", { method: "POST", body: JSON.stringify({ items }) }),
  incentiveList: () => http("/incentives/products"),
  incentiveLeaderboard: (branch, month) =>
    http(`/incentives/leaderboard${bq(branch, month ? `month=${month}` : "")}`),
  employeeIncentives: (employeeId, month) =>
    http(`/incentives/employee/${employeeId}${month ? `?month=${month}` : ""}`),

  // Sales-rep commission calculator (net sales × % per rep, post + audit).
  commissionPreview: (start, end, branch, rate) =>
    http(`/commissions/preview${bq(branch, `period_start=${start}&period_end=${end}&default_rate_pct=${rate}`)}`),
  commissionRuns: (branch) => http(`/commissions/runs${bq(branch)}`),
  commissionRun: (runId) => http(`/commissions/runs/${runId}`),
  postCommissionRun: (payload) =>
    http("/commissions/runs", { method: "POST", body: JSON.stringify(payload) }),
  voidCommissionRun: (runId) =>
    http(`/commissions/runs/${runId}/void`, { method: "POST" }),

  // Change history (audit): price changes, stock movements, login events.
  productChanges: (branch, days = 90) => http(`/audit/product-changes?days=${days}`),
  stockChanges: (branch, days = 30) => http(`/audit/stock-changes${bq(branch, `days=${days}`)}`),
  authEvents: (limit = 100) => http(`/audit/auth-events?limit=${limit}`),
  updatePricing: (productId, payload) =>
    http(`/inventory/products/${productId}/pricing`, { method: "POST", body: JSON.stringify(payload) }),

  // Payroll depth: per-employee base/commission/deductions/advances/net + history.
  employeePayroll: (employeeId) => http(`/employees/${employeeId}/payroll`),

  // Shareholders / owners register + dividend history (company_Owner mirror).
  shareholders: () => http("/shareholders"),
  shareholder: (id) => http(`/shareholders/${id}`),

  // Permissions discovery: the current user's own flags/limits/role access.
  myPermissions: (employeeId) =>
    http(`/permissions/me${employeeId ? `?employee_id=${employeeId}` : ""}`),

  // Notification center + ticker (News_bar/Flag parity): expiry/low-stock/shortage.
  notifications: (branch, expiryDays = 30) =>
    http(`/notifications${bq(branch, `expiry_days=${expiryDays}`)}`),
  notificationTicker: (branch, limit = 12) =>
    http(`/notifications/ticker${bq(branch, `limit=${limit}`)}`),
  dismissNotifications: (eventKeys, branch) =>
    http("/notifications/dismiss", { method: "POST", body: JSON.stringify({ event_keys: eventKeys, branch_id: branch || null }) }),

  // CRM: loyalty points, WhatsApp invoices, marketing campaigns.
  crmStatus: () => http("/crm/status"),
  loyalty: (customerId) => http(`/crm/loyalty/${customerId}`),
  customerProfile: (customerId) => http(`/customers/${customerId}/profile`),
  updateCustomer: (customerId, payload) => http(`/customers/${customerId}`, { method: "POST", body: JSON.stringify(payload) }),
  chartOfAccounts: (branch) => http(`/accounting/chart${bq(branch)}`),
  // Accounting mirror: كشف حساب statement, Tuning تسويات reasons + adjustments.
  accountStatement: (accountType, accountRef, branch, days) =>
    http(`/accounting/statement${bq(branch, `account_type=${accountType}${accountRef ? `&account_ref=${accountRef}` : ""}&days=${days}`)}`),
  adjustmentReasons: () => http("/accounting/adjustment-reasons"),
  adjustments: (branch, days) => http(`/accounting/adjustments${bq(branch, `days=${days}`)}`),
  createJournal: (payload) => http("/accounting/journal", { method: "POST", body: JSON.stringify(payload) }),
  adjustLoyalty: (customerId, payload) =>
    http(`/crm/loyalty/${customerId}/adjust`, { method: "POST", body: JSON.stringify(payload) }),
  saleWhatsapp: (saleId) => http(`/crm/sales/${saleId}/whatsapp`),
  campaigns: () => http("/crm/campaigns"),
  createCampaign: (payload) => http("/crm/campaigns", { method: "POST", body: JSON.stringify(payload) }),
  sendCampaign: (campaignId) => http(`/crm/campaigns/${campaignId}/send`, { method: "POST" }),
  campaignLinks: (campaignId) => http(`/crm/campaigns/${campaignId}/links`),

  // Phase 4: Social media + promo codes
  generateSocialCopy: (context, brandName) =>
    http("/marketing/posts/generate-copy", { method: "POST", body: JSON.stringify({ context, brand_name: brandName }) }),
  createSocialPost: (payload) =>
    http("/marketing/posts", { method: "POST", body: JSON.stringify(payload) }),
  getSocialPost: (postId) => http(`/marketing/posts/${postId}`),
  socialCalendar: (channel, month) => {
    const p = new URLSearchParams();
    if (channel) p.set("channel", channel);
    if (month) p.set("month", String(month));
    const s = p.toString();
    return http(`/marketing/calendar${s ? "?" + s : ""}`);
  },
  approveSocialPost: (postId) =>
    http(`/marketing/posts/${postId}/approve`, { method: "PATCH" }),
  publishSocialPost: (postId) =>
    http(`/marketing/posts/${postId}/publish`, { method: "POST" }),
  createPromoCode: (payload) =>
    http("/marketing/promo-codes", { method: "POST", body: JSON.stringify(payload) }),
  listPromoCodes: () => http("/marketing/promo-codes"),
  getActivePromoCodes: () => http("/marketing/promo-codes/active"),
  validatePromoCode: (code, invoiceTotal) =>
    http(`/marketing/promo-codes/${code}/validate?invoice_total=${invoiceTotal}`),
  deactivatePromoCode: (code) =>
    http(`/marketing/promo-codes/${code}/deactivate`, { method: "PATCH" }),

  // Phase 6 Dashboard — new KPI endpoints.
  purchasing: (branch) => http(`/dashboard/purchasing${bq(branch)}`),
  yoy: (branch) => http(`/dashboard/yoy${bq(branch)}`),
  dashboardCash: () => http("/dashboard/cash"),
  expenses: (branch) => http(`/dashboard/expenses${bq(branch)}`),
  staffNow: (branch) => http(`/dashboard/staff-now${bq(branch)}`),
  stocktakingAlerts: (minutes = 5) => http(`/stocktaking/recent-alerts?minutes=${minutes}`),

  // Phase 5 Decision cards (القرارات اليومية).
  decisions: () => http("/decisions"),
  dismissDecision: (cardId) => http(`/decisions/${cardId}/dismiss`, { method: "POST" }),
  actionDecision: (cardId, employeeId = null) => http(`/decisions/${cardId}/action`, {
    method: "POST",
    body: JSON.stringify({ employee_id: employeeId }),
  }),
};
