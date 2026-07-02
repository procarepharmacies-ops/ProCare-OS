"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, session as sessionStore } from "./api";

const UIContext = createContext(null);

export function useUI() {
  const ctx = useContext(UIContext);
  if (!ctx) throw new Error("useUI must be used within <Providers>");
  return ctx;
}

const LANG_KEY = "procare.lang";
const THEME_KEY = "procare.theme";
const BRANCH_KEY = "procare.branch";

export default function Providers({ children }) {
  // SSR-safe defaults: Arabic + Light. Real values hydrate from localStorage.
  const [lang, setLang] = useState("ar");
  const [theme, setTheme] = useState("light");
  const [branch, setBranch] = useState(0); // 0 = all branches (consolidated)
  const [branches, setBranches] = useState([]);
  const [online, setOnline] = useState(null);
  const [user, setUser] = useState(null); // { employee_id, name_ar, name_en, role, branch_id }
  const [authChecked, setAuthChecked] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    const l = localStorage.getItem(LANG_KEY);
    const t = localStorage.getItem(THEME_KEY);
    const b = localStorage.getItem(BRANCH_KEY);
    if (l === "ar" || l === "en") setLang(l);
    if (t === "light" || t === "dark") setTheme(t);
    if (b != null) setBranch(Number(b) || 0);

    const saved = sessionStore.get();
    setUser(saved?.employee || null);
    setAuthChecked(true);
  }, []);

  // Client-side login gate: every page except /login requires a session.
  useEffect(() => {
    if (!authChecked) return;
    if (!user && pathname !== "/login") {
      router.replace("/login");
    }
  }, [authChecked, user, pathname, router]);

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

  useEffect(() => {
    localStorage.setItem(BRANCH_KEY, String(branch));
  }, [branch]);

  // Load branches + liveness once a session exists (avoids noisy 401s pre-login).
  useEffect(() => {
    if (!user) return;
    let alive = true;
    (async () => {
      try {
        const [h, b] = await Promise.all([api.health(), api.branches()]);
        if (!alive) return;
        setOnline(Boolean(h));
        setBranches(b.branches || []);
      } catch {
        if (alive) setOnline(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [user]);

  const toggleLang = useCallback(() => setLang((p) => (p === "ar" ? "en" : "ar")), []);
  const toggleTheme = useCallback(() => setTheme((p) => (p === "light" ? "dark" : "light")), []);

  const login = useCallback((token, employee) => {
    sessionStore.set({ token, employee });
    setUser(employee);
  }, []);

  const logout = useCallback(() => {
    sessionStore.clear();
    setUser(null);
    router.replace("/login");
  }, [router]);

  return (
    <UIContext.Provider
      value={{
        lang,
        theme,
        branch,
        branches,
        online,
        user,
        authChecked,
        setBranch,
        toggleLang,
        toggleTheme,
        login,
        logout,
      }}
    >
      {children}
    </UIContext.Provider>
  );
}
