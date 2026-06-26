"use client";

// Dependency-free SVG charts — keep the skeleton's "zero extra deps" principle.

export function BarChart({ data, height = 180, color = "var(--primary)", labelKey = "date", valueKey = "revenue" }) {
  if (!data || data.length === 0) return <p className="muted">—</p>;
  const max = Math.max(...data.map((d) => d[valueKey]), 1);
  const w = 100 / data.length;
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width: "100%", height }}>
      {data.map((d, i) => {
        const h = (d[valueKey] / max) * 92;
        return (
          <rect
            key={i}
            x={i * w + w * 0.15}
            y={100 - h}
            width={w * 0.7}
            height={h}
            rx={0.6}
            fill={color}
            opacity={0.85}
          >
            <title>{`${d[labelKey]}: ${Math.round(d[valueKey]).toLocaleString()}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

export function HBar({ value, max, color = "var(--accent)" }) {
  const pct = Math.min(100, (value / (max || 1)) * 100);
  return (
    <div style={{ background: "var(--bg)", borderRadius: 6, height: 8, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: color }} />
    </div>
  );
}
