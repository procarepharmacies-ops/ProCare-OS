import "./rx.css";
import RXShell from "../components/rx/RXShell";

export const metadata = {
  title: "ProCare RX",
  applicationName: "ProCare RX",
  // Overrides the root manifest for everything under /rx, which is what makes
  // this install as its own app with its own icon rather than as the desktop one.
  manifest: "/rx/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "ProCare RX" },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  // REQUIRED for env(safe-area-inset-*) to report anything but 0 — without it
  // the bottom tab bar sits under the home indicator on notched phones.
  viewportFit: "cover",
  themeColor: "#0a7d5a",
};

// Registered with an explicit /rx/ scope so it takes precedence over the root
// worker for RX navigations (longest matching scope wins).
const swRegister = `if('serviceWorker' in navigator){window.addEventListener('load',function(){
  navigator.serviceWorker.register('/rx/sw.js',{scope:'/rx/'}).catch(function(){})
})}`;

export default function RXLayout({ children }) {
  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: swRegister }} />
      <RXShell>{children}</RXShell>
    </>
  );
}
