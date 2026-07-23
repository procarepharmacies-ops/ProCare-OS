"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Shell from "../components/Shell";
import Icon from "../components/icons";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";
import { printReceipt } from "../lib/print";

// useSearchParams (for the ?rx=<id> prescription hand-off) must sit inside a
// Suspense boundary so Next can build the page.
export default function POSPage() {
  return (
    <Suspense fallback={null}>
      <POSInner />
    </Suspense>
  );
}

function POSInner() {
  const { lang, branch, branches, setBranch, user } = useUI();
  const L = (k) => t(lang, k);
  const [products, setProducts] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [search, setSearch] = useState("");
  const [cart, setCart] = useState([]);
  const [isCredit, setIsCredit] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [result, setResult] = useState(null);
  // Loyalty + WhatsApp CRM state.
  const [loyaltyInfo, setLoyaltyInfo] = useState(null);
  const [redeemIn, setRedeemIn] = useState("");
  const [waLink, setWaLink] = useState(null);
  const [advisory, setAdvisory] = useState([]);
  // Substitution panel: same-active-ingredient alternatives with per-branch
  // stock + nearest expiry (drug substitution during sales).
  const [subsFor, setSubsFor] = useState(null); // {product_id, name}
  const [subs, setSubs] = useState(null);
  // Last completed sale id — enables the branded receipt print.
  const [lastSaleId, setLastSaleId] = useState(null);
  // Return mode (eStock: sale returns were used 4,359 times — a first-class flow).
  const [mode, setMode] = useState("sale"); // "sale" | "return"
  const [returnSaleId, setReturnSaleId] = useState("");
  const [returnInvoice, setReturnInvoice] = useState(null);
  const [returnQty, setReturnQty] = useState({}); // product_id -> qty
  // Cash desk shift (eStock's Cash Desk: open with float, close vs expected).
  const [shift, setShift] = useState(null);
  const [floatIn, setFloatIn] = useState("");
  const [countedIn, setCountedIn] = useState("");
  const [shiftMsg, setShiftMsg] = useState(null);
  // Shortcoming: sell what's on hand and log the unmet remainder to the sheet.
  const [allowPartial, setAllowPartial] = useState(false);
  // F2 cross-branch stock popup: the product whose branch stock we're showing.
  const [branchStock, setBranchStock] = useState(null);

  // POS writes to a specific branch; default to the first if "All" is selected.
  const posBranch = branch || branches[0]?.branch_id;

  // Seed the cart from a reviewed prescription (?rx=<id>): the prescription
  // reader hands off here so the pharmacist dispenses it as a normal sale.
  const searchParams = useSearchParams();
  const [rxId, setRxId] = useState(null);
  useEffect(() => {
    const id = searchParams.get("rx");
    if (!id || !posBranch) return;
    setRxId(Number(id));
    api
      .rxCart(id, posBranch)
      .then((res) => {
        const lines = (res.lines || []).map((l) => ({
          product_id: l.product_id,
          name: lang === "ar" ? l.name_ar : l.name_en || l.name_ar,
          sell_price: l.sell_price,
          amount: l.amount || 1,
        }));
        if (lines.length) setCart(lines);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, posBranch]);

  // F2 = branch-stock popup for the top search match (eStock's branch-stock
  // hotkey); Esc closes any open popup.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "F2") {
        e.preventDefault();
        const top = products[0];
        if (top) setBranchStock(top);
      } else if (e.key === "Escape") {
        setBranchStock(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [products]);

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

  // Customer picked -> show their loyalty balance for redemption.
  useEffect(() => {
    setLoyaltyInfo(null);
    setRedeemIn("");
    if (!customerId) return;
    let alive = true;
    api.loyalty(Number(customerId)).then((r) => alive && setLoyaltyInfo(r)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [customerId]);

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
      if (found)
        return c.map((x) =>
          x.product_id === p.product_id
            ? { ...x, amount: x.amount + (x.unit === "small" ? 1 / (x.unit_factor || 1) : 1) }
            : x
        );
      return [
        ...c,
        {
          product_id: p.product_id,
          name: lang === "ar" ? p.name_ar : p.name_en || p.name_ar,
          sell_price: p.sell_price,
          buy_price: Number(p.buy_price) || 0,
          amount: 1, // ALWAYS in big units (علبة) — the DB stock unit
          unit: "big",
          unit_big: p.unit_big || null,
          unit_small: p.unit_small || null,
          unit_factor: Number(p.unit_factor) > 1 ? Number(p.unit_factor) : 1,
        },
      ];
    });
  }
  // qty is what the cashier typed, in the line's SELECTED unit; stock stays in
  // big units, so a small-unit qty is divided by the factor (٢ شريط = ٠٫٦٦٧ علبة).
  function setQty(pid, qty) {
    setCart((c) =>
      c.map((x) => {
        if (x.product_id !== pid) return x;
        const q = Math.max(1, qty);
        return { ...x, amount: x.unit === "small" ? q / (x.unit_factor || 1) : q };
      })
    );
  }
  function toggleUnit(pid) {
    setCart((c) =>
      c.map((x) => {
        if (x.product_id !== pid || !x.unit_small || x.unit_factor <= 1) return x;
        // Keep the physical quantity, flip only the display/entry unit.
        return { ...x, unit: x.unit === "big" ? "small" : "big" };
      })
    );
  }
  const shownQty = (x) =>
    x.unit === "small" ? Math.round(x.amount * (x.unit_factor || 1)) : Math.round(x.amount * 1000) / 1000;
  function removeItem(pid) {
    setCart((c) => c.filter((x) => x.product_id !== pid));
  }

  const total = useMemo(() => cart.reduce((s, x) => s + x.sell_price * x.amount, 0), [cart]);
  // مكسب الفاتورة أثناء البيع — manager/CEO eyes only (buy prices are gated).
  const invoiceProfit = useMemo(
    () => cart.reduce((s, x) => s + (x.sell_price - (x.buy_price || 0)) * x.amount, 0),
    [cart]
  );
  const canSeeProfit = user && (user.role === "ceo" || user.role === "manager");

  useEffect(() => {
    if (!posBranch) return;
    api.cashShift(posBranch).then((r) => setShift(r.shift)).catch(() => {});
  }, [posBranch]);

  async function doOpenShift() {
    setShiftMsg(null);
    try {
      const s = await api.openShift({ branch_id: posBranch, cashier_id: 1, opening_float: Number(floatIn) || 0 });
      setShift(s);
      setFloatIn("");
    } catch (e) {
      setShiftMsg({ ok: false, msg: e.message });
    }
  }

  async function doCloseShift() {
    setShiftMsg(null);
    try {
      const s = await api.closeShift({ branch_id: posBranch, counted_cash: Number(countedIn) || 0 });
      setShift(null);
      setCountedIn("");
      setShiftMsg({
        ok: true,
        msg: `${L("expected_cash")}: ${fmt(s.expected_cash)} · ${L("variance")}: ${fmt(s.variance)} ${L("egp")}`,
      });
    } catch (e) {
      setShiftMsg({ ok: false, msg: e.message });
    }
  }

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

  async function showSubs(item, outOfStock = false) {
    setSubsFor({ product_id: item.product_id, name: item.name, outOfStock });
    setSubs(null);
    try {
      const r = await api.substitutions(item.product_id, posBranch, lang);
      setSubs(r.substitutions || r.alternatives || []);
    } catch {
      setSubs([]);
    }
  }

  function swapToSub(s) {
    // From an out-of-stock trigger there is no cart line yet → add the chosen
    // in-stock alternative. Otherwise replace the original cart line.
    if (subsFor?.outOfStock) {
      addToCart({ product_id: s.product_id, name_ar: s.name, name_en: s.name, sell_price: s.sell_price, on_hand: 1 });
    } else {
      setCart((c) =>
        c.map((x) =>
          x.product_id === subsFor.product_id
            ? { ...x, product_id: s.product_id, name: s.name, sell_price: s.sell_price }
            : x
        )
      );
    }
    setSubsFor(null);
    setSubs(null);
  }

  // Order the product from another branch that has stock: creates a transfer
  // request (a manager approves it — nothing moves until then).
  async function orderFromBranch(fromBranchId, productId, name) {
    try {
      await api.requestTransfer({
        from_branch_id: fromBranchId,
        to_branch_id: posBranch,
        lines: [{ product_id: productId, amount: 1 }],
      });
      setShiftMsg({ ok: true, text: L("transfer_requested") + ": " + name });
    } catch {
      setShiftMsg({ ok: false, text: L("transfer_request_failed") });
    }
  }

  async function doPrintReceipt() {
    if (!lastSaleId) return;
    try {
      const sale = await api.saleDetail(lastSaleId);
      printReceipt(sale, { lang });
    } catch {
      /* receipt is best-effort */
    }
  }

  async function completeSale() {
    setResult(null);
    setWaLink(null);
    setLastSaleId(null);
    try {
      const payload = {
        branch_id: posBranch,
        cashier_id: 1,
        is_credit: isCredit,
        customer_id: customerId ? Number(customerId) : null,
        lines: cart.map((x) => ({ product_id: x.product_id, amount: x.amount })),
        redeem_points: Number(redeemIn) || 0,
        allow_partial: allowPartial,
      };
      const r = await api.createSale(payload);
      // If this sale came from a prescription, mark it dispensed.
      if (rxId) {
        api.rxDispensed(rxId).catch(() => {});
        setRxId(null);
      }
      let msg = `${L("sale_done")} ${r.sale_id} · ${fmt(r.total_net)} ${L("egp")}`;
      if (r.loyalty_points !== undefined) msg += ` · ${L("points_balance")}: ${fmt(r.loyalty_points)} ⭐`;
      if (r.whatsapp_sent) msg += ` · ${L("wa_sent")} ✓`;
      // Flag any line the shortcoming path trimmed (sold < requested).
      if (allowPartial && Array.isArray(r.lines)) {
        const sold = Object.fromEntries(r.lines.map((l) => [l.product_id, l.amount]));
        const trimmed = cart.filter((x) => (sold[x.product_id] ?? 0) < x.amount);
        if (trimmed.length) msg += ` · ${L("pos_partial_logged")}`;
      }
      setResult({ ok: true, msg });
      setWaLink(r.whatsapp_link || null);
      setLastSaleId(r.sale_id);
      setCart([]);
      setIsCredit(false);
      setCustomerId("");
      setRedeemIn("");
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
      <div style={{ display: "flex", gap: 8, marginBottom: 14, alignItems: "center", flexWrap: "wrap" }}>
        <button className={`btn ${mode === "sale" ? "primary" : ""}`} onClick={() => { setMode("sale"); setResult(null); }}>
          {L("new_sale")}
        </button>
        <button className={`btn ${mode === "return" ? "primary" : ""}`} onClick={() => { setMode("return"); setResult(null); }}>
          {L("return_mode")}
        </button>
        {/* Cash desk shift control */}
        <span style={{ marginInlineStart: "auto", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span className={`badge ${shift ? "ok" : ""}`}>
            {shift ? `${L("shift_open")} · ${L("opening_float")} ${fmt(shift.opening_float)}` : L("shift_closed")}
          </span>
          {!shift ? (
            <>
              <input className="input" type="number" min={0} placeholder={L("opening_float")}
                     value={floatIn} onChange={(e) => setFloatIn(e.target.value)} style={{ width: 110 }} />
              <button className="btn" onClick={doOpenShift}>{L("open_shift")}</button>
            </>
          ) : (
            <>
              <input className="input" type="number" min={0} placeholder={L("counted_cash")}
                     value={countedIn} onChange={(e) => setCountedIn(e.target.value)} style={{ width: 110 }} />
              <button className="btn" onClick={doCloseShift} disabled={countedIn === ""}>{L("close_shift")}</button>
            </>
          )}
        </span>
      </div>
      {shiftMsg && (
        <p className={`badge ${shiftMsg.ok ? "ok" : "danger"}`} style={{ marginBottom: 12, display: "inline-block", padding: 8 }}>
          {shiftMsg.msg}
        </p>
      )}

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
              onKeyDown={(e) => {
                // Enter = take the top suggestion straight into the cart.
                if (e.key === "Enter" && products.length > 0 && products[0].on_hand > 0) {
                  addToCart(products[0]);
                  setSearch("");
                }
              }}
              style={{ width: "100%" }}
            />
            {search && (
              <p className="muted" style={{ margin: "6px 2px 0", fontSize: 12 }}>
                {products.length} {L("search_matches")} — Enter {L("search_enter_hint")}
              </p>
            )}
            {/* Visible hotkey map (eStock keeps its shortcuts on-screen). */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
              {[
                ["Enter", L("hotkey_add")],
                ["F2", L("hotkey_branch_stock")],
                ["Esc", L("hotkey_close")],
              ].map(([k, label]) => (
                <span key={k} className="badge" style={{ fontSize: 11 }}>
                  <kbd style={{ fontWeight: 700 }}>{k}</kbd> {label}
                </span>
              ))}
            </div>
          </div>
          <div style={{ maxHeight: 460, overflowY: "auto" }}>
            <table className="tbl">
              <tbody>
                {products.map((p) => (
                  <tr
                    key={p.product_id}
                    style={{ cursor: "pointer" }}
                    onClick={() =>
                      p.on_hand > 0
                        ? addToCart(p)
                        : showSubs({ product_id: p.product_id, name: lang === "ar" ? p.name_ar : p.name_en || p.name_ar }, true)
                    }
                    title={p.on_hand > 0 ? "" : L("oos_show_alts")}
                  >
                    <td>
                      {lang === "ar" ? p.name_ar : p.name_en || p.name_ar}
                      {p.unit_small && p.unit_factor > 1 && (
                        <span className="muted" style={{ fontSize: 11 }}>
                          {" "}· {p.unit_big || ""} = {fmt(p.unit_factor)} {p.unit_small}
                        </span>
                      )}
                    </td>
                    <td className="num muted">{fmt(p.sell_price)}</td>
                    <td className="num">
                      {p.on_hand > 0 ? (
                        <span className="muted">{fmt(p.on_hand)}</span>
                      ) : (
                        <span style={{ display: "inline-flex", gap: 4, flexWrap: "wrap", justifyContent: "flex-end" }}>
                          <span className="badge danger">0</span>
                          {/* أثناء البيع: هل الصنف متوفر في الفرع الآخر؟ */}
                          {(p.other_branches || []).map((b) => (
                            <span key={b.branch_id} className="badge ok" style={{ fontSize: 11 }}>
                              {L("available_in")} {b.branch}: {fmt(b.on_hand)}
                            </span>
                          ))}
                        </span>
                      )}
                    </td>
                    <td>{p.on_hand > 0 ? "＋" : "⇄"}</td>
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
              <button className="btn icon" onClick={() => showSubs(x)} title={L("alternatives")}>
                ⇄
              </button>
              {/* Unit selector (وحدة كبرى/صغرى): sell by علبة or by شريط/أمبول. */}
              {x.unit_small && x.unit_factor > 1 && (
                <button
                  className="btn"
                  style={{ padding: "2px 8px", fontSize: 12 }}
                  title={`1 ${x.unit_big || ""} = ${x.unit_factor} ${x.unit_small}`}
                  onClick={() => toggleUnit(x.product_id)}
                >
                  {x.unit === "small" ? x.unit_small : x.unit_big || L("unit_lbl")} ▾
                </button>
              )}
              <input
                className="input"
                type="number"
                min={1}
                value={shownQty(x)}
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

          {/* Substitution recommendations: same active ingredient, price, stock
              per branch with the nearest expiry. Click to swap into the cart. */}
          {subsFor && (
            <div className="card" style={{ margin: "10px 0", padding: 10, background: "var(--bg)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <strong style={{ fontSize: 13 }}>
                  {subsFor.outOfStock ? "⚠ " + L("oos_alts_title") : "⇄ " + L("alt_for")}: {subsFor.name}
                </strong>
                <button className="btn icon" onClick={() => { setSubsFor(null); setSubs(null); }}>✕</button>
              </div>
              {subs === null && <p className="muted" style={{ fontSize: 13 }}>{L("loading")}</p>}
              {subs && subs.length === 0 && <p className="muted" style={{ fontSize: 13 }}>{L("no_alternatives")}</p>}
              {subs?.map((s) => (
                <div key={s.product_id} style={{ borderTop: "1px solid var(--border)", padding: "6px 0", fontSize: 13 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                    <span>
                      <strong>{s.name}</strong>
                      <span className="muted"> · {s.scientific_name}</span>
                    </span>
                    <span style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      <span className="num">{fmt(s.sell_price)} {L("egp")}</span>
                      <button className="btn" onClick={() => swapToSub(s)}>⇄</button>
                    </span>
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
                    {(s.branches || []).map((b) => (
                      <span key={b.branch_id} className="badge" style={{ fontSize: 11, display: "inline-flex", gap: 4, alignItems: "center" }}>
                        {b.branch_name}: {fmt(b.qty)}
                        {b.nearest_expiry ? ` · ${L("expiry_lbl")} ${b.nearest_expiry}` : ""}
                        {b.branch_id !== posBranch && b.qty > 0 && (
                          <button
                            className="btn"
                            style={{ padding: "0 6px", fontSize: 11 }}
                            title={L("order_from_branch")}
                            onClick={() => orderFromBranch(b.branch_id, s.product_id, s.name)}
                          >
                            ⇩ {L("order")}
                          </button>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div style={{ borderTop: "1px solid var(--border)", marginTop: 10, paddingTop: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 20, fontWeight: 700 }}>
              <span>{L("total")}</span>
              <span className="num">
                {fmt(total)} {L("egp")}
              </span>
            </div>
            {canSeeProfit && cart.length > 0 && (
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginTop: 4 }} className="muted">
                <span>{L("invoice_profit")}</span>
                <span className="num" style={{ color: invoiceProfit >= 0 ? "var(--ok)" : "var(--danger)" }}>
                  {fmt(invoiceProfit)} {L("egp")}
                </span>
              </div>
            )}

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

            {/* Customer is optional on cash sales — attaching one earns loyalty
                points and enables the WhatsApp invoice. Required for credit. */}
            <select className="select" value={customerId} onChange={(e) => setCustomerId(e.target.value)} style={{ width: "100%", marginBottom: 12 }}>
              <option value="">{L("select_customer")}</option>
              {customers.map((c) => (
                <option key={c.customer_id} value={c.customer_id}>
                  {(lang === "ar" ? c.name_ar : c.name_en || c.name_ar)}
                  {c.over_limit ? " ⚠️" : ""}
                </option>
              ))}
            </select>

            {loyaltyInfo && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
                <span className="badge ok">
                  ⭐ {fmt(loyaltyInfo.points)} {L("points")} ≈ {fmt(loyaltyInfo.value_egp)} {L("egp")}
                </span>
                {loyaltyInfo.points > 0 && (
                  <>
                    <input
                      className="input"
                      type="number"
                      min={0}
                      max={loyaltyInfo.points}
                      placeholder={L("redeem_points")}
                      value={redeemIn}
                      onChange={(e) => setRedeemIn(e.target.value)}
                      style={{ width: 120 }}
                    />
                    {Number(redeemIn) > 0 && (
                      <span className="muted" style={{ fontSize: 13 }}>
                        −{fmt(Math.min(Number(redeemIn) * loyaltyInfo.point_value_egp, total).toFixed(2))} {L("egp")}
                      </span>
                    )}
                  </>
                )}
              </div>
            )}

            <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, fontSize: 13, cursor: "pointer" }}>
              <input type="checkbox" checked={allowPartial} onChange={(e) => setAllowPartial(e.target.checked)} />
              <span>{L("pos_partial_toggle")}</span>
            </label>

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
            {waLink && (
              <a className="btn" href={waLink} target="_blank" rel="noreferrer"
                 style={{ marginTop: 8, width: "100%", display: "block", textAlign: "center" }}>
                💬 {L("wa_send_invoice")}
              </a>
            )}
            {lastSaleId && (
              <button className="btn" onClick={doPrintReceipt}
                      style={{ marginTop: 8, width: "100%" }}>
                {L("print_receipt")}
              </button>
            )}
          </div>
        </div>
      </div>
      )}

      {/* F2 cross-branch stock popup: where else this item is on the shelf. */}
      {branchStock && (
        <div
          onClick={() => setBranchStock(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "grid", placeItems: "center", zIndex: 50 }}
        >
          <div className="card" onClick={(e) => e.stopPropagation()} style={{ minWidth: 320, maxWidth: 480 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <h3 className="section-title" style={{ margin: 0 }}>
                {lang === "ar" ? branchStock.name_ar : branchStock.name_en || branchStock.name_ar}
              </h3>
              <button className="btn icon" style={{ marginInlineStart: "auto" }} onClick={() => setBranchStock(null)}>✕</button>
            </div>
            <table className="tbl">
              <tbody>
                <tr>
                  <td>{L("this_branch")}</td>
                  <td className="num">
                    <span className={`badge ${branchStock.on_hand > 0 ? "ok" : "danger"}`}>{fmt(branchStock.on_hand)}</span>
                  </td>
                </tr>
                {(branchStock.other_branches || []).map((b) => (
                  <tr key={b.branch_id}>
                    <td>{b.branch}</td>
                    <td className="num"><span className="badge">{fmt(b.on_hand)}</span></td>
                  </tr>
                ))}
                {(!branchStock.other_branches || branchStock.other_branches.length === 0) && (
                  <tr><td colSpan="2" className="muted">{L("no_other_branch_stock")}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Shell>
  );
}
