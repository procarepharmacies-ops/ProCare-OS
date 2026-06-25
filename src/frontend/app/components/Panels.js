"use client";

import { useUI } from "../providers";
import { t } from "../i18n";
import { money, num, pickName } from "../api";

function Empty() {
  const { lang } = useUI();
  return <p style={{ color: "var(--muted)", fontSize: 13 }}>{t(lang, "nothing")}</p>;
}

export function TopProducts({ rows }) {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  return (
    <div className="card panel grow">
      <h2>{L("top_products")}</h2>
      {!rows || rows.length === 0 ? <Empty /> : (
        <table className="tbl">
          <thead><tr>
            <th>{L("product")}</th><th className="num">{L("units")}</th><th className="num">{L("revenue")}</th>
          </tr></thead>
          <tbody>
            {rows.slice(0, 8).map((r, i) => (
              <tr key={i}>
                <td>{pickName(r, lang)}</td>
                <td className="num">{num(r.units_sold, lang)}</td>
                <td className="num">{money(r.revenue, lang)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function ExpirySoon({ data }) {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  const rows = (data?.within_30 || []).slice(0, 8);
  return (
    <div className="card panel grow">
      <h2>{L("expiry_soon")}{" "}
        {data && <span className="badge warn">{num(data.counts?.within_30, lang)}</span>}
      </h2>
      {rows.length === 0 ? <Empty /> : (
        <table className="tbl">
          <thead><tr>
            <th>{L("product")}</th><th className="num">{L("qty")}</th>
            <th className="num">{L("days_left")}</th>
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{pickName(r, lang)}</td>
                <td className="num">{num(r.qty_remaining, lang)}</td>
                <td className="num">
                  {r.days_to_expiry < 0
                    ? <span className="badge danger">{L("expired")}</span>
                    : num(r.days_to_expiry, lang)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function LowStock({ data }) {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  const rows = (data?.drafts || []).slice(0, 8);
  return (
    <div className="card panel grow">
      <h2>{L("low_stock_panel")}{" "}
        {data && <span className="badge warn">{num(data.count, lang)}</span>}
      </h2>
      {rows.length === 0 ? <Empty /> : (
        <table className="tbl">
          <thead><tr>
            <th>{L("product")}</th><th className="num">{L("on_hand")}</th>
            <th className="num">{L("min")}</th><th className="num">{L("suggest_order")}</th>
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{pickName(r, lang)}</td>
                <td className="num">{num(r.on_hand, lang)}</td>
                <td className="num">{num(r.min_stock, lang)}</td>
                <td className="num"><span className="badge ok">{num(r.suggested_order_qty, lang)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function Debtors({ data }) {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  const rows = (data?.customers || []).slice(0, 8);
  return (
    <div className="card panel grow">
      <h2>{L("debtors_panel")}{" "}
        {data && <span className="badge danger">{num(data.count, lang)}</span>}
      </h2>
      {rows.length === 0 ? <Empty /> : (
        <table className="tbl">
          <thead><tr>
            <th>{L("customer")}</th><th className="num">{L("balance")}</th><th className="num">{L("over_by")}</th>
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{pickName(r, lang, "customer_name")}</td>
                <td className="num">{money(r.balance, lang)}</td>
                <td className="num" style={{ color: "var(--danger)" }}>{money(r.over_limit_by, lang)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
