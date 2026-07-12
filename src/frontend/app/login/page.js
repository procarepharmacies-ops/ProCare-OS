"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useUI } from "../providers";
import { t } from "../i18n";
import { api } from "../api";
import Wordmark from "../components/Wordmark";

export default function LoginPage() {
  const { lang, theme, toggleLang, toggleTheme, login } = useUI();
  const router = useRouter();
  const L = (k) => t(lang, k);

  // mode: "login" → "forgot" (send code) → "reset" (code + new password)
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [shake, setShake] = useState(false);
  const [revealing, setRevealing] = useState(false);
  const [greetName, setGreetName] = useState("");

  function fail(message) {
    setBusy(false);
    setError(message || L("login_error"));
    setShake(true);
    setTimeout(() => setShake(false), 500);
  }

  async function submitLogin(e) {
    e.preventDefault();
    if (!username || !password || busy) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.auth.login(username.trim(), password);
      login(r.token, r.employee);
      setGreetName(lang === "ar" ? r.employee.name_ar : r.employee.name_en || r.employee.name_ar);
      setBusy(false);
      setRevealing(true);
      // Let the logo-assembly animation play, then hand off to the dashboard.
      setTimeout(() => router.replace("/"), 1700);
    } catch {
      fail(L("login_error"));
    }
  }

  async function submitForgot(e) {
    e.preventDefault();
    if (!username || busy) return;
    setBusy(true);
    setError("");
    try {
      await api.auth.forgotPassword(username.trim());
      setBusy(false);
      setNotice(L("code_sent"));
      setMode("reset");
    } catch (err) {
      fail(err?.detail?.message || err?.message || L("login_error"));
    }
  }

  async function submitReset(e) {
    e.preventDefault();
    if (!username || !code || !newPassword || busy) return;
    setBusy(true);
    setError("");
    try {
      await api.auth.resetPassword(username.trim(), code.trim(), newPassword);
      setBusy(false);
      setNotice(L("reset_done"));
      setPassword("");
      setCode("");
      setNewPassword("");
      setMode("login");
    } catch (err) {
      fail(err?.detail?.message || err?.message || L("login_error"));
    }
  }

  function switchMode(next) {
    setMode(next);
    setError("");
    setNotice("");
  }

  return (
    <div className="login-screen">
      {/* Ambient animated brand orbs the glass card blurs against. */}
      <div className="login-orb orb-a" aria-hidden />
      <div className="login-orb orb-b" aria-hidden />
      <div className="login-orb orb-c" aria-hidden />

      <div className="login-toolbar">
        <button className="btn icon" onClick={toggleLang} title="language / اللغة">
          {lang === "ar" ? "EN" : "ع"}
        </button>
        <button className="btn icon" onClick={toggleTheme} title="theme / المظهر">
          {theme === "light" ? "🌙" : "☀️"}
        </button>
      </div>

      <div className={`login-card card glass-strong ${shake ? "shake" : ""}`}>
        <div className="login-mark login-mark-float">
          <span className="login-mark-halo" aria-hidden />
          <Wordmark size={64} />
        </div>
        <h1 className="login-app-name">{L("app")}</h1>
        <p className="login-tagline">{L("tagline")}</p>

        {mode === "login" && (
          <form onSubmit={submitLogin} className="login-form">
            <h2 className="login-title">{L("login_title")}</h2>

            <label className="login-field">
              <span>{L("username")}</span>
              <input
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                autoComplete="username"
                autoCapitalize="none"
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

            {notice && <p className="login-notice">{notice}</p>}
            {error && <p className="login-error">{error}</p>}

            <button className="btn primary login-submit" type="submit" disabled={busy || !username || !password}>
              {busy ? L("logging_in") : L("login_button")}
            </button>

            <button type="button" className="login-link" onClick={() => switchMode("forgot")}>
              {L("forgot_password")}
            </button>
          </form>
        )}

        {mode === "forgot" && (
          <form onSubmit={submitForgot} className="login-form">
            <h2 className="login-title">{L("reset_title")}</h2>
            <p className="login-hint">{L("reset_intro")}</p>

            <label className="login-field">
              <span>{L("username")}</span>
              <input
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                autoComplete="username"
                autoCapitalize="none"
              />
            </label>

            {error && <p className="login-error">{error}</p>}

            <button className="btn primary login-submit" type="submit" disabled={busy || !username}>
              {busy ? L("sending") : L("send_code")}
            </button>

            <button type="button" className="login-link" onClick={() => switchMode("login")}>
              {L("back_to_login")}
            </button>
          </form>
        )}

        {mode === "reset" && (
          <form onSubmit={submitReset} className="login-form">
            <h2 className="login-title">{L("reset_title")}</h2>
            {notice && <p className="login-notice">{notice}</p>}

            <label className="login-field">
              <span>{L("reset_code")}</span>
              <input
                className="input login-code"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                inputMode="numeric"
                autoFocus
                placeholder="••••••"
              />
            </label>

            <label className="login-field">
              <span>{L("new_password")}</span>
              <input
                className="input"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
              />
            </label>

            {error && <p className="login-error">{error}</p>}

            <button
              className="btn primary login-submit"
              type="submit"
              disabled={busy || code.length !== 6 || newPassword.length < 8}
            >
              {busy ? L("resetting") : L("confirm_reset")}
            </button>

            <button type="button" className="login-link" onClick={() => switchMode("login")}>
              {L("back_to_login")}
            </button>
          </form>
        )}
      </div>

      {revealing && <LogoRevealOverlay greetName={greetName} lang={lang} />}
    </div>
  );
}

// Post-login flourish: the real ProCare logo scales in with a glow, then the
// welcome line + slogan fade up underneath it.
function LogoRevealOverlay({ greetName, lang }) {
  return (
    <div className="reveal-overlay">
      <div className="reveal-part reveal-part-plate">
        <Wordmark size={140} />
      </div>
      <div className="reveal-text">
        <div className="reveal-welcome">
          {t(lang, "welcome_back")}, {greetName}
        </div>
        <div className="reveal-slogan">{t(lang, "tagline")}</div>
      </div>
    </div>
  );
}
