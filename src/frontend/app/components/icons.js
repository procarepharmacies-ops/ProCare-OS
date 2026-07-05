"use client";

// Pharmaceutical icon set — dependency-free inline SVG, stroke-based so icons
// inherit currentColor (works on the gradient nav pill and in both themes).
// All icons share a 24×24 viewBox and round caps for a consistent visual weight.

const P = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7.5" height="9.5" rx="2" />
      <rect x="13.5" y="3" width="7.5" height="5.5" rx="2" />
      <rect x="13.5" y="11.5" width="7.5" height="9.5" rx="2" />
      <rect x="3" y="15.5" width="7.5" height="5.5" rx="2" />
    </>
  ),
  // Capsule pill split by its seam — inventory.
  pill: (
    <>
      <rect x="5" y="8.5" width="14" height="7" rx="3.5" transform="rotate(-45 12 12)" />
      <line x1="9.6" y1="9.6" x2="14.4" y2="14.4" />
    </>
  ),
  // Receipt with a torn edge — point of sale.
  receipt: (
    <>
      <path d="M6.5 3h11v18l-1.9-1.4-1.8 1.4-1.8-1.4-1.8 1.4-1.8-1.4L6.5 21z" />
      <line x1="9.5" y1="8" x2="14.5" y2="8" />
      <line x1="9.5" y1="12" x2="14.5" y2="12" />
    </>
  ),
  customers: (
    <>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3.5 20c0-3.1 2.4-5.2 5.5-5.2s5.5 2.1 5.5 5.2" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M16.4 15.1c2.4.4 4.1 2.2 4.1 4.9" />
    </>
  ),
  // Storefront awning — vendors/suppliers.
  store: (
    <>
      <path d="M4.5 9.8V20h15V9.8" />
      <path d="M3.5 6.5 5 3.5h14l1.5 3c0 1.5-1.2 2.7-2.7 2.7-1.1 0-2-.6-2.5-1.5-.5.9-1.4 1.5-2.5 1.5s-2-.6-2.5-1.5c-.5.9-1.4 1.5-2.5 1.5-1.5 0-2.8-1.2-2.8-2.7z" />
      <path d="M9.5 20v-5.5h5V20" />
    </>
  ),
  // Sealed carton — purchasing.
  box: (
    <>
      <path d="M3.5 7.6 12 3.2l8.5 4.4v8.8L12 20.8l-8.5-4.4z" />
      <path d="M3.5 7.6 12 12l8.5-4.4" />
      <line x1="12" y1="12" x2="12" y2="20.8" />
    </>
  ),
  // Two-way arrows — inter-branch transfers.
  transfer: (
    <>
      <path d="M4 8h13" />
      <path d="M14 5l3 3-3 3" />
      <path d="M20 16H7" />
      <path d="M10 13l-3 3 3 3" />
    </>
  ),
  // Coin stack — accounting.
  coins: (
    <>
      <ellipse cx="12" cy="5.5" rx="7" ry="2.8" />
      <path d="M5 5.5v6.5c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8V5.5" />
      <path d="M5 12v6.5c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8V12" />
    </>
  ),
  // ID badge — employees.
  badge: (
    <>
      <rect x="4.5" y="3.5" width="15" height="17" rx="2.5" />
      <circle cx="12" cy="10" r="2.5" />
      <path d="M7.5 17.5c.6-2.2 2.4-3.5 4.5-3.5s3.9 1.3 4.5 3.5" />
    </>
  ),
  bell: (
    <>
      <path d="M18.5 16h-13c1.3-1.3 2.1-2.1 2.1-6.2a4.4 4.4 0 018.8 0c0 4.1.8 4.9 2.1 6.2z" />
      <path d="M10.4 19a1.7 1.7 0 003.2 0" />
    </>
  ),
  // Mortar & pestle — clinical advisory.
  mortar: (
    <>
      <path d="M4.5 10.5h15c-.3 3.2-2.2 5.5-5.4 6.3l.6 3.2H9.3l.6-3.2c-3.2-.8-5.1-3.1-5.4-6.3z" />
      <path d="M15.8 3.2c1 .9 1.2 1.8.5 2.7l-3.2 4.4" />
    </>
  ),
  // Chat bubble with a sparkle — AI assistant.
  sparkle: (
    <>
      <path d="M21 11.5a8.5 8.5 0 01-12.4 7.5L3 21l2-5.6A8.5 8.5 0 1121 11.5z" />
      <path d="M12 7.8l.9 2.2 2.2.9-2.2.9-.9 2.2-.9-2.2-2.2-.9 2.2-.9z" />
    </>
  ),
  // Trend line over axes — reports.
  chart: (
    <>
      <path d="M4 4v16h16" />
      <path d="M7.5 15.5l3.5-4.2 3 2.6 4.5-6" />
    </>
  ),
  // Megaphone — marketing / campaigns.
  megaphone: (
    <>
      <path d="M3 10.5v3a1.5 1.5 0 001.5 1.5H7l9 4.5v-15L7 9H4.5A1.5 1.5 0 003 10.5z" />
      <path d="M16 9.5a3.5 3.5 0 010 5M7.5 15.2l1 4.3h2.6l-.8-4" />
    </>
  ),
  gear: (
    <>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6M5.4 5.4l1.9 1.9M16.7 16.7l1.9 1.9M18.6 5.4l-1.9 1.9M7.3 16.7l-1.9 1.9" />
    </>
  ),
  // Clipboard with a check — daily tasks.
  clipboard: (
    <>
      <rect x="5" y="4.5" width="14" height="17" rx="2.5" />
      <path d="M9 4.5V3.2h6v1.3" />
      <path d="M8.8 13.2l2.2 2.2 4.2-4.6" />
    </>
  ),
  // Door with an exit arrow — log out.
  logout: (
    <>
      <path d="M14.5 4.5H7a1.5 1.5 0 00-1.5 1.5v12A1.5 1.5 0 007 19.5h7.5" />
      <path d="M11 12h9.5" />
      <path d="M17 8.5l3.5 3.5-3.5 3.5" />
    </>
  ),
  // Pharmacy cross — the brand mark.
  cross: (
    <>
      <path d="M9.3 3.8h5.4v5.5h5.5v5.4h-5.5v5.5H9.3v-5.5H3.8V9.3h5.5z" />
    </>
  ),
  // Camera — prescription reader.
  camera: (
    <>
      <path d="M4 8.5A2 2 0 016 6.5h2l1.4-2h5.2l1.4 2h2a2 2 0 012 2V18a2 2 0 01-2 2H6a2 2 0 01-2-2z" />
      <circle cx="12" cy="13" r="3.4" />
    </>
  ),
  // Safe / vault — treasury.
  safe: (
    <>
      <rect x="3.5" y="4" width="17" height="15" rx="2" />
      <circle cx="12" cy="11.5" r="3.4" />
      <path d="M12 8.1v1.4M12 13.5v1.4M8.6 11.5H10M14 11.5h1.4" />
      <path d="M6.5 19v1.8M17.5 19v1.8" />
    </>
  ),
  // Sheet with lines — shortage sheet.
  sheet: (
    <>
      <path d="M6 3.5h9l3.5 3.5v13.5H6z" />
      <path d="M15 3.5V7h3.5" />
      <line x1="8.5" y1="11" x2="15.5" y2="11" />
      <line x1="8.5" y1="14.5" x2="15.5" y2="14.5" />
      <line x1="8.5" y1="18" x2="12.5" y2="18" />
    </>
  ),
  moon: <path d="M20 14.5A8 8 0 119.5 4a6.5 6.5 0 0010.5 10.5z" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
    </>
  ),
};

export default function Icon({ name, size = 20, strokeWidth = 1.8, ...props }) {
  const shape = P[name];
  if (!shape) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {shape}
    </svg>
  );
}
