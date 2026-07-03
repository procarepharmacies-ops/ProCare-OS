"use client";

import { useEffect, useMemo, useState } from "react";
import Shell from "../components/Shell";
import Icon from "../components/icons";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

export default function POSPage() {
  const { lang, branch, branches, setBranch } = useUI();
  const L = (k) => t(lang, k);
  const [products, setProducts] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [search, setSearch] = useState("");
  const [cart, setCart] = useState([]);
  const [isCredit, setIsCredit] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [result, setResult] = useState(null);
  const [advisory, setAdvisory] = useState([]);
  // Return mode (eStock: sale returns were used 4,359 times — a first-class flow).
  const [mode, setMode] = useState("sale"); // "sale" | "return"
  const [returnSaleId, setReturnSaleId] = useState("");
  const [returnInvoice, setReturnInvoice] = useState(null);
  const [returnQty, setReturnQty] = useState({}); // product_id -> qty

  // POS writes to a specific branch; default to the first if "All" is selected.
  const posBranch = branch || branches[0]?.branch_id;

  useEffect(() => {
    if (!posBranch) return;
    let alive = true;
    const id = setTimeout(async () => {
      try {
        const r = await api.products(posBranch, search);
        if (alive) setProducts(r.products);
      } catch {
        /* ignore */
      }
    }, 200);
    return () => {
      alive = false;
      clearTimeout(id);
    };
  }, [posBranch, search]);

  useEffect(() => {
    api.customers().then((r) => setCustomers(r.customers)).catch(() => {});
  }, []);

  // Advisory drug-interaction check on the basket — runs as items change, shown
  // to the pharmacist. Never blocks the sale (clinical guardrail).
  useEffect(() => {
    if (cart.length < 2) {
      setAdvisory([]);
      return;
    }
    let alive = true;
    api
      .clinicalInteractions(cart.map((x) => x.product_id), posBranch, lang)
      .then((r) => alive && setAdvisory(r.interactions || []))
      .catch(() => alive && setAdvisory([]));
    return () => {
      alive = false;
    };
  }, [cart, posBranch, lang]);

  const sevClass = (s) => (s === "critical" || s === "major" ? "danger" : "warn");

  const fmt = (n) => Number(n || 0).toLocaleString("en-US");

  function addToCart(p) {
    setResult(null);
    setCart((c) => {
      const found = c.find((x) => x.product_id === p.product_id);
      if (found) return c.map((x) => (x.product_id === p.product_id ? { ...x, amount: x.amount + 1 } : x));
      return [...c, { product_id: p.product_id, name: lang === "ar" ? p.name_ar : p.name_en || p.name_ar, sell_price: p.sell_price, amount: 1 }];
    });
  }
  function setQty(pid, amount) {
    setCart((c) => c.map((x) => (x.product_id === pid ? { ...x, amount: Math.max(1, amount) } : x)));
  }
  function removeItem(pid) {
    setCart((c) => c.filter((x) => x.product_id !== pid));
  }

  const total = useMemo(() => cart.reduce((s, x) => s + x.sell_price * x.amount, 0), [cart]);

  async function loadReturnInvoice() {
    setResult(null);
    setReturnInvoice(null);
    try {
      const inv = await api.returnable(Number(returnSaleId));
      setReturnInvoice(inv);
      const init = {};
      for (const l of inv.lines) init[l.product_id] = l.returnable;
      setReturnQty(init);
    } catch (e) {
      setResult({ ok: false, msg: e.message });
    }
  }

  async function completeReturn() {
    setResult(null);
    try {
      const lines = returnInvoice.lines
        .filter((l) => Number(returnQty[l.product_id]) > 0)
        .map((l) => ({ product_id: l.product_id, amount: Number(returnQty[l.product_id]) }));
      const r = await api.returnSale(returnInvoice.sale_id, { lines, cashier_id: 1 });
      setResult({ ok: true, msg: `${L("return_done")} ${r.return_id} · ${fmt(r.total_refund)} ${L("egp")}` });
      setReturnInvoice(null);
      setReturnSaleId("");
      setReturnQty({});
    } catch (e) {
      setResult({ ok: false, msg: e.message });
    }
  }

  async function completeSale() {
    setResult(null);
    try {
      const payload = {
        branch_id: posBranch,
        cashier_id: 1,
        is_credit: isCredit,
        customer_id: isCredit ? Number(customerId) || null : customerId ? Number(customerId) : null,
        lines: cart.map((x) => ({ product_id: x.product_id, amount: x.amount })),
      };
      const r = await api.createSale(payload);
      setResult({ ok: true, msg: `${L("sale_done")} ${r.sale_id} · ${fmt(r.total_net)} ${L("egp")}` });
      setCart([]);
      setIsCredit(false);
      setCustomerId("");
    } catch (e) {
      setResult({ ok: false, msg: e.message });
    }
  }

  return (
    <Shell titleKey="nav_pos">
      {!branch && branches.length > 0 && (
        <p className="muted" style={{ marginBottom: 12 }}>
          {lang === "ar" ? "البيع على فرع:" : "Selling at branch:"}{" "}
          <select className="select" value={posBranch} onChange={(e) => setBranch(Number(e.target.value))}>
            {branches.map((b) => (
              <option key={b.branch_id} value={b.branch_id}>
                {lang === "ar" ? b.name_ar : b.name_en}
              </option>
            ))}
          </select>
        </p>
      )}
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <button className={`btn ${mode === "sale" ? "primary" : ""}`} onClick={() => { setMode("sale"); setResult(null); }}>
          {L("new_sale")}
        </button>
        <button className={`btn ${mode === "return" ? "primary" : ""}`} onClick={() => { setMode("return"); setResult(null); }}>
          {L("return_mode")}
        </button>
      </div>

      {mode === "return" && (
        <div className="card" style={{ maxWidth: 640 }}>
          <h3 className="section-title">{L("sale_return")}</h3>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <input
              className="input"
              type="number"
              min={1}
              placeholder={L("invoice_number")}
              value={returnSaleId}
              onChange={(e) => setReturnSaleId(e.target.value)}
              style={{ flex: 1 }}
            />
            <button className="btn primary" disabled={!returnSaleId} onClick={loadReturnInvoice}>
              {L("load_invoice")}
            </button>
          </div>

          {returnInvoice && (
            <>
              <p className="muted" style={{ fontSize: 13 }}>
                #{returnInvoice.sale_id} · {new Date(returnInvoice.sale_date).toLocaleDateString()} ·{" "}
                {fmt(returnInvoice.total_net)} {L("egp")}
                {returnInvoice.customer ? ` · ${returnInvoice.customer}` : ""}
              </p>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>{L("add_item")}</th>
                    <th className="num">{L("sold_qty")}</th>
                    <th className="num">{L("returnable_qty")}</th>
                    <th className="num">{L("return_qty")}</th>
                  </tr>
                </thead>
                <tbody>
                  {returnInvoice.lines.map((l) => (
                    <tr key={l.product_id}>
                      <td>{lang === "ar" ? l.name_ar : l.name_en || l.name_ar}</td>
                      <td className="num muted">{fmt(l.sold)}</td>
                      <td className="num">{fmt(l.returnable)}</td>
                      <td className="num">
                        <input
                          className="input"
                          type="number"
                          min={0}
                          max={l.returnable}
                          value={returnQty[l.product_id] ?? 0}
                          onChange={(e) =>
                            setReturnQty((q) => ({
                              ...q,
                              [l.product_id]: Math.min(Math.max(0, Number(e.target.value)), l.returnable),
                            }))
                          }
                          style={{ width: 72 }}
                          disabled={l.returnable <= 0}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
                <span style={{ fontWeight: 700 }}>
                  {L("refund_total")}:{" "}
                  <span className="num">
                    {fmt(
                      returnInvoice.lines.reduce(
                        (s, l) => s + (Number(returnQty[l.product_id]) || 0) * l.unit_net_price,
                        0
                      ).toFixed(2)
                    )}{" "}
                    {L("egp")}
                  </span>
                </span>
                <button
                  className="btn primary"
                  disabled={!returnInvoice.lines.some((l) => Number(returnQty[l.product_id]) > 0)}
                  onClick={completeReturn}
                >
                  {L("complete_return")}
                </button>
              </div>
            </>
          )}

          {result && (
            <p className={`badge ${result.ok ? "ok" : "danger"}`} style={{ marginTop: 12, display: "block", padding: 10 }}>
              {result.msg}
            </p>
          )}
        </div>
      )}

      {mode === "sale" && (
      <div className="grid" style={{ gridTemplateColumns: "1.3fr 1fr" }}>
        {/* Product picker */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: 12, borderBottom: "1px solid var(--border)" }}>
            <input
              className="input"
              placeholder={L("search") + "…"}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: "100%" }}
            />
          </div>
          <div style={{ maxHeight: 460, overflowY: "auto" }}>
            <table className="tbl">
              <tbody>
                {products.map((p) => (
                  <tr key={p.product_id} style={{ cursor: "pointer" }} onClick={() => p.on_hand > 0 && addToCart(p)}>
                    <td>{lang === "ar" ? p.name_ar : p.name_en || p.name_ar}</td>
                    <td className="num muted">{fmt(p.sell_price)}</td>
                    <td className="num">
                      {p.on_hand > 0 ? (
                        <span className="muted">{fmt(p.on_hand)}</span>
                      ) : (
                        <span className="badge danger">0</span>
                      )}
                    </td>
                    <td>＋</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Cart */}
        <div className="card">
          <h3 className="section-title">{L("new_sale")}</h3>
          {cart.length === 0 && <p className="muted">{L("cart_empty")}</p>}
          {cart.map((x) => (
            <div key={x.product_id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={{ flex: 1 }}>{x.name}</span>
              <input
                className="input"
                type="number"
                min={1}
                value={x.amount}
                onChange={(e) => setQty(x.product_id, Number(e.target.value))}
                style={{ width: 64 }}
              />
              <span className="num muted" style={{ width: 70, textAlign: "end" }}>
                {fmt(x.sell_price * x.amount)}
              </span>
              <button className="btn icon" onClick={() => removeItem(x.product_id)} title={L("remove")}>
                ✕
              </button>
            </div>
          ))}

          <div style={{ borderTop: "1px solid var(--border)", marginTop: 10, paddingTop: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 20, fontWeight: 700 }}>
              <span>{L("total")}</span>
              <span className="num">
                {fmt(total)} {L("egp")}
              </span>
            </div>

            {advisory.length > 0 && (
              <div
                className="card"
                style={{ margin: "12px 0", padding: 10, borderColor: "var(--danger)", background: "var(--bg)" }}
              >
                <div style={{ fontWeight: 700, marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                  <Icon name="mortar" size={16} /> {L("interactions")}
                </div>
                {advisory.map((it, i) => (
                  <div key={i} style={{ marginBottom: 6, fontSize: 13 }}>
                    <span className={`badge ${sevClass(it.severity)}`}>{L(`sev_${it.severity}`)}</span>{" "}
                    <strong>{it.product_a.name} + {it.product_b.name}</strong>
                    <div className="muted">{it.effect}</div>
                    <div style={{ fontSize: 12 }}>↳ {it.recommendation}</div>
                  </div>
                ))}
                <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                  {L("advisory_note")}
                </div>
              </div>
            )}

            <div style={{ display: "flex", gap: 8, margin: "12px 0" }}>
              <button className={`btn ${!isCredit ? "primary" : ""}`} onClick={() => setIsCredit(false)} style={{ flex: 1 }}>
                {L("pay_cash")}
              </button>
              <button className={`btn ${isCredit ? "primary" : ""}`} onClick={() => setIsCredit(true)} style={{ flex: 1 }}>
                {L("pay_credit")}
              </button>
            </div>

            {isCredit && (
              <select className="select" value={customerId} onChange={(e) => setCustomerId(e.target.value)} style={{ width: "100%", marginBottom: 12 }}>
                <option value="">{L("select_customer")}</option>
                {customers.map((c) => (
                  <option key={c.customer_id} value={c.customer_id}>
                    {(lang === "ar" ? c.name_ar : c.name_en || c.name_ar)}
                    {c.over_limit ? " ⚠️" : ""}
                  </option>
                ))}
              </select>
            )}

            <button
              className="btn primary"
              style={{ width: "100%" }}
              disabled={cart.length === 0 || (isCredit && !customerId)}
              onClick={completeSale}
            >
              {L("complete_sale")}
            </button>

            {result && (
              <p className={`badge ${result.ok ? "ok" : "danger"}`} style={{ marginTop: 12, display: "block", padding: 10 }}>
                {result.msg}
              </p>
            )}
          </div>
        </div>
      </div>
      )}
    </Shell>
  );
}
