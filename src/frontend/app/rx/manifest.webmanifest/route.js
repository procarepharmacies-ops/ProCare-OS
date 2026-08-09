// ProCare RX — a SECOND installable PWA served from the same origin.
//
// Installability is per (id, start_url, scope), not per origin, so one Next.js
// app can ship two home-screen apps: the full desktop system at "/" and this
// phone-first الجرد app at "/rx". Staff get a distinct icon, name and window —
// and Bubblewrap can wrap this manifest into its own APK — without forking the
// codebase into a second repo that would have to duplicate auth, i18n, the API
// client and the GS1 parser.
//
// A Route Handler rather than a second app/manifest.js: that convention is
// root-only. app/rx/layout.js points at this file via `metadata.manifest`,
// which overrides the root manifest link for everything under /rx.

export const dynamic = "force-static";

export function GET() {
  const manifest = {
    name: "ProCare RX — الجرد",
    short_name: "ProCare RX",
    description:
      "جرد المخزون بالباركود من الموبايل — Barcode stocktaking for pharmacy staff",
    id: "/rx",
    start_url: "/rx",
    scope: "/rx",
    display: "standalone",
    // Portrait: this is a one-handed, scan-in-the-aisle app.
    orientation: "portrait",
    dir: "rtl",
    lang: "ar",
    background_color: "#0f2027",
    theme_color: "#0a7d5a",
    icons: [
      { src: "/rx/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/rx/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/rx/maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/rx/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      {
        name: "جرد جديد / New count",
        url: "/rx/count",
        icons: [{ src: "/rx/icon-192.png", sizes: "192x192" }],
      },
    ],
  };
  return new Response(JSON.stringify(manifest, null, 2), {
    headers: { "content-type": "application/manifest+json" },
  });
}
