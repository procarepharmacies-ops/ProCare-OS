"""Agent orchestration — status, dispatch, audit (absorbed from AgenticOS v2.0).

Detects four agents on this machine and can dispatch tasks to them with
human-confirm guards. Agent run history is stored in ProCare's own SQL
database (agent_runs table) — not a flat JSONL file.

Safety rules (from claude.md / CLAUDE.md):
  1. No agent writes to SQL/Slack/vault without explicit human confirm.
  2. Gemini = non-sensitive tasks only (data leaves to Google).
  3. Every dispatched run audited to the agent_runs table.
  4. MCP agent dispatch defaults to dry_run=true.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
import urllib.request
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.db import models as m

HERMES_URL = os.environ.get("HERMES_URL", "http://127.0.0.1:5000")
# Hermes runs as a LOCAL Ollama model (no data leaves the machine), so it works
# offline and needs no API key. OLLAMA_URL is the daemon; HERMES_MODEL is the
# model it drives (qwen2.5 handles Arabic well). If Ollama is reachable, Hermes
# is online AND dispatchable.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
HERMES_MODEL = os.environ.get("HERMES_MODEL", "gemma3:1b-it-qat")
DISPATCH_TIMEOUT = int(os.environ.get("DISPATCH_TIMEOUT", "300"))
DRY_RUN_DEFAULT = os.environ.get("MCP_AGENT_DRY_RUN", "true").lower() != "false"

# The Hermes Agent CLI is pip-installed into its own venv, which is NOT on the
# service's PATH, so `_which` alone finds nothing. Look there explicitly.
# Override with HERMES_CLI when it lives somewhere else.
_HERMES_CLI_FALLBACK = os.path.join(
    os.environ.get("LOCALAPPDATA", r"C:\Users\Default\AppData\Local"),
    "hermes", "hermes-agent", "venv", "Scripts", "hermes.exe",
)


def _hermes_cli() -> str | None:
    """Path to the Hermes Agent CLI, or None when it is not installed."""
    explicit = os.environ.get("HERMES_CLI")
    if explicit and os.path.exists(explicit):
        return explicit
    found = _which("hermes")
    if found:
        return found
    return _HERMES_CLI_FALLBACK if os.path.exists(_HERMES_CLI_FALLBACK) else None


def _ollama_up() -> bool:
    return _http_ok(OLLAMA_URL.rstrip("/") + "/api/tags")


def hermes_mode() -> str | None:
    """How Hermes can be reached right now, or None when it cannot.

      * ``"cli"``    — the Hermes Agent CLI. It answers through whatever
        provider the CLI is logged into (Nous Portal by default), so the task
        text DOES leave this machine.
      * ``"ollama"`` — a local Ollama daemon. Nothing leaves the machine.

    The CLI is preferred because it is what the owner actually runs; Ollama is
    kept for fully-offline installs. The distinction is not cosmetic — it
    decides whether the dry-run/confirm guard applies (see ``dispatch``).
    """
    if _hermes_cli():
        return "cli"
    if _ollama_up():
        return "ollama"
    return None


def _run_hermes_cli(task: str) -> str:
    """Run the task through the Hermes Agent CLI (`hermes -z <prompt>`)."""
    exe = _hermes_cli()
    if not exe:
        raise RuntimeError("Hermes Agent CLI not installed")
    r = subprocess.run(
        [exe, "-z", task],
        capture_output=True, text=True, timeout=DISPATCH_TIMEOUT, shell=False,
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "")[-300:])
    return (r.stdout or "").strip() or "(no text)"


def _run_hermes_ollama(task: str) -> str:
    """Run a task on the local Ollama model. Local + private: nothing leaves
    the machine, so it is safe for sensitive pharmacy data."""
    url = OLLAMA_URL.rstrip("/") + "/api/chat"
    body = json.dumps({
        "model": HERMES_MODEL,
        "messages": [{"role": "user", "content": task}],
        "stream": False,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=DISPATCH_TIMEOUT) as r:
        data = json.loads(r.read())
    return (data.get("message", {}) or {}).get("content", "") or "(no text)"


def _run_hermes(task: str) -> str:
    """Dispatch to whichever Hermes transport is available, CLI first."""
    mode = hermes_mode()
    if mode == "cli":
        return _run_hermes_cli(task)
    if mode == "ollama":
        return _run_hermes_ollama(task)
    raise RuntimeError("Hermes unavailable: no CLI installed and Ollama is not running")


def _http_ok(url: str, timeout: int = 3) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


def _which(binname: str) -> str | None:
    """Windows-aware which: checks PATH incl .exe/.cmd/.bat shims."""
    for cand in (binname, binname + ".exe", binname + ".cmd", binname + ".bat"):
        p = shutil.which(cand)
        if p:
            return p
    return None


def agent_status() -> dict:
    """Return the online/offline/dispatchable state of all registered agents."""
    agents = []

    # Hermes = the Hermes Agent CLI (hosted, via whatever provider it is logged
    # into) or a local Ollama daemon for offline installs. `detail` names which,
    # because only the Ollama path keeps the task text on this machine.
    hmode = hermes_mode()
    agents.append({
        "id": "hermes", "label": "Hermes Ops", "label_ar": "هيرمس العمليات",
        "kind": "ops", "online": hmode is not None,
        "detail": {
            "cli": "Hermes Agent CLI · hosted (task text leaves this machine)",
            "ollama": f"local · {HERMES_MODEL}",
        }.get(hmode, "offline (no Hermes CLI, and Ollama not running on :11434)"),
        "dispatchable": hmode is not None,
        "local": hmode == "ollama",
    })

    # Claude Code CLI
    claude_path = _which("claude")
    agents.append({
        "id": "claude", "label": "Claude Code", "label_ar": "كلود كود",
        "kind": "reasoning", "online": claude_path is not None,
        "detail": "ready" if claude_path else "CLI not found",
        "dispatchable": claude_path is not None,
    })

    # Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    gem_cli = _which("gemini")
    gem_ok = bool(gemini_key) or gem_cli is not None
    agents.append({
        "id": "gemini", "label": "Gemini", "label_ar": "جيميناي",
        "kind": "fast", "online": gem_ok,
        "detail": "ready (non-sensitive only)" if gem_ok else "no API key / CLI",
        "dispatchable": gem_ok,
    })

    # Antigravity
    ag_path = _which("antigravity")
    agents.append({
        "id": "antigravity", "label": "Antigravity", "label_ar": "أنتي جرافيتي",
        "kind": "coding", "online": ag_path is not None,
        "detail": "ready" if ag_path else "CLI not installed",
        "dispatchable": ag_path is not None,
    })

    return {"agents": agents}


def _build_command(agent: str, task: str, workspace: str | None) -> list[str] | None:
    if agent == "claude":
        return [_which("claude") or "claude", "-p", task]
    if agent == "antigravity":
        cmd = [_which("antigravity") or "antigravity", "run", task]
        if workspace:
            cmd += ["--workspace", workspace]
        return cmd
    return None


def _run_gemini(task: str) -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    # Follow the configured model rather than pinning one here: the previously
    # hardcoded gemini-2.0-flash has been retired by Google and now 404s.
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.ai_model}:generateContent?key={key}"
    )
    body = json.dumps({"contents": [{"parts": [{"text": task}]}]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=DISPATCH_TIMEOUT) as r:
        data = json.loads(r.read())
    text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    ) or "(no text)"
    return text


def dispatch(
    agent: str,
    task: str,
    session: Session,
    workspace: str | None = None,
    task_id: int | None = None,
    confirm: bool = False,
    dry_run: bool | None = None,
) -> dict:
    """Dispatch a task to an AI agent with full guardrails.

    Returns a result dict with status, output, and latency. Always audits
    the run to the agent_runs SQL table.
    """
    if dry_run is None:
        dry_run = DRY_RUN_DEFAULT

    run_id = uuid.uuid4().hex[:12]
    t0 = time.time()
    base = {
        "run_id": run_id, "agent": agent, "task": task[:500],
        "task_id": task_id, "output": "", "command": "",
    }

    if not task.strip():
        return {**base, "status": "error", "output": "empty task", "latency_ms": 0}

    st = {a["id"]: a for a in agent_status()["agents"]}
    if agent not in st:
        return {**base, "status": "blocked", "output": f"unknown agent '{agent}'", "latency_ms": 0}
    if not st[agent]["dispatchable"]:
        hints = {
            "hermes": "Hermes is status-only; manage it via its own dashboard on :5000.",
            "gemini": "Set GEMINI_API_KEY in .env (non-sensitive tasks only).",
            "antigravity": "Install Antigravity and sign in with Google.",
        }
        return {**base, "status": "blocked", "output": f"{agent} not dispatchable. {hints.get(agent, '')}", "latency_ms": 0}

    cmd = _build_command(agent, task, workspace)
    base["command"] = " ".join(cmd) if cmd else f"{agent} · {task[:40]}…"

    # The dry-run / external-confirm guard is waived ONLY for a transport that
    # keeps the task text on this machine. That used to be true of "hermes" by
    # definition, when it was always local Ollama. It no longer is: the Hermes
    # Agent CLI answers through a hosted provider, so the task — which may quote
    # patient or financial data — leaves the device. Waiving the guard on the
    # CLI path would silently strip the protection, so the exemption now follows
    # the transport, not the agent name.
    local_safe = agent == "hermes" and hermes_mode() == "ollama"

    if dry_run and not local_safe:
        result = {**base, "status": "blocked", "output": "dry run — not executed", "latency_ms": 0}
        _audit(session, result)
        return result

    if not confirm and not local_safe:
        result = {**base, "status": "blocked", "output": "confirmation required — resend with confirm=true", "latency_ms": 0}
        _audit(session, result)
        return result

    try:
        if agent == "hermes":
            out = _run_hermes(task)
        elif agent == "gemini":
            out = _run_gemini(task)
        else:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=DISPATCH_TIMEOUT, shell=False)
            if r.returncode != 0:
                raise RuntimeError((r.stderr or r.stdout or "")[-300:])
            out = (r.stdout or "").strip()

        result = {**base, "status": "done", "output": out[:20000], "latency_ms": int((time.time() - t0) * 1000)}
    except subprocess.TimeoutExpired:
        result = {**base, "status": "error", "output": f"timed out after {DISPATCH_TIMEOUT}s", "latency_ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        result = {**base, "status": "error", "output": str(e)[:500], "latency_ms": int((time.time() - t0) * 1000)}

    _audit(session, result)
    return result


def _audit(session: Session, result: dict) -> None:
    """Write agent run to the SQL database for audit trail."""
    try:
        run = m.AgentRun(
            run_id=result["run_id"],
            agent=result["agent"],
            task=result["task"][:500],
            status=result["status"],
            output=result.get("output", "")[:2000],
            latency_ms=result.get("latency_ms", 0),
            task_id=result.get("task_id"),
        )
        session.add(run)
        session.commit()
    except Exception:
        session.rollback()


def recent_runs(session: Session, limit: int = 50) -> list[dict]:
    """Return recent agent runs from the database."""
    rows = (
        session.query(m.AgentRun)
        .order_by(m.AgentRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "run_id": r.run_id,
            "agent": r.agent,
            "task": r.task,
            "status": r.status,
            "output": r.output[:200] if r.output else "",
            "latency_ms": r.latency_ms,
            "task_id": r.task_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
