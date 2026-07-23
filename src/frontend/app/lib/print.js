// Print + export helpers: the branded receipt, ProCare-template report print
// (→ PDF via the browser's print dialog), barcode label sheets, and data-only
// CSV/Excel downloads. All dependency-free.
import { code128Svg } from "./barcode";

const BRAND_CSS = `
  * { box-sizing: border-box; }
  body { font-family: "Cairo","Segoe UI",Tahoma,sans-serif; color: #111; margin: 0; padding: 18px; }
  .brand { display: flex; align-items: center; gap: 10px; border-bottom: 3px solid #0e7c66; padding-bottom: 10px; margin-bottom: 12px; }
  .brand .mark { width: 34px; height: 34px; background: #0e7c66; color: #fff; border-radius: 9px; display: grid; place-items: center; font-size: 21px; font-weight: 800; }
  .brand h1 { font-size: 19px; margin: 0; }
  .brand small { color: #0e7c66; display: block; font-size: 11px; }
  .meta { color: #555; font-size: 12px; margin-bottom: 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: start; }
  th { background: #f0faf7; color: #0e7c66; }
  tfoot td { font-weight: 700; background: #fafafa; }
  .totals { margin-top: 10px; font-size: 14px; }
  .totals div { display: flex; justify-content: space-between; padding: 3px 0; }
  .grand { font-size: 17px; font-weight: 800; border-top: 2px solid #0e7c66; margin-top: 4px; padding-top: 6px; }
  .footer { margin-top: 16px; text-align: center; color: #777; font-size: 11px; }
  .bc { text-align: center; margin-top: 10px; }
  @media print { body { padding: 0; } }
`;

function openAndPrint(html, { rtl = true, title = "ProCare" } = {}) {
  const w = window.open("", "_blank", "width=840,height=900");
  if (!w) return;
  w.document.write(
    `<!doctype html><html dir="${rtl ? "rtl" : "ltr"}"><head><meta charset="utf-8"><title>${title}</title>` +
      `<style>${BRAND_CSS}</style></head><body>${html}</body></html>`
  );
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 350);
}

function brandHeader(subtitle) {
  return (
    `<div class="brand"><div class="mark">+</div><div><h1>ProCare AI</h1>` +
    `<small>مش مجرد صيدلية… عيلة لكل احتياجاتك</small></div>` +
    `<div style="margin-inline-start:auto;color:#555;font-size:12px">${subtitle || ""}</div></div>`
  );
}

const N = (v) => Number(v || 0).toLocaleString("en-US");

// --- Receipt -----------------------------------------------------------------
// `sale` is GET /api/sales/{id}. Discount always prints; profit prints only
// when `showProfit` (management copy) — the customer copy stays clean.
export function printReceipt(sale, { lang = "ar", showProfit = false, showDosage = false, showNote = true } = {}) {
  const ar = lang !== "en";
  const esc = (s) => String(s).replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
  const rows = sale.lines
    .map((l) => {
      const dose = showDosage && (l.dosage_form || l.uses)
        ? `<tr><td colspan="${showProfit ? 6 : 5}" style="color:#555;font-size:11px;padding-top:0">↳ ${esc([l.dosage_form, l.uses].filter(Boolean).join(" — "))}</td></tr>`
        : "";
      return (
        `<tr><td>${ar ? l.name_ar : l.name_en || l.name_ar}</td>` +
        `<td>${N(l.amount)}</td><td>${N(l.sell_price)}</td>` +
        `<td>${N(l.disc_money)}</td><td>${N(l.total_sell)}</td>` +
        (showProfit ? `<td>${N(l.profit)}</td>` : "") +
        `</tr>` + dose
      );
    })
    .join("");
  const noteBlock = showNote && sale.note
    ? `<div style="margin-top:8px;font-size:12px">📝 ${esc(sale.note)}</div>`
    : "";
  const html =
    brandHeader(`${ar ? "فاتورة رقم" : "Invoice #"} ${sale.sale_id}`) +
    `<div class="meta">${new Date(sale.sale_date).toLocaleString(ar ? "ar-EG" : "en-US")}` +
    ` · ${ar ? "فرع" : "Branch"}: ${ar ? sale.branch_name_ar || "" : sale.branch_name_en || ""}` +
    (sale.customer ? ` · ${ar ? "العميل" : "Customer"}: ${sale.customer}` : "") +
    (sale.cashier ? ` · ${ar ? "الكاشير" : "Cashier"}: ${sale.cashier}` : "") +
    (sale.is_return ? ` · <b>${ar ? "مرتجع" : "RETURN"}</b>` : "") +
    `</div>` +
    `<table><thead><tr><th>${ar ? "الصنف" : "Item"}</th><th>${ar ? "كمية" : "Qty"}</th>` +
    `<th>${ar ? "سعر" : "Price"}</th><th>${ar ? "خصم" : "Disc"}</th><th>${ar ? "إجمالي" : "Total"}</th>` +
    (showProfit ? `<th>${ar ? "ربح" : "Profit"}</th>` : "") +
    `</tr></thead><tbody>${rows}</tbody></table>` +
    `<div class="totals">` +
    `<div><span>${ar ? "الإجمالي قبل الخصم" : "Gross"}</span><span>${N(sale.total_gross)}</span></div>` +
    `<div><span>${ar ? "إجمالي الخصم" : "Total discount"}</span><span>−${N(sale.total_discount)}</span></div>` +
    (showProfit
      ? `<div><span>${ar ? "ربح الفاتورة" : "Invoice profit"}</span><span>${N(sale.profit)}</span></div>`
      : "") +
    `<div class="grand"><span>${ar ? "الصافي" : "Net"}</span><span>${N(sale.total_net)} ${ar ? "ج.م" : "EGP"}</span></div>` +
    `</div>` +
    noteBlock +
    `<div class="bc">${code128Svg(`INV-${sale.sale_id}`, { height: 38 })}</div>` +
    `<div class="footer">${ar ? "شكراً لثقتكم — ProCare Pharmacies" : "Thank you — ProCare Pharmacies"}</div>`;
  openAndPrint(html, { rtl: ar, title: `Invoice ${sale.sale_id}` });
}

// --- Branded report print (→ PDF) ---------------------------------------------
// columns: [{key, label}] ; rows: array of objects.
export function printReport(title, columns, rows, { lang = "ar", subtitle = "" } = {}) {
  const ar = lang !== "en";
  const head = columns.map((c) => `<th>${c.label}</th>`).join("");
  const body = rows
    .map(
      (r) =>
        `<tr>${columns
          .map((c) => `<td>${r[c.key] === null || r[c.key] === undefined ? "—" : typeof r[c.key] === "number" ? N(r[c.key]) : r[c.key]}</td>`)
          .join("")}</tr>`
    )
    .join("");
  const html =
    brandHeader(title) +
    `<div class="meta">${subtitle || new Date().toLocaleString(ar ? "ar-EG" : "en-US")} · ${rows.length} ${ar ? "سطر" : "rows"}</div>` +
    `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>` +
    `<div class="footer">ProCare OS — ${new Date().toISOString().slice(0, 10)}</div>`;
  openAndPrint(html, { rtl: ar, title });
}

// --- Barcode label sheet ---------------------------------------------------------
export function printLabels(items, { lang = "ar" } = {}) {
  // items: [{code, name, price, count}]
  const cells = items
    .flatMap((it) => Array.from({ length: it.count || 1 }, () => it))
    .map(
      (it) =>
        `<div style="display:inline-block;border:1px dashed #bbb;border-radius:6px;padding:8px 10px;margin:4px;text-align:center">` +
        `<div style="font-size:11px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${it.name}</div>` +
        `${code128Svg(it.code, { height: 34 })}` +
        (it.price ? `<div style="font-size:12px;font-weight:700">${N(it.price)} ${lang !== "en" ? "ج.م" : "EGP"}</div>` : "") +
        `</div>`
    )
    .join("");
  openAndPrint(brandHeader(lang !== "en" ? "ملصقات باركود" : "Barcode labels") + cells, {
    rtl: lang !== "en",
    title: "Barcode labels",
  });
}

// --- Data-only exports --------------------------------------------------------------
export function downloadCSV(filename, columns, rows) {
  const esc = (v) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [columns.map((c) => esc(c.label)).join(",")];
  for (const r of rows) lines.push(columns.map((c) => esc(r[c.key])).join(","));
  // UTF-8 BOM so Excel renders Arabic correctly.
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

// "Excel" export = the same CSV with an .xls-friendly name; Excel opens it
// directly. (A real XLSX writer is a heavy dependency for zero data gain.)
export function downloadExcel(filename, columns, rows) {
  downloadCSV(filename.replace(/\.xls$/, "") + ".csv", columns, rows);
}
