"""Tests for the multi-provider LLM registry (services.llm).

Focus on the behaviour that matters operationally: keyless local providers are
"configured" without an API key, provider dispatch routes to the right backend,
and every path fails soft (returns None) so the assistant keeps working.
"""
from __future__ import annotations

import importlib

import pytest

from app.services import llm


@pytest.fixture
def reload_config(monkeypatch):
    """Re-import config + llm after setting env, so provider is recomputed."""
    def _apply(**env):
        for k, v in env.items():
            if v is None:
                monkeypatch.delenv(k, raising=False)
            else:
                monkeypatch.setenv(k, v)
        import app.config as cfg
        importlib.reload(cfg)
        importlib.reload(llm)
        return cfg
    yield _apply
    # Restore modules to a clean default for the rest of the suite.
    import app.config as cfg
    importlib.reload(cfg)
    importlib.reload(llm)


def test_ollama_is_configured_without_key(reload_config):
    cfg = reload_config(AI_PROVIDER="ollama", ANTHROPIC_API_KEY=None, GEMINI_API_KEY=None)
    assert cfg.settings.ai_provider == "ollama"
    assert cfg.settings.ai_is_configured() is True  # keyless
    assert llm.is_configured() is True


def test_hermes_is_hosted_openrouter_not_local_ollama(reload_config):
    """"hermes" used to be an alias for a model on a LOCAL Ollama server. It is
    now the hosted Nous Hermes free tier on OpenRouter, so it must resolve to
    its own provider, its own key and OpenRouter's base URL — never localhost."""
    cfg = reload_config(AI_PROVIDER="hermes", AI_MODEL=None, AI_BASE_URL=None, OLLAMA_BASE_URL=None)
    assert cfg.settings.ai_provider == "hermes"
    assert cfg.settings.ai_model.endswith(":free")
    assert "hermes" in cfg.settings.ai_model.lower()
    assert cfg.settings.ai_api_key_env == "OPENROUTER_API_KEY"
    assert "localhost" not in cfg.settings.ai_base_url
    # The base URL must NOT already end in /v1: llm.py appends
    # "/v1/chat/completions", so a /v1 here would request /v1/v1/... and 404.
    assert cfg.settings.ai_base_url == "https://openrouter.ai/api"


def test_openrouter_and_nous_also_select_hermes(reload_config):
    for name in ("openrouter", "nous"):
        cfg = reload_config(AI_PROVIDER=name)
        assert cfg.settings.ai_provider == "hermes"


def test_hermes_needs_the_openrouter_key(reload_config):
    """Free models are still gated behind a key — hermes must NOT be treated as
    keyless, or the assistant would try (and fail) instead of falling back."""
    cfg = reload_config(AI_PROVIDER="hermes", OPENROUTER_API_KEY=None)
    assert cfg.settings.ai_is_configured() is False
    cfg = reload_config(AI_PROVIDER="hermes", OPENROUTER_API_KEY="sk-or-v1-test")
    assert cfg.settings.ai_is_configured() is True


def test_hermes_falls_back_to_other_free_models(reload_config):
    """A retired/rate-limited :free slug must roll to another free model rather
    than take the assistant offline."""
    reload_config(AI_PROVIDER="hermes", OPENROUTER_API_KEY="sk-or-v1-test", AI_MODEL_FALLBACKS=None)
    models = llm._openai_models()
    assert len(models) >= 3
    assert models[0].endswith(":free")
    assert all(m.endswith(":free") for m in models), models
    assert len(set(models)) == len(models)  # no duplicate attempts


def test_ollama_keeps_the_local_base_url(reload_config):
    """Splitting hermes out must not drag the local provider to OpenRouter."""
    cfg = reload_config(AI_PROVIDER="ollama", AI_BASE_URL=None, OLLAMA_BASE_URL=None)
    assert cfg.settings.ai_base_url == "http://localhost:11434"


def test_gemini_defaults_to_pro_on_the_free_tier(reload_config):
    cfg = reload_config(AI_PROVIDER="gemini", AI_MODEL=None)
    assert cfg.settings.ai_model == "gemini-2.5-pro"
    # Floating alias, never a dated build — a retired dated model strands the
    # install and drops the assistant to the keyword router silently.
    assert not cfg.settings.ai_model[-1].isdigit() or "-2.5-pro" in cfg.settings.ai_model


def test_claude_alias_maps_to_anthropic(reload_config):
    cfg = reload_config(AI_PROVIDER="claude")
    assert cfg.settings.ai_provider == "anthropic"


def test_hosted_provider_needs_key(reload_config):
    cfg = reload_config(AI_PROVIDER="anthropic", ANTHROPIC_API_KEY=None)
    assert cfg.settings.ai_is_configured() is False
    # Unconfigured → classify short-circuits to None (caller falls back).
    assert llm.classify("مبيعات اليوم", {"sales_today": "x", "help": "y"}, None) is None


def test_ollama_classify_routes_and_parses(reload_config, monkeypatch):
    reload_config(AI_PROVIDER="ollama")
    calls = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"tool_calls": [
                {"function": {"name": "answer_with_intent",
                              "arguments": '{"intent": "sales_today", "branch_id": 2}'}}
            ]}}]}

    def fake_post(url, **kw):
        calls["url"] = url
        return FakeResp()

    import httpx
    monkeypatch.setattr(httpx, "post", fake_post)
    out = llm.classify("كام بعنا النهارده", {"sales_today": "x", "help": "y"}, None)
    assert out == ("sales_today", 2)
    assert "/v1/chat/completions" in calls["url"]  # OpenAI-compatible endpoint


def test_hermes_classify_hits_openrouter_with_auth(reload_config, monkeypatch):
    """The whole point of the switch: hermes must reach OpenRouter over the
    shared OpenAI-compatible transport, authenticated, not a local server."""
    reload_config(AI_PROVIDER="hermes", OPENROUTER_API_KEY="sk-or-v1-test", AI_BASE_URL=None)
    calls = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"tool_calls": [
                {"function": {"name": "answer_with_intent",
                              "arguments": '{"intent": "sales_today", "branch_id": 1}'}}
            ]}}]}

    def fake_post(url, **kw):
        calls["url"] = url
        calls["headers"] = kw.get("headers") or {}
        calls["model"] = (kw.get("json") or {}).get("model")
        return FakeResp()

    import httpx
    monkeypatch.setattr(httpx, "post", fake_post)
    assert llm.classify("كام بعنا النهارده", {"sales_today": "x", "help": "y"}, None) == ("sales_today", 1)
    # Exact URL, not a prefix: a doubled /v1 (from a base_url that already ends
    # in /v1) still "starts with" the right thing but 404s in production.
    assert calls["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert calls["headers"].get("Authorization") == "Bearer sk-or-v1-test"
    assert calls["model"].endswith(":free")


def test_hermes_rolls_to_the_next_free_model_on_failure(reload_config, monkeypatch):
    """A dead or rate-limited primary slug must not end the attempt."""
    reload_config(AI_PROVIDER="hermes", OPENROUTER_API_KEY="sk-or-v1-test", AI_MODEL_FALLBACKS=None)
    tried = []

    class OkResp:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "تم."}}]}

    def fake_post(url, **kw):
        model = (kw.get("json") or {}).get("model")
        tried.append(model)
        if len(tried) == 1:
            raise RuntimeError("429 rate limit")  # primary is congested
        return OkResp()

    import httpx
    monkeypatch.setattr(httpx, "post", fake_post)
    assert llm.complete("لخص") == "تم."
    assert len(tried) == 2 and tried[0] != tried[1]


def test_ollama_complete_returns_text(reload_config, monkeypatch):
    reload_config(AI_PROVIDER="ollama")

    class FakeResp:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "ملخص الأداء جيد."}}]}

    import httpx
    monkeypatch.setattr(httpx, "post", lambda url, **kw: FakeResp())
    assert llm.complete("phrase these facts") == "ملخص الأداء جيد."


def test_cli_missing_binary_returns_none(reload_config, monkeypatch):
    reload_config(AI_PROVIDER="claude-cli")
    import subprocess

    def boom(*a, **k):
        raise FileNotFoundError("claude not installed")

    monkeypatch.setattr(subprocess, "run", boom)
    assert llm.classify("q", {"help": "y"}, None) is None
    assert llm.complete("q") is None


def test_network_error_fails_soft(reload_config, monkeypatch):
    reload_config(AI_PROVIDER="ollama")
    import httpx

    def boom(*a, **k):
        raise httpx.ConnectError("no ollama server")

    monkeypatch.setattr(httpx, "post", boom)
    assert llm.classify("q", {"help": "y"}, None) is None
    assert llm.complete("q") is None
