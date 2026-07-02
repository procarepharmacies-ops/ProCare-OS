"use client";

// Dependency-free SVG charts — keep the skeleton's "zero extra deps" principle.
// Bars grow in with a staggered CSS animation (bar-grow / hbar-grow keyframes
// live in globals.css and are disabled under prefers-reduced-motion).

import { useEffect, useId, useRef, useState } from "react";

export function BarChart({ data, height = 180, color = "var(--primary)", labelKey = "date", valueKey = "revenue" }) {
  const gradId = useId();
  if (!data || data.length === 0) return <p className="muted">—</p>;
  const max = Math.max(...data.map((d) => d[valueKey]), 1);
  const w = 100 / data.length;
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width: "100%", height }}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary-2)" />
          <stop offset="100%" stopColor={color} />
        </linearGradient>
      </defs>
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
            fill={`url(#${gradId})`}
            opacity={0.9}
            style={{
              transformBox: "fill-box",
              transformOrigin: "center bottom",
              animation: `bar-grow 0.7s cubic-bezier(0.2, 0.7, 0.3, 1) ${i * 25}ms both`,
            }}
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

  return <>{format ? format(display) : Math.round(display).toLocaleString()}</>;
}
