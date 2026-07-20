// Web app manifest — makes ProCare installable like a native app (home-screen
// icon on Android/iOS, desktop app window on Chrome/Edge). Served by Next.js
// at /manifest.webmanifest and linked automatically from every page.
export default function manifest() {
  return {
    name: "ProCare AI — نظام الصيدلية",
    short_name: "ProCare",
    description:
      "Procare Pharmacies operating system — POS, inventory, purchasing, accounting, AI assistant. مش مجرد صيدلية… عيلة لكل احتياجاتك",
    id: "/",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "any",
    dir: "rtl",
    lang: "ar",
    background_color: "#f6f8fa",
    theme_color: "#0a7d5a",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "قارئ الروشتات / Rx Camera", url: "/prescriptions?mode=camera", icons: [{ src: "/icon-192.png", sizes: "192x192" }] },
      { name: "نقطة البيع / POS", url: "/pos", icons: [{ src: "/icon-192.png", sizes: "192x192" }] },
      { name: "المخزون / Inventory", url: "/inventory", icons: [{ src: "/icon-192.png", sizes: "192x192" }] },
      { name: "التقارير / Reports", url: "/reports", icons: [{ src: "/icon-192.png", sizes: "192x192" }] },
    ],
  };
}
