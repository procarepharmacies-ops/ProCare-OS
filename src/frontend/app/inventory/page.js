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
  // Classification filters (الفلترة): form / OTC / place / price sort.
  const [filters, setFilters] = useState({ dosage_form: "", otc: "", location: "", sort: "" });
  const [filterValues, setFilterValues] = useState({ dosage_forms: [], locations: [] });
  // إضافة صنف جديد.
  const [showAdd, setShowAdd] = useState(false);
  const [draft, setDraft] = useState({});
  const [addMsg, setAddMsg] = useState(null);

  useEffect(() => {
    api.productFilters().then(setFilterValues).catch(() => {});
  }, [showAdd]); // refresh after adding (new form/location values)

  useEffect(() => {
    if (stagnantMode) return;
    let alive = true;
    const id = setTimeout(async () => {
      try {
        const r = await api.productsFiltered(branch, {
          search,
          dosage_form: filters.dosage_form,
          otc: filters.otc,
          location: filters.location,
          sort: filters.sort,
        });
        if (alive) setRows(r.products);
      } catch {
        if (alive) setRows([]);
      }
    }, 200);
    return () => {
      alive = false;
      clearTimeout(id);
    };
  }, [branch, search, stagnantMode, filters]);

  async function saveProduct() {
    setAddMsg(null);
    try {
      await api.createProduct({
        ...draft,
        sell_price: Number(draft.sell_price) || 0,
        buy_price: Number(draft.buy_price) || 0,
        min_stock: Number(draft.min_stock) || 0,
        unit_factor: Number(draft.unit_factor) || 1,
        is_otc: !!draft.is_otc,
      });
      setAddMsg({ kind: "ok", text: t(lang, "product_saved") });
      setDraft({});
      setShowAdd(false);
      setFilters((f) => ({ ...f })); // re-trigger list load
    } catch (e) {
      setAddMsg({ kind: "danger", text: e?.message || String(e) });
    }
  }

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
        {!stagnantMode && (
          <>
            <select
              className="input"
              value={filters.dosage_form}
              onChange={(e) => setFilters((f) => ({ ...f, dosage_form: e.target.value }))}
            >
              <option value="">{L("dosage_form")}: {L("all_lbl")}</option>
              {filterValues.dosage_forms.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            <select
              className="input"
              value={filters.otc}
              onChange={(e) => setFilters((f) => ({ ...f, otc: e.target.value }))}
            >
              <option value="">OTC: {L("all_lbl")}</option>
              <option value="true">OTC</option>
              <option value="false">Rx</option>
            </select>
            <select
              className="input"
              value={filters.location}
              onChange={(e) => setFilters((f) => ({ ...f, location: e.target.value }))}
            >
              <option value="">{L("shelf_place")}: {L("all_lbl")}</option>
              {filterValues.locations.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            <select
              className="input"
              value={filters.sort}
              onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value }))}
            >
              <option value="">{L("price_sort")}</option>
              <option value="price_asc">{L("price_asc")}</option>
              <option value="price_desc">{L("price_desc")}</option>
            </select>
            <button className="btn primary" onClick={() => setShowAdd(true)}>
              ＋ {L("add_product")}
            </button>
          </>
        )}
        {addMsg && <span className={`badge ${addMsg.kind === "ok" ? "ok" : "danger"}`}>{addMsg.text}</span>}
      </div>

      {showAdd && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <h3 className="section-title" style={{ margin: 0 }}>{L("add_product")}</h3>
            <button className="btn icon" onClick={() => setShowAdd(false)}>✕</button>
          </div>
          <div className="grid" style={{ gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            <input className="input" placeholder={L("product") + " (عربي) *"} value={draft.name_ar || ""}
              onChange={(e) => setDraft((d) => ({ ...d, name_ar: e.target.value }))} />
            <input className="input" placeholder={L("product") + " (EN)"} value={draft.name_en || ""}
              onChange={(e) => setDraft((d) => ({ ...d, name_en: e.target.value }))} />
            <input className="input" placeholder={L("scientific")} value={draft.scientific_name || ""}
              onChange={(e) => setDraft((d) => ({ ...d, scientific_name: e.target.value }))} />
            <input className="input" type="number" placeholder={L("price")} value={draft.sell_price || ""}
              onChange={(e) => setDraft((d) => ({ ...d, sell_price: e.target.value }))} />
            <input className="input" type="number" placeholder="سعر الشراء" value={draft.buy_price || ""}
              onChange={(e) => setDraft((d) => ({ ...d, buy_price: e.target.value }))} />
            <input className="input" placeholder="الباركود / الكود" value={draft.code || ""}
              onChange={(e) => setDraft((d) => ({ ...d, code: e.target.value }))} />
            <input className="input" placeholder={L("dosage_form")} list="forms-list" value={draft.dosage_form || ""}
              onChange={(e) => setDraft((d) => ({ ...d, dosage_form: e.target.value }))} />
            <datalist id="forms-list">
              {filterValues.dosage_forms.map((v) => <option key={v} value={v} />)}
            </datalist>
            <input className="input" placeholder={L("uses_lbl")} value={draft.uses || ""}
              onChange={(e) => setDraft((d) => ({ ...d, uses: e.target.value }))} />
            <input className="input" placeholder={L("shelf_place")} value={draft.shelf_location || ""}
              onChange={(e) => setDraft((d) => ({ ...d, shelf_location: e.target.value }))} />
            <input className="input" placeholder="الوحدة الكبرى (علبة)" value={draft.unit_big || ""}
              onChange={(e) => setDraft((d) => ({ ...d, unit_big: e.target.value }))} />
            <input className="input" placeholder="الوحدة الصغرى (شريط)" value={draft.unit_small || ""}
              onChange={(e) => setDraft((d) => ({ ...d, unit_small: e.target.value }))} />
            <input className="input" type="number" placeholder="عدد الصغرى في الكبرى" value={draft.unit_factor || ""}
              onChange={(e) => setDraft((d) => ({ ...d, unit_factor: e.target.value }))} />
          </div>
          <div style={{ display: "flex", gap: 12, marginTop: 10, alignItems: "center" }}>
            <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input type="checkbox" checked={!!draft.is_otc}
                onChange={(e) => setDraft((d) => ({ ...d, is_otc: e.target.checked }))} />
              {L("otc_lbl")}
            </label>
            <button className="btn primary" onClick={saveProduct} disabled={!draft.name_ar}>
              {L("save")}
            </button>
          </div>
        </div>
      )}

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
