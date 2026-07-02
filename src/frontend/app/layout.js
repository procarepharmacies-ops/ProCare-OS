import "./globals.css";
import { Cairo } from "next/font/google";
import Providers from "./providers";

// Cairo — the Arabic-first brand typeface (also covers Latin), self-hosted at
// build time via next/font so it works fully offline on the pharmacy LAN.
const cairo = Cairo({
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-cairo",
  display: "swap",
});

export const metadata = {
  title: "ProCare AI",
  description: "Independent pharmacy operating system",
};

// Apply saved lang/dir/theme before first paint to avoid a flash and to keep
// SSR output (ar / rtl / light) consistent with what the client restores.
const noFlash = `(function(){try{
  var l=localStorage.getItem('procare.lang')||'ar';
  var t=localStorage.getItem('procare.theme')||'light';
  document.documentElement.lang=l;
  document.documentElement.dir=(l==='ar')?'rtl':'ltr';
  document.documentElement.setAttribute('data-theme',t);
}catch(e){}})();`;

export default function RootLayout({ children }) {
  return (
    <html lang="ar" dir="rtl" data-theme="light" className={cairo.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: noFlash }} />
      </head>
      <body suppressHydrationWarning>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
