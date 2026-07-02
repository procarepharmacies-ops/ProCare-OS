"use client";

// Temporary brand mark — a simple "P" monogram in the two real ProCare brand
// colors (blue #1a76b4 -> lime #8cc63f, taken from the actual logo). This is
// NOT a redraw of the illustrated ProCare logo (mortar/figure/ring artwork) —
// that needs the real logo file dropped into this component once it's
// available as an actual asset (e.g. src/frontend/public/logo.svg), replacing
// the <svg> below with an <img src="/logo.svg" />.
export default function Wordmark({ size = 38 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <linearGradient id="procare-mark-grad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="var(--primary)" />
          <stop offset="100%" stopColor="var(--primary-2)" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill="url(#procare-mark-grad)" />
      <text
        x="20"
        y="27"
        textAnchor="middle"
        fontFamily="var(--font-cairo), sans-serif"
        fontWeight="800"
        fontSize="20"
        fill="#fff"
      >
        P
      </text>
    </svg>
  );
}
