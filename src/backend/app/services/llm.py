"""One provider registry for every LLM call in ProCare.

Before this module each call site (assistant intent routing, deep-analysis
narrative, prescription OCR) hard-coded its own ``httpx.post`` to a single
provider. This centralises them so the same four providers work everywhere:

  * ``anthropic``  — Claude API (hosted, needs ANTHROPIC_API_KEY)
  * ``gemini``     — Google Gemini API (hosted, needs GEMINI_API_KEY).
                     Defaults to Gemini Pro on the free tier.
  * ``hermes``     — Nous Hermes served through OpenRouter's FREE tier
                     (hosted, needs OPENROUTER_API_KEY). Same gateway the
                     branch PCs' Hermes Agent already uses.
  * ``ollama``     — local, OpenAI-compatible server at settings.ai_base_url
                     (http://localhost:11434). NO API key — fully offline.
  * ``claude-cli`` — shell out to a locally installed & logged-in Claude Code
                     CLI. NO API key.
  * ``hermes-cli`` — shell out to a locally installed Hermes CLI. NO API key
                     held by ProCare (the binary carries its own auth).

``hermes`` and ``ollama`` share one OpenAI-compatible transport
(``_openai_*``); they differ only in base URL, key and model list.
``claude-cli`` and ``hermes-cli`` share one subprocess transport
(``_run_cli``); they differ only in which executable and args are invoked.

Two public entry points, both provider-agnostic and both fail-soft (return
``None`` on any error) so the assistant always falls back to its deterministic
keyword router and a sale/report is never blocked by an AI outage:

  * ``classify(query, choices, branch_id)`` -> (choice, branch_id) | None
        Constrained pick of ONE label from ``choices`` (the intent whitelist).
  * ``complete(prompt, system=None)`` -> str | None
        Free-text completion, used only to *phrase* already-computed facts.
"""
from __future__ import annotations

import json
import subprocess

from app.config import settings

_TIMEOUT = 20


def _openai_headers():
    """Auth headers for OpenAI-compatible endpoints (OpenRouter, etc.).

    Ollama needs none; OpenRouter requires ``Authorization: Bearer <key>``.
    We attach the key whenever one is present in the environment, plus the
    OpenRouter-recommended attribution headers (harmless for other backends)."""
    key = settings.ai_api_key()
    if not key:
        return {}
    return {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "https://procarepharmacies.local",
        "X-Title": "ProCare OS",
    }


def _openai_models():
    """Ordered model list for the OpenAI-compatible (hermes/OpenRouter, ollama)
    path: the primary ``AI_MODEL`` first, then any comma-separated
    ``AI_MODEL_FALLBACKS``, then the provider's own built-in fallbacks.

    On a rate-limit (429) or error, callers try the next model in turn — so a
    congested free model never takes the pharmacy assistant offline. For
    ``hermes`` the built-ins matter more than usual: OpenRouter's ``:free``
    slugs are retired and renamed without notice, and a dead primary would
    otherwise drop the assistant to the keyword router with no visible cause.
    """
    import os

    from app.config import HERMES_FALLBACK_MODELS

    models = [settings.ai_model]
    for m in (os.environ.get("AI_MODEL_FALLBACKS") or "").split(","):
        m = m.strip()
        if m and m not in models:
            models.append(m)
    if settings.ai_provider == "hermes":
        for m in HERMES_FALLBACK_MODELS:
            if m not in models:
                models.append(m)
    return models


def provider() -> str:
    return settings.ai_provider


def is_configured() -> bool:
    """True when the active provider can run (keyless local, or key present)."""
    return settings.ai_is_configured()


# --- constrained intent classification --------------------------------------
def classify(query: str, choices: dict[str, str], branch_id: int | None) -> tuple[str, int | None] | None:
    """Pick exactly one key of ``choices`` for the question. Returns
    (choice, branch_id) or None to let the caller fall back."""
    if not is_configured():
        return None
    p = provider()
    try:
        if p == "gemini":
            return _classify_gemini(query, choices, branch_id)
        if p in ("hermes", "ollama"):
            return _classify_openai(query, choices, branch_id)
        if p in _cli_providers():
            return _classify_cli(query, choices, branch_id)
        return _classify_anthropic(query, choices, branch_id)
    except Exception:  # noqa: BLE001
        return None


def _system_prompt(choices: dict[str, str]) -> str:
    return (
        "You route an Arabic/English pharmacy-manager question to exactly one "
        "read-only intent. Intents: " + json.dumps(choices, ensure_ascii=False) + "."
    )


def _coerce(choice: str, choices: dict[str, str]) -> str:
    return choice if choice in choices else "help" if "help" in choices else next(iter(choices))


def _classify_anthropic(query, choices, branch_id):
    import httpx

    tools = [{
        "name": "answer_with_intent",
        "description": "Pick the single best intent to answer the pharmacy question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "enum": list(choices)},
                "branch_id": {"type": "integer", "description": "1=Elsanta, 2=Mas-hala, 0=all branches"},
            },
            "required": ["intent"],
        },
    }]
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": settings.ai_api_key(), "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={
            "model": settings.ai_model, "max_tokens": 256,
            "system": _system_prompt(choices) + " Always call the answer_with_intent tool.",
            "tools": tools, "tool_choice": {"type": "tool", "name": "answer_with_intent"},
            "messages": [{"role": "user", "content": query}],
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    for block in resp.json().get("content", []):
        if block.get("type") == "tool_use":
            inp = block["input"]
            b = inp.get("branch_id", branch_id)
            return _coerce(inp.get("intent", "help"), choices), (b if b else branch_id)
    return None


def _classify_gemini(query, choices, branch_id):
    import httpx

    tools = [{"function_declarations": [{
        "name": "answer_with_intent",
        "description": "Pick the single best intent to answer the pharmacy question.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "enum": list(choices)},
                "branch_id": {"type": "integer", "description": "1=Elsanta, 2=Mas-hala, 0=all branches"},
            },
            "required": ["intent"],
        },
    }]}]
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.ai_model}:generateContent",
        params={"key": settings.ai_api_key()},
        json={
            "system_instruction": {"parts": [{"text": _system_prompt(choices) + " Always call the answer_with_intent function."}]},
            "contents": [{"role": "user", "parts": [{"text": query}]}],
            "tools": tools, "tool_config": {"function_calling_config": {"mode": "ANY"}},
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    for cand in resp.json().get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            call = part.get("functionCall")
            if call and call.get("name") == "answer_with_intent":
                args = call.get("args", {})
                b = args.get("branch_id", branch_id)
                return _coerce(args.get("intent", "help"), choices), (b if b else branch_id)
    return None


def _classify_openai(query, choices, branch_id):
    """Ollama's OpenAI-compatible /v1/chat/completions with tool-calling."""
    import httpx

    tools = [{
        "type": "function",
        "function": {
            "name": "answer_with_intent",
            "description": "Pick the single best intent to answer the pharmacy question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "enum": list(choices)},
                    "branch_id": {"type": "integer", "description": "1=Elsanta, 2=Mas-hala, 0=all branches"},
                },
                "required": ["intent"],
            },
        },
    }]
    last_exc = None
    for model in _openai_models():
        try:
            resp = httpx.post(
                f"{settings.ai_base_url.rstrip('/')}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _system_prompt(choices)},
                        {"role": "user", "content": query},
                    ],
                    "tools": tools, "tool_choice": "auto", "stream": False,
                },
                headers=_openai_headers(),
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as e:  # noqa: BLE001 — try next fallback model (429/5xx/etc.)
            last_exc = e
            continue
        choice0 = (resp.json().get("choices") or [{}])[0].get("message", {})
        for call in choice0.get("tool_calls", []) or []:
            if call.get("function", {}).get("name") == "answer_with_intent":
                args = json.loads(call["function"].get("arguments") or "{}")
                b = args.get("branch_id", branch_id)
                return _coerce(args.get("intent", "help"), choices), (b if b else branch_id)
        # Some local models answer in content instead of a tool call — accept a bare
        # intent label if it's one of the choices.
        content = (choice0.get("content") or "").strip().strip('"').lower()
        for key in choices:
            if key in content:
                return key, branch_id
        return None
    if last_exc:
        raise last_exc
    return None


def _classify_cli(query, choices, branch_id):
    """Shell out to the active provider's CLI, asking for a single JSON label."""
    prompt = (
        _system_prompt(choices)
        + " Reply with ONLY a JSON object {\"intent\": <one intent key>, \"branch_id\": <0|1|2>}. "
        + "Question: " + query
    )
    out = _run_cli(prompt)
    if not out:
        return None
    try:
        data = json.loads(_first_json(out))
        b = data.get("branch_id", branch_id)
        return _coerce(data.get("intent", "help"), choices), (b if b else branch_id)
    except Exception:  # noqa: BLE001
        return None


# --- free-text completion (phrasing already-computed facts) ------------------
def complete(prompt: str, system: str | None = None, max_tokens: int = 400) -> str | None:
    """Free-text completion, or None on any failure/unconfigured."""
    if not is_configured():
        return None
    p = provider()
    try:
        if p == "gemini":
            return _complete_gemini(prompt, system, max_tokens)
        if p in ("hermes", "ollama"):
            return _complete_openai(prompt, system, max_tokens)
        if p in _cli_providers():
            return _run_cli(f"{system}\n\n{prompt}" if system else prompt)
        return _complete_anthropic(prompt, system, max_tokens)
    except Exception:  # noqa: BLE001
        return None


def _complete_anthropic(prompt, system, max_tokens):
    import httpx

    body = {"model": settings.ai_model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
    if system:
        body["system"] = system
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": settings.ai_api_key(), "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json=body, timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    parts = [b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text"]
    return ("".join(parts)).strip() or None


def _complete_gemini(prompt, system, max_tokens):
    import httpx

    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.ai_model}:generateContent",
        params={"key": settings.ai_api_key()}, json=body, timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    for cand in resp.json().get("candidates", []):
        texts = [p.get("text", "") for p in cand.get("content", {}).get("parts", [])]
        if any(texts):
            return "".join(texts).strip()
    return None


def _complete_openai(prompt, system, max_tokens):
    import httpx

    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    last_exc = None
    for model in _openai_models():
        try:
            resp = httpx.post(
                f"{settings.ai_base_url.rstrip('/')}/v1/chat/completions",
                json={"model": model, "messages": messages, "max_tokens": max_tokens, "stream": False},
                headers=_openai_headers(),
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            out = ((resp.json().get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()
            if out:
                return out
        except Exception as e:  # noqa: BLE001 — try next fallback model (429/5xx/etc.)
            last_exc = e
            continue
    if last_exc:
        raise last_exc
    return None


# --- local-CLI helpers ------------------------------------------------------
def _cli_providers() -> dict:
    """Providers answered by shelling out to a local binary (claude-cli,
    hermes-cli). Read live from config so a reload picks up new entries."""
    from app.config import _CLI_PROVIDERS

    return _CLI_PROVIDERS


def _cli_argv(prompt: str) -> list[str] | None:
    """argv for the active provider's CLI, or None if it is not a CLI provider.

    The executable and the args placed before the prompt both default from the
    provider table and can be overridden per install with e.g.
    ``HERMES_CLI_BIN`` / ``HERMES_CLI_ARGS`` (``CLAUDE_CLI_BIN`` / ``_ARGS``),
    because a locally installed binary's name and flags are a property of that
    machine, not of ProCare. The prompt is always the final argv element and is
    never interpolated into a shell string — no shell=True on this path, so a
    prescription or question containing shell metacharacters cannot execute.
    """
    import os
    import shlex

    spec = _cli_providers().get(settings.ai_provider)
    if not spec:
        return None
    env_prefix = settings.ai_provider.replace("-", "_").upper()  # HERMES_CLI
    binary = (os.environ.get(f"{env_prefix}_BIN") or spec["bin"]).strip()
    if not binary:
        return None
    raw_args = os.environ.get(f"{env_prefix}_ARGS")
    args = shlex.split(raw_args if raw_args is not None else spec["args"])
    return [binary, *args, prompt]


def _run_cli(prompt: str) -> str | None:
    """Run the active provider's CLI and return its text, or None if the binary
    is missing, times out, or exits non-zero — fail-soft like every other
    provider path, so a missing CLI drops to the keyword router, not an error."""
    argv = _cli_argv(prompt)
    if not argv:
        return None
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip() or None


def _first_json(text: str) -> str:
    """Extract the first {...} object from a text blob (CLI may wrap it)."""
    start = text.find("{")
    end = text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text


def status() -> dict:
    """Small report for /api/health and the settings screen."""
    return {
        "provider": settings.ai_provider,
        "model": settings.ai_model,
        "configured": is_configured(),
        "keyless": settings.ai_provider in _keyless(),
        "base_url": settings.ai_base_url if settings.ai_provider in ("hermes", "ollama") else None,
        # The whole chain, so a settings screen shows what will actually be
        # tried when a free slug is retired — not just the dead primary.
        "models": _openai_models() if settings.ai_provider in ("hermes", "ollama") else [settings.ai_model],
        # For a local-CLI provider, the executable that will actually be run —
        # otherwise "configured: true, keyless: true" looks healthy on a PC
        # where the binary was never installed. The prompt is omitted.
        "cli_bin": (_cli_argv("") or [None])[0],
    }


def _keyless() -> set[str]:
    from app.config import _KEYLESS_PROVIDERS

    return _KEYLESS_PROVIDERS
