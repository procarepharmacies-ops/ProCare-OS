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
  // الأصناف الراكدة: stagnant-items report mode.
  const [stagnantMode, setStagnantMode] = useState(false);
  const [stagnantDays, setStagnantDays] = useState(90);
  const [stagnant, setStagnant] = useState(null);

  useEffect(() => {
    if (stagnantMode) return;
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
  }, [branch, search, stagnantMode]);

  useEffect(() => {
    if (!stagnantMode) return;
    let alive = true;
    setStagnant(null);
    api
      .stagnant(branch, stagnantDays)
      .then((r) => alive && setStagnant(r))
      .catch(() => alive && setStagnant({ items: [], total_value: 0, total_items: 0 }));
    return () => {
      alive = false;
    };
  }, [branch, stagnantDays, stagnantMode]);

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
  const unitLabel = (p) =>
    p.unit_small && p.unit_factor > 1
      ? `${p.unit_big || "—"} = ${fmt(p.unit_factor)} ${p.unit_small}`
      : p.unit_big || "—";

  return (
    <Shell titleKey="nav_inventory">
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 16 }}>
        {!stagnantMode && (
          <input
            className="input"
            placeholder={L("search") + "…"}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ minWidth: 280 }}
          />
        )}
        <button
          className={`btn ${stagnantMode ? "primary" : ""}`}
          onClick={() => setStagnantMode((v) => !v)}
        >
          🕸 {L("stagnant_only")}
        </button>
        {stagnantMode && (
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {L("stagnant_days")}
            <input
              className="input"
              type="number"
              min={7}
              value={stagnantDays}
              onChange={(e) => setStagnantDays(Math.max(7, Number(e.target.value) || 90))}
              style={{ width: 80 }}
            />
          </label>
        )}
        {stagnantMode && stagnant && (
          <span className="badge warn">
            {stagnant.total_items} {L("stagnant_title")} · {L("stock_value")}: {fmt(stagnant.total_value)}
          </span>
        )}
      </div>

      {stagnantMode ? (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>{L("product")}</th>
                <th className="num">{L("on_hand")}</th>
                <th className="num">{L("stock_value")}</th>
                <th>{L("last_sale")}</th>
                <th className="num">{L("idle_days")}</th>
              </tr>
            </thead>
            <tbody>
              {stagnant?.items?.map((p) => (
                <tr key={p.product_id}>
                  <td>{lang === "ar" ? p.name_ar : p.name_en || p.name_ar}</td>
                  <td className="num">{fmt(p.on_hand)}</td>
                  <td className="num">{fmt(p.value)}</td>
                  <td className="muted">{p.last_sale ? p.last_sale.slice(0, 10) : L("never_sold")}</td>
                  <td className="num muted">{p.idle_days ?? "∞"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {stagnant && stagnant.items.length === 0 && (
            <p className="muted" style={{ padding: 16 }}>{L("none")}</p>
          )}
          {!stagnant && <p className="muted" style={{ padding: 16 }}>{L("loading")}</p>}
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>{L("product")}</th>
                <th>{L("scientific")}</th>
                <th>{L("unit_lbl")}</th>
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
                  <td className="muted">{unitLabel(p)}</td>
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
      )}
    </Shell>
  );
}
