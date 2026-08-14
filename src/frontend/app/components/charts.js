"use client";

// Dependency-free SVG charts — keep the skeleton's "zero extra deps" principle.
// Bars grow in with a staggered CSS animation (bar-grow / hbar-grow keyframes
// live in globals.css and are disabled under prefers-reduced-motion).

import { useEffect, useId, useRef, useState } from "react";

export function BarChart({ data, height = 180, color = "var(--primary)", labelKey = "date", valueKey = "revenue", onDrill }) {
  const gradId = useId();
  const [hoverId, setHoverId] = useState(null);
  const [tooltip, setTooltip] = useState(null);

  if (!data || data.length === 0) return <p className="muted">—</p>;
  const max = Math.max(...data.map((d) => d[valueKey]), 1);
  const w = 100 / data.length;

  const handleMouseMove = (e, d, i) => {
    const rect = e.currentTarget.parentElement.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setHoverId(i);
    setTooltip({ x, y, label: d[labelKey], value: Math.round(d[valueKey]).toLocaleString("en-US") });
  };

  return (
    <div style={{ position: "relative", width: "100%", height }}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width: "100%", height }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--primary-2)" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
        </defs>
        {data.map((d, i) => {
          const h = (d[valueKey] / max) * 92;
          const isHovered = hoverId === i;
          return (
            <g key={i}>
              <rect
                x={i * w + w * 0.15}
                y={100 - h}
                width={w * 0.7}
                height={h}
                rx={0.6}
                fill={`url(#${gradId})`}
                opacity={isHovered ? 1 : 0.9}
                style={{
                  transformBox: "fill-box",
                  transformOrigin: "center bottom",
                  animation: `bar-grow 0.7s cubic-bezier(0.2, 0.7, 0.3, 1) ${i * 25}ms both`,
                  cursor: onDrill ? "pointer" : "default",
                  filter: isHovered ? "brightness(1.15)" : "none",
                  transition: "filter 200ms",
                }}
                onMouseMove={(e) => handleMouseMove(e, d, i)}
                onMouseLeave={() => { setHoverId(null); setTooltip(null); }}
                onClick={() => onDrill?.(d)}
              >
                <title>{`${d[labelKey]}: ${Math.round(d[valueKey]).toLocaleString("en-US")}`}</title>
              </rect>
            </g>
          );
        })}
      </svg>
      {tooltip && (
        <div
          style={{
            position: "absolute",
            left: tooltip.x,
            top: tooltip.y - 40,
            background: "var(--bg-2)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "6px 12px",
            fontSize: 12,
            pointerEvents: "none",
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
            zIndex: 10,
            whiteSpace: "nowrap",
          }}
        >
          <div style={{ fontWeight: 600 }}>{tooltip.label}</div>
          <div style={{ color: "var(--primary)" }}>{tooltip.value}</div>
        </div>
      )}
    </div>
  );
}

export function HBar({ value, max, color = "var(--accent)" }) {
  const pct = Math.min(100, (value / (max || 1)) * 100);
  return (
    <div style={{ background: "color-mix(in srgb, var(--text) 8%, transparent)", borderRadius: 6, height: 8, overflow: "hidden" }}>
      <div
        style={{
          width: `${pct}%`,
          height: "100%",
          borderRadius: 6,
          background: `linear-gradient(90deg, ${color}, var(--primary-2))`,
          animation: "hbar-grow 0.8s cubic-bezier(0.2, 0.7, 0.3, 1) both",
        }}
      />
    </div>
  );
}

// Animated number: eases from 0 to `value` with rAF; re-runs when value changes.
// Pass `format` to control rendering (e.g. locale digits); default is a plain
// rounded toLocaleString.
export function CountUp({ value, duration = 900, format }) {
  const target = Number(value || 0);
  const [display, setDisplay] = useState(0);
  const rafRef = useRef(null);

  useEffect(() => {
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setDisplay(target);
      return;
    }
    const t0 = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(target * eased);
      if (p < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return <>{format ? format(display) : Math.round(display).toLocaleString("en-US")}</>;
}

export function Sparkline({ data, height = 24, color = "var(--primary)", valueKey = "value" }) {
  if (!data || data.length < 2) return <p className="muted">—</p>;
  const values = data.map((d) => d[valueKey]);
  const max = Math.max(...values, 1);
  const min = Math.min(...values);
  const range = max - min || 1;
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 100 - ((v - min) / range) * 80 - 10;
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width: "100%", height, display: "inline-block" }}>
      <polyline points={points} stroke={color} strokeWidth="1.5" fill="none" vectorEffect="non-scaling-stroke" opacity="0.8" />
      <circle cx={100} cy={100 - ((values[values.length - 1] - min) / range) * 80 - 10} r="2" fill={color} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function Donut({ data, height = 180, labelKey = "label", valueKey = "value" }) {
  if (!data || data.length === 0) return <p className="muted">—</p>;
  const total = data.reduce((sum, d) => sum + d[valueKey], 0);
  const colors = ["var(--primary)", "var(--accent)", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];
  let angle = -90;
  const arcs = data.map((d, i) => {
    const sliceAngle = (d[valueKey] / total) * 360;
    const startAngle = angle;
    const endAngle = angle + sliceAngle;
    const rad1 = (startAngle * Math.PI) / 180;
    const rad2 = (endAngle * Math.PI) / 180;
    const x1 = 50 + 30 * Math.cos(rad1);
    const y1 = 50 + 30 * Math.sin(rad1);
    const x2 = 50 + 30 * Math.cos(rad2);
    const y2 = 50 + 30 * Math.sin(rad2);
    const largeArc = sliceAngle > 180 ? 1 : 0;
    const path = `M 50 50 L ${x1} ${y1} A 30 30 0 ${largeArc} 1 ${x2} ${y2} Z`;
    angle = endAngle;
    return { path, color: colors[i % colors.length], label: d[labelKey], value: d[valueKey], pct: ((d[valueKey] / total) * 100).toFixed(1) };
  });
  return (
    <div style={{ display: "flex", gap: 16, alignItems: "center", height }}>
      <svg viewBox="0 0 100 100" style={{ flex: "0 0 120px", height }}>
        {arcs.map((arc, i) => (
          <path key={i} d={arc.path} fill={arc.color} opacity="0.85" style={{ transition: "opacity 200ms" }}>
            <title>{`${arc.label}: ${arc.pct}%`}</title>
          </path>
        ))}
      </svg>
      <div style={{ flex: 1, fontSize: 12 }}>
        {arcs.map((arc, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <div style={{ width: 12, height: 12, borderRadius: 2, background: arc.color }} />
            <span>{arc.label}</span>
            <span style={{ marginLeft: "auto", fontWeight: 600, color: "var(--primary)" }}>{arc.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function StackedBar({ data, height = 180, labelKey = "date", series = [] }) {
  if (!data || data.length === 0) return <p className="muted">—</p>;
  const colors = ["var(--primary)", "var(--accent)", "#10b981", "#f59e0b"];
  const max = Math.max(...data.map((d) => series.reduce((sum, s) => sum + (d[s.key] || 0), 0)), 1);
  const w = 100 / data.length;
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width: "100%", height }}>
      {data.map((d, i) => {
        let y = 100;
        return (
          <g key={i}>
            {series.map((s, j) => {
              const h = ((d[s.key] || 0) / max) * 92;
              const startY = y - h;
              y = startY;
              return (
                <rect
                  key={j}
                  x={i * w + w * 0.15}
                  y={startY}
                  width={w * 0.7}
                  height={h}
                  fill={colors[j % colors.length]}
                  opacity="0.85"
                  style={{ animation: `bar-grow 0.7s cubic-bezier(0.2, 0.7, 0.3, 1) ${i * 25 + j * 10}ms both` }}
                >
                  <title>{`${d[labelKey]} - ${s.label}: ${Math.round(d[s.key] || 0).toLocaleString("en-US")}`}</title>
                </rect>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}

export function BulletBar({ actual, target, max, label, color = "var(--primary)" }) {
  const actualPct = Math.min(100, (actual / (max || 1)) * 100);
  const targetPct = (target / (max || 1)) * 100;
  const status = actual >= target ? "ok" : actual >= target * 0.8 ? "warning" : "danger";
  const statusColor = { ok: "var(--ok)", warning: "#f59e0b", danger: "var(--danger)" };
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 12 }}>
        <span>{label}</span>
        <span style={{ fontWeight: 600, color: statusColor[status] }}>
          {Math.round(actual).toLocaleString("en-US")} / {Math.round(target).toLocaleString("en-US")}
        </span>
      </div>
      <div style={{ background: "color-mix(in srgb, var(--text) 8%, transparent)", borderRadius: 4, height: 16, overflow: "hidden", position: "relative" }}>
        <div
          style={{
            width: `${actualPct}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${color}, var(--primary-2))`,
            borderRadius: 4,
            transition: "width 800ms cubic-bezier(0.2, 0.7, 0.3, 1)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: `${targetPct}%`,
            top: 0,
            height: "100%",
            borderLeft: `2px solid ${statusColor[status]}`,
            opacity: 0.7,
          }}
        />
      </div>
    </div>
  );
}

export function Heatmap({ data, rows = [], cols = [], valueKey = "value", height = 200 }) {
  if (!data || data.length === 0) return <p className="muted">—</p>;
  const max = Math.max(...data.map((d) => d[valueKey] || 0), 1);
  const getCellColor = (val) => {
    const norm = (val || 0) / max;
    if (norm < 0.25) return "#e0f2fe";
    if (norm < 0.5) return "#7dd3fc";
    if (norm < 0.75) return "#38bdf8";
    if (norm < 0.9) return "#0284c7";
    return "#0c4a6e";
  };
  return (
    <svg viewBox={`0 0 ${cols.length * 20} ${rows.length * 20}`} style={{ width: "100%", height }}>
      {rows.map((row, ri) =>
        cols.map((col, ci) => {
          const cell = data.find((d) => d.row === row && d.col === col);
          const val = cell?.[valueKey] || 0;
          return (
            <g key={`${ri}-${ci}`}>
              <rect
                x={ci * 20}
                y={ri * 20}
                width={20}
                height={20}
                fill={getCellColor(val)}
                stroke="var(--border)"
                strokeWidth="0.5"
              >
                <title>{`${row} × ${col}: ${Math.round(val).toLocaleString("en-US")}`}</title>
              </rect>
            </g>
          );
        })
      )}
    </svg>
  );
}
