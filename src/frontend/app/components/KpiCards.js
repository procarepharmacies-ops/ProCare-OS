"use client";

import { useUI } from "../providers";
import { t } from "../i18n";
import { money, num, pct } from "../api";

export default function KpiCards({ kpis }) {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  if (!kpis) return null;

  const egp = (v) => `${money(v, lang)} ${L("egp")}`;
  const delta = pct(kpis.month_delta_pct);
  const deltaDir = kpis.month_delta_pct == null ? "" : kpis.month_delta_pct >= 0 ? "up" : "down";

  const cards = [
    { label: L("sales_today"), value: egp(kpis.sales_today),
      sub: `${num(kpis.bills_today, lang)} ${L("bills_today")} · ${L("avg_basket")} ${egp(kpis.avg_basket_today)}` },
    { label: L("sales_month"), value: egp(kpis.sales_month),
      sub: delta ? `${delta} ${L("vs_last_month")}` : null, subDir: deltaDir },
    { label: L("profit_month"), value: egp(kpis.profit_month) },
    { label: L("expiring_30"), value: num(kpis.expiring_30_days, lang),
      sub: `${num(kpis.expiring_7_days, lang)} ${L("expiring_7")} · ${num(kpis.expired_in_stock, lang)} ${L("expired_in_stock")}`,
      tone: kpis.expiring_7_days > 0 ? "warn" : "" },
    { label: L("low_stock"), value: num(kpis.low_stock_items, lang),
      tone: kpis.low_stock_items > 0 ? "warn" : "" },
    { label: L("debtors_over_limit"), value: num(kpis.debtors_over_limit, lang),
      sub: `${L("vendor_payables")}: ${egp(kpis.vendor_payables)}`,
      tone: kpis.debtors_over_limit > 0 ? "danger" : "" },
  ];

  return (
    <section className="kpi-grid" style={{ marginTop: 18 }}>
      {cards.map((c, i) => (
        <div key={i} className={`card kpi ${c.tone || ""}`}>
          <div className="label">{c.label}</div>
          <div className="value">{c.value}</div>
          {c.sub && <div className={`sub ${c.subDir || ""}`}>{c.sub}</div>}
        </div>
      ))}
    </section>
  );
}
