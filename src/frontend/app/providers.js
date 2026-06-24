"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

const UIContext = createContext(null);

export function useUI() {
  const ctx = useContext(UIContext);
  if (!ctx) throw new Error("useUI must be used within <Providers>");
  return ctx;
}

const LANG_KEY = "procare.lang";
const THEME_KEY = "procare.theme";

export default function Providers({ children }) {
  // SSR-safe defaults: Arabic + Light. Real values hydrate from localStorage.
  const [lang, setLang] = useState("ar");
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    const l = localStorage.getItem(LANG_KEY);
    const t = localStorage.getItem(THEME_KEY);
    if (l === "ar" || l === "en") setLang(l);
    if (t === "light" || t === "dark") setTheme(t);
  }, []);

  useEffect(() => {
    const el = document.documentElement;
    el.lang = lang;
    el.dir = lang === "ar" ? "rtl" : "ltr"; // RTL for Arabic, LTR for English
    localStorage.setItem(LANG_KEY, lang);
  }, [lang]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const toggleLang = useCallback(
    () => setLang((p) => (p === "ar" ? "en" : "ar")),
    []
  );
  const toggleTheme = useCallback(
    () => setTheme((p) => (p === "light" ? "dark" : "light")),
    []
  );

  return (
    <UIContext.Provider value={{ lang, theme, toggleLang, toggleTheme }}>
      {children}
    </UIContext.Provider>
  );
}
