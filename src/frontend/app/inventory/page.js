"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

export default function InventoryPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState(null);

  useEffect(() => {
    let alive = true;
    const id = setTimeout(async () => {
      try {
        const r = await api.products(branch, search);
        if (alive) setRows(r.products);
      } catch {
        if (alive) setRows([]);
      }
    }, 200);
    return () => {
      alive = false;
      clearTimeout(id);
    };
  }, [branch, search]);

  const fmt = (n) => Number(n || 0).toLocaleString(lang === "ar" ? "ar-EG" : "en-US");

  return (
    <Shell titleKey="nav_inventory">
      <input
        className="input"
        placeholder={L("search") + "…"}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 16, minWidth: 280 }}
      />
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>{L("product")}</th>
              <th>{L("scientific")}</th>
              <th className="num">{L("price")}</th>
              <th className="num">{L("on_hand")}</th>
              <th className="num">{L("min")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows?.map((p) => (
              <tr key={p.product_id}>
                <td>{lang === "ar" ? p.name_ar : p.name_en || p.name_ar}</td>
                <td className="muted">{p.scientific_name || "—"}</td>
                <td className="num">{fmt(p.sell_price)}</td>
                <td className="num">{fmt(p.on_hand)}</td>
                <td className="num muted">{fmt(p.min_stock)}</td>
                <td>{p.low && <span className="badge warn">{L("low_badge")}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows && rows.length === 0 && <p className="muted" style={{ padding: 16 }}>{L("none")}</p>}
        {!rows && <p className="muted" style={{ padding: 16 }}>{L("loading")}</p>}
      </div>
    </Shell>
  );
}
