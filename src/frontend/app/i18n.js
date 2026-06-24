// Bilingual UI strings (chrome only). Product/data text comes from the DB as
// name_ar / name_en. Arabic is the default; English is an optional toggle.
export const dict = {
  ar: {
    app: "بروكير أو إس",
    tagline: "نظام إدارة الصيدلية المستقل",
    branch: "الفرع",
    all_branches: "كل الفروع",
    backend_status: "حالة الخادم",
    online: "متصل",
    offline: "غير متصل",
    using_example: "يستخدم إعداد المثال",
    sales_today: "مبيعات اليوم",
    sales_month: "مبيعات الشهر",
    low_stock: "أصناف منخفضة",
    expiring_30: "تنتهي خلال ٣٠ يوم",
    debtors: "عملاء تجاوزوا الحد",
    not_wired: "غير موصول بقاعدة البيانات بعد (المرحلة ١)",
    phase0: "المرحلة ٠ — هيكل أولي",
  },
  en: {
    app: "ProCare OS",
    tagline: "Independent pharmacy operating system",
    branch: "Branch",
    all_branches: "All branches",
    backend_status: "Backend status",
    online: "Online",
    offline: "Offline",
    using_example: "using example config",
    sales_today: "Sales today",
    sales_month: "Sales this month",
    low_stock: "Low-stock items",
    expiring_30: "Expiring in 30 days",
    debtors: "Over-limit customers",
    not_wired: "Not wired to the database yet (Phase 1)",
    phase0: "Phase 0 — skeleton",
  },
};

export function t(lang, key) {
  return (dict[lang] && dict[lang][key]) || dict.ar[key] || key;
}
