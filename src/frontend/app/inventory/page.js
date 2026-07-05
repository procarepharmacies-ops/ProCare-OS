"use client";

import { useEffect, useState } from "react";
import Shell from "../components/Shell";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";
import { printLabels } from "../lib/print";

export default function InventoryPage() {
  const { lang, branch } = useUI();
  const L = (k) => t(lang, k);
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState(null);
  // Merchandising: inline shelf-location editing (eStock's Sites).
  const [editingLoc, setEditingLoc] = useState(null); // product_id
  const [locDraft, setLocDraft] = useState("");

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

  async function saveLocation(pid) {
    try {
      const r = await api.setLocation(pid, locDraft);
      setRows((rs) => rs.map((p) => (p.product_id === pid ? { ...p, shelf_location: r.shelf_location } : p)));
    } catch {
      /* keep old value */
    }
    setEditingLoc(null);
    setLocDraft("");
  }

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");

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
              <th>{L("shelf_place")}</th>
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
                <td>
                  {editingLoc === p.product_id ? (
                    <input
                      className="input"
                      autoFocus
                      value={locDraft}
                      onChange={(e) => setLocDraft(e.target.value)}
                      onBlur={() => saveLocation(p.product_id)}
                      onKeyDown={(e) => e.key === "Enter" && saveLocation(p.product_id)}
                      style={{ width: 130 }}
                    />
                  ) : (
                    <span
                      className={p.shelf_location ? "" : "muted"}
                      style={{ cursor: "pointer" }}
                      title={L("shelf_place_hint")}
                      onClick={() => {
                        setEditingLoc(p.product_id);
                        setLocDraft(p.shelf_location || "");
                      }}
                    >
                      {p.shelf_location || "＋"}
                    </span>
                  )}
                </td>
                <td className="num">{fmt(p.sell_price)}</td>
                <td className="num">{fmt(p.on_hand)}</td>
                <td className="num muted">{fmt(p.min_stock)}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  {p.low && <span className="badge warn">{L("low_badge")}</span>}{" "}
                  <button
                    className="btn icon"
                    title={L("print_labels")}
                    onClick={() =>
                      printLabels(
                        [
                          {
                            // Internal coding: fall back to a PC-prefixed id when
                            // the product has no barcode yet.
                            code: p.code || `PC${String(p.product_id).padStart(6, "0")}`,
                            name: lang === "ar" ? p.name_ar : p.name_en || p.name_ar,
                            price: p.sell_price,
                            count: 3,
                          },
                        ],
                        { lang }
                      )
                    }
                  >
                    🏷
                  </button>
                </td>
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
