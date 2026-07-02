"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";

export default function LoginPage() {
  const { lang, theme, toggleLang, toggleTheme, login } = useUI();
  const router = useRouter();
  const L = (k) => t(lang, k);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [shake, setShake] = useState(false);
  const [revealing, setRevealing] = useState(false);
  const [greetName, setGreetName] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!username || !password || busy) return;
    setBusy(true);
    setError(false);
    try {
      const r = await api.auth.login(username, password);
      login(r.token, r.employee);
      setGreetName(lang === "ar" ? r.employee.name_ar : r.employee.name_en || r.employee.name_ar);
      setBusy(false);
      setRevealing(true);
      // Let the logo-assembly animation play, then hand off to the dashboard.
      setTimeout(() => router.replace("/"), 1700);
    } catch {
      setBusy(false);
      setError(true);
      setShake(true);
      setTimeout(() => setShake(false), 500);
    }
  }

  return (
    <div className="login-screen">
      <div className="login-toolbar">
        <button className="btn icon" onClick={toggleLang} title="language / اللغة">
          {lang === "ar" ? "EN" : "ع"}
        </button>
        <button className="btn icon" onClick={toggleTheme} title="theme / المظهر">
          {theme === "light" ? "🌙" : "☀️"}
        </button>
      </div>

      <div className={`login-card card ${shake ? "shake" : ""}`}>
        <div className="login-mark">
          <LogoMark />
        </div>
        <h1 className="login-app-name">{L("app")}</h1>
        <p className="login-tagline">{L("tagline")}</p>

        <form onSubmit={submit} className="login-form">
          <h2 className="login-title">{L("login_title")}</h2>

          <label className="login-field">
            <span>{L("username")}</span>
            <input
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              autoComplete="username"
            />
          </label>

          <label className="login-field">
            <span>{L("password")}</span>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>

          {error && <p className="login-error">{L("login_error")}</p>}

          <button className="btn primary login-submit" type="submit" disabled={busy || !username || !password}>
            {busy ? L("logging_in") : L("login_button")}
          </button>
        </form>
      </div>

      {revealing && <LogoRevealOverlay greetName={greetName} lang={lang} />}
    </div>
  );
}

// The brand mark used on the login card itself — a static, calm version.
function LogoMark({ size = 56 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <linearGradient id="login-mark-grad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="var(--primary)" />
          <stop offset="100%" stopColor="var(--primary-2)" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill="url(#login-mark-grad)" />
      <path d="M9 13.5C9 9.9 12.1 7 16 7" stroke="#fff" strokeOpacity="0.55" strokeWidth="2.1" strokeLinecap="round" />
      <path d="M31 26.5c0 3.6-3.1 6.5-7 6.5" stroke="#fff" strokeOpacity="0.55" strokeWidth="2.1" strokeLinecap="round" />
      <path d="M17 12.2h6v4.8h4.8v6h-4.8v4.8h-6v-4.8h-4.8v-6H17z" fill="#fff" />
    </svg>
  );
}

// Post-login flourish: the brand mark's three parts fly in from the corners
// and assemble, then the welcome line + slogan fade up. This is a generic
// placeholder built from primitives — swap the three <g> pieces below for the
// real ProCare logo's parts the moment that artwork is available; the timing
// and stage choreography stay the same.
function LogoRevealOverlay({ greetName, lang }) {
  return (
    <div className="reveal-overlay">
      <svg width="140" height="140" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="reveal-grad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="var(--primary)" />
            <stop offset="100%" stopColor="var(--primary-2)" />
          </linearGradient>
        </defs>
        <rect className="reveal-part reveal-part-plate" width="40" height="40" rx="11" fill="url(#reveal-grad)" />
        <path
          className="reveal-part reveal-part-arc-l"
          d="M9 13.5C9 9.9 12.1 7 16 7"
          stroke="#fff"
          strokeOpacity="0.6"
          strokeWidth="2.1"
          strokeLinecap="round"
        />
        <path
          className="reveal-part reveal-part-arc-r"
          d="M31 26.5c0 3.6-3.1 6.5-7 6.5"
          stroke="#fff"
          strokeOpacity="0.6"
          strokeWidth="2.1"
          strokeLinecap="round"
        />
        <path
          className="reveal-part reveal-part-cross"
          d="M17 12.2h6v4.8h4.8v6h-4.8v4.8h-6v-4.8h-4.8v-6H17z"
          fill="#fff"
        />
      </svg>
      <div className="reveal-text">
        <div className="reveal-welcome">
          {t(lang, "welcome_back")}, {greetName}
        </div>
        <div className="reveal-slogan">{t(lang, "tagline")}</div>
      </div>
    </div>
  );
}
