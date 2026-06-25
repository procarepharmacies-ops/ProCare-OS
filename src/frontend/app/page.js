"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet } from "./api";
import Header from "./components/Header";
import KpiCards from "./components/KpiCards";
import SalesChart from "./components/SalesChart";
import { TopProducts, ExpirySoon, LowStock, Debtors } from "./components/Panels";
import AiChat from "./components/AiChat";

export default function Dashboard() {
  const [health, setHealth] = useState(null);
  const [branches, setBranches] = useState([]);
  const [branch, setBranch] = useState("ALL");
  const [summary, setSummary] = useState(null);
  const [series, setSeries] = useState([]);
  const [top, setTop] = useState([]);
  const [expiry, setExpiry] = useState(null);
  const [lowStock, setLowStock] = useState(null);
  const [debtors, setDebtors] = useState(null);
  const [online, setOnline] = useState(true);

  // One-time: backend health + branch list.
  useEffect(() => {
    (async () => {
      try {
        const [h, b] = await Promise.all([apiGet("/health"), apiGet("/branches")]);
        setHealth(h);
        setBranches(b.branches || []);
        setOnline(true);
      } catch {
        setOnline(false);
      }
    })();
  }, []);

  // Branch-scoped data; re-runs on branch change and manual refresh.
  const load = useCallback(async (b) => {
    try {
      const [s, ds, tp, ex, ls, db] = await Promise.all([
        apiGet(`/dashboard/summary?branch=${b}`),
        apiGet(`/dashboard/daily-sales?branch=${b}&days=30`),
        apiGet(`/dashboard/top-products?branch=${b}&days=30&limit=8`),
        apiGet(`/alerts/expiry?branch=${b}`),
        apiGet(`/alerts/low-stock?branch=${b}`),
        apiGet(`/alerts/debtors`),
      ]);
      setSummary(s);
      setSeries(ds.series || []);
      setTop(tp.products || []);
      setExpiry(ex);
      setLowStock(ls);
      setDebtors(db);
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    load(branch);
  }, [branch, load]);

  return (
    <main className="wrap">
      <Header
        branches={branches}
        branch={branch}
        setBranch={setBranch}
        health={health}
        online={online}
        onRefresh={() => load(branch)}
      />

      <KpiCards kpis={summary?.kpis} />

      <SalesChart series={series} />

      <div className="row">
        <TopProducts rows={top} />
        <ExpirySoon data={expiry} />
      </div>
      <div className="row">
        <LowStock data={lowStock} />
        <Debtors data={debtors} />
      </div>

      <AiChat branch={branch} />
    </main>
  );
}
