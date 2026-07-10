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


def test_hermes_alias_maps_to_ollama(reload_config):
    cfg = reload_config(AI_PROVIDER="hermes", AI_MODEL=None)
    assert cfg.settings.ai_provider == "ollama"
    assert cfg.settings.ai_model == "hermes3"


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
