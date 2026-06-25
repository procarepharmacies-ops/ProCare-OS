"use client";

import { useUI } from "../providers";
import { t, dict } from "../i18n";
import { money } from "../api";

// Dependency-free SVG bar chart of daily net sales. Always LTR (old -> new).
export default function SalesChart({ series }) {
  const { lang } = useUI();
  const L = (k) => t(lang, k);
  if (!series || series.length === 0) {
    return (
      <div className="card panel">
        <h2>{L("daily_sales")}</h2>
        <p style={{ color: "var(--muted)" }}>{L("nothing")}</p>
      </div>
    );
  }

  const W = 980, H = 200, padX = 8, padY = 16;
  const max = Math.max(...series.map((d) => d.revenue || 0), 1);
  const n = series.length;
  const bw = (W - padX * 2) / n;
  const total = series.reduce((s, d) => s + (d.revenue || 0), 0);

  return (
    <div className="card panel">
      <h2>
        {L("daily_sales")}{" "}
        <span style={{ fontWeight: 400, color: "var(--muted)", fontSize: 13 }}>
          · {money(total, lang)} {L("egp")}
        </span>
      </h2>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="200" role="img" dir="ltr"
           preserveAspectRatio="none">
        {series.map((d, i) => {
          const h = ((d.revenue || 0) / max) * (H - padY * 2);
          const x = padX + i * bw;
          const y = H - padY - h;
          const last = i === n - 1;
          return (
            <g key={i}>
              <rect
                className="bar"
                x={x + 1}
                y={y}
                width={Math.max(bw - 2, 1)}
                height={Math.max(h, 1)}
                rx="2"
                fill={last ? "var(--accent)" : "var(--primary)"}
              >
                <title>{`${d.sale_day}: ${money(d.revenue, lang)} ${L("egp")} (${d.bills})`}</title>
              </rect>
            </g>
          );
        })}
        <line x1={padX} y1={H - padY} x2={W - padX} y2={H - padY}
              stroke="var(--border)" strokeWidth="1" />
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", color: "var(--muted)", fontSize: 11, marginTop: 4, direction: "ltr" }}>
        <span>{series[0].sale_day}</span>
        <span>{series[n - 1].sale_day}</span>
      </div>
    </div>
  );
}
