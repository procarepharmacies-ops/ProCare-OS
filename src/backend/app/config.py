"""Configuration loader.

Reads ``config/connections.json`` (git-ignored) and falls back to
``config/connections.example.json`` so the skeleton runs out of the box.

Security: this module NEVER exposes secrets. The API only ever reports *whether*
a data source is configured with a real (non-placeholder) credential — never the
credential itself.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# config.py -> app -> backend -> src -> <repo root>
ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "config"

# Tokens used in the committed example file; treated as "not configured".
_PLACEHOLDER_MARKERS = ("REPLACE_ME", "REPLACE_WITH", "TBD")


def _load() -> tuple[dict, str]:
    # PROCARE_CONFIG_FILE (env) pins the config — the test suite points it at
    # the example file so tests never see (or touch) the operator's real
    # servers, whatever is in connections.json on this machine.
    override = os.environ.get("PROCARE_CONFIG_FILE")
    if override:
        p = Path(override)
        with p.open(encoding="utf-8") as fh:
            return json.load(fh), p.name
    real = CONFIG_DIR / "connections.json"
    example = CONFIG_DIR / "connections.example.json"
    path = real if real.exists() else example
    with path.open(encoding="utf-8") as fh:
        return json.load(fh), path.name


def _is_real(value) -> bool:
    """True only if ``value`` is a non-empty string with no placeholder marker."""
    if not isinstance(value, str):
        return False
    v = value.strip()
    if not v:
        return False
    return not any(marker in v for marker in _PLACEHOLDER_MARKERS)


def _source_configured(block) -> bool:
    if not isinstance(block, dict):
        return False
    return _is_real(block.get("username")) and _is_real(block.get("password"))


def _odbc_url(block: dict) -> str | None:
    """Build a pyodbc SQLAlchemy URL from a connection block, or None.

    Returns None unless the block carries real (non-placeholder) credentials, so
    callers transparently fall back to the local SQLite dev database.
    """
    if not _source_configured(block):
        return None
    from urllib.parse import quote_plus

    driver = block.get("driver", "ODBC Driver 18 for SQL Server")
    server = block.get("server", "")
    # Port forwarding: "SERVER=host,1433". Accept an explicit port (default 1433
    # only when the server has no port baked in already).
    port = block.get("port")
    if port and "," not in str(server):
        server = f"{server},{port}"
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={block.get('database', '')}",
        f"UID={block.get('username', '')}",
        f"PWD={block.get('password', '')}",
        f"Encrypt={block.get('encrypt', 'yes')}",
        f"TrustServerCertificate={block.get('trust_server_certificate', 'yes')}",
    ]
    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(";".join(parts))


_data, _source = _load()
_ui = _data.get("ui", {})
_branches = _data.get("branches", {})
_ai = _data.get("ai", {})
_notify = _data.get("notifications", {})

# Per-provider defaults: which model to use and which env var holds the key.
# ``keyless`` providers run locally (Ollama) or via a logged-in CLI (Claude
# Code) and need NO API key — the assistant works fully offline on the LAN.
_AI_PROVIDER_DEFAULTS = {
    "anthropic": {"model": "claude-sonnet-4-6", "key_env": "ANTHROPIC_API_KEY"},
    "gemini": {"model": "gemini-2.0-flash", "key_env": "GEMINI_API_KEY"},
    # Ollama serves an OpenAI-compatible API at http://localhost:11434. "Hermes"
    # is just a model served by Ollama (default hermes3), so hermes -> ollama.
    "ollama": {"model": "hermes3", "key_env": "OLLAMA_API_KEY", "keyless": True},
    # Shell out to a locally installed & logged-in Claude Code CLI.
    "claude-cli": {"model": "claude-sonnet-4-6", "key_env": "ANTHROPIC_API_KEY", "keyless": True},
}

# Providers that need no API key to be considered "configured".
_KEYLESS_PROVIDERS = {p for p, d in _AI_PROVIDER_DEFAULTS.items() if d.get("keyless")}


def _norm_provider(p: str) -> str:
    p = (p or "").strip().lower()
    if p in ("gemini", "google"):
        return "gemini"
    if p in ("ollama", "hermes", "local"):
        return "ollama"
    if p in ("claude-cli", "claude_cli", "cli"):
        return "claude-cli"
    if p in ("claude",):
        return "anthropic"
    return p


def _detect_ai_provider() -> str:
    """Pick the AI provider: explicit AI_PROVIDER env or config wins; otherwise
    infer from whichever API key is present in the environment."""
    import os

    explicit = os.environ.get("AI_PROVIDER") or _ai.get("provider")
    if explicit:
        return _norm_provider(explicit)
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "anthropic"


def _config_is_for(provider: str) -> bool:
    """True if the config file's ``ai`` block targets the active provider, so its
    model / api_key_env apply. When the provider was switched via env (e.g. to
    Gemini), the example file's Anthropic values must NOT leak through."""
    return _norm_provider(_ai.get("provider", "")) == provider


def _ai_model_for(provider: str) -> str:
    import os

    default = _AI_PROVIDER_DEFAULTS.get(provider, _AI_PROVIDER_DEFAULTS["anthropic"])["model"]
    if os.environ.get("AI_MODEL"):
        return os.environ["AI_MODEL"]
    if _config_is_for(provider) and _ai.get("model"):
        return _ai["model"]
    return default


def _ai_key_env_for(provider: str) -> str:
    default = _AI_PROVIDER_DEFAULTS.get(provider, _AI_PROVIDER_DEFAULTS["anthropic"])["key_env"]
    if _config_is_for(provider) and _ai.get("api_key_env"):
        return _ai["api_key_env"]
    return default


class Settings:
    """Read-only view of config, safe to serialise (no secrets)."""

    source_file: str = _source
    using_example: bool = _source == "connections.example.json"

    default_language: str = _ui.get("default_language", "ar")
    languages = _ui.get("languages", ["ar", "en"])
    default_theme: str = _ui.get("default_theme", "light")
    themes = _ui.get("themes", ["light", "dark"])

    network_host: str = _data.get("network_host", "192.168.1.2")

    # Which data sources have real (non-placeholder) credentials.
    estock_configured: bool = _source_configured(_data.get("estock_source", {})) or any(
        _source_configured(b) for b in (_data.get("estock_sources") or [])
    )
    titan_configured: bool = _source_configured(_data.get("titan_drugeye_source", {}))
    procare_configured: bool = _source_configured(_data.get("procare_database", {}))

    # AI assistant. Supports Anthropic (Claude API), Google (Gemini), Ollama /
    # Hermes (local, no key), and the Claude Code CLI (local, no key). The key is
    # read from the environment, never from git — config only names which env var
    # holds it. Provider/model/key-env can be set in the config "ai" block OR via
    # environment (AI_PROVIDER / AI_MODEL), which is how the Docker stack sets it.
    # If nothing is set, we auto-detect from whichever API key is present.
    ai_provider: str = _detect_ai_provider()
    ai_model: str = _ai_model_for(ai_provider)
    ai_api_key_env: str = _ai_key_env_for(ai_provider)
    # Base URL for local/OpenAI-compatible providers (Ollama). Override with
    # AI_BASE_URL (or OLLAMA_BASE_URL) to point at another host on the LAN.
    ai_base_url: str = (
        os.environ.get("AI_BASE_URL")
        or os.environ.get("OLLAMA_BASE_URL")
        or _ai.get("base_url")
        or "http://localhost:11434"
    )

    # Login gate (CEO/manager/assistant roles). AUTH_ENABLED env wins when set
    # (either way). When unset: ON automatically for a production deployment
    # (real eStock source or SQL Server configured — a live pharmacy must not
    # run open), OFF for dev/demo/tests so the seeded stack stays frictionless.
    auth_enabled: bool = (
        os.environ.get("AUTH_ENABLED", "").lower() in ("1", "true", "yes", "on")
        if os.environ.get("AUTH_ENABLED") is not None
        else (estock_configured or procare_configured)
    )

    # Loyalty programme rates (overridable per pharmacy via env):
    #   earn : every LOYALTY_EGP_PER_POINT EGP of net spend = 1 point;
    #   spend: each point is worth LOYALTY_POINT_VALUE EGP at redemption.
    # Defaults: 10 EGP -> 1 point, 1 point -> 0.25 EGP (2.5% back).
    loyalty_egp_per_point: float = float(os.environ.get("LOYALTY_EGP_PER_POINT", "10") or 10)
    loyalty_point_value: float = float(os.environ.get("LOYALTY_POINT_VALUE", "0.25") or 0.25)

    # Manager phone for WhatsApp operational alerts (transfer requests, daily
    # report, expiry/reorder summaries). Env wins, else the notifications config
    # block. Empty/placeholder = those manager alerts are simply skipped.
    manager_phone: str = (
        (os.environ.get("MANAGER_PHONE") or _notify.get("manager_phone") or "").strip()
        if _is_real(os.environ.get("MANAGER_PHONE") or _notify.get("manager_phone") or "")
        else ""
    )

    @staticmethod
    def procare_sqlalchemy_url() -> str | None:
        """SQL Server URL for ProCare's own DB, or None to use SQLite dev DB."""
        return _odbc_url(_data.get("procare_database", {}))

    @staticmethod
    def estock_sqlalchemy_url() -> str | None:
        """Read-only SQL Server URL for the eStock mirror source, or None.

        Falls back to the first entry of ``estock_sources`` (multi-branch setups)
        so single-source tools (preflight, --run, backup imports) keep working.
        """
        url = _odbc_url(_data.get("estock_source", {}))
        if url:
            return url
        for block in _data.get("estock_sources") or []:
            url = _odbc_url(block)
            if url:
                return url
        return None

    @staticmethod
    def estock_sources() -> list[dict]:
        """Every configured eStock mirror source (one per branch server).

        Reads the ``estock_sources`` list — each entry a full connection block
        plus its own ``store_branch_map`` — and falls back to the legacy single
        ``estock_source`` block so existing configs keep working. Entries without
        real credentials are skipped. Each item carries only what the sync needs:
        ``{"name", "url", "store_branch_map"}``.
        """
        blocks = list(_data.get("estock_sources") or [])
        if not blocks and _data.get("estock_source"):
            blocks = [_data["estock_source"]]
        out: list[dict] = []
        for i, block in enumerate(blocks):
            url = _odbc_url(block)
            if url:
                out.append(
                    {
                        "name": str(block.get("name") or block.get("database") or f"estock{i + 1}"),
                        "url": url,
                        "store_branch_map": block.get("store_branch_map"),
                    }
                )
        return out

    @staticmethod
    def titan_sqlalchemy_url() -> str | None:
        """Read-only URL for the Titan / Drug-Eye clinical source, or None.

        The Titan schema/engine under ``D:\\Labirdo`` is still TBD (docs/03), so
        this only builds a SQL Server URL when a real login is configured; the
        clinical service falls back to its curated advisory rules otherwise.
        """
        return _odbc_url(_data.get("titan_drugeye_source", {}))

    @staticmethod
    def estock_url_for_database(database: str) -> str | None:
        """Build a read-only URL for another database on the SAME server/login as
        ``estock_source`` — used to import each restored branch backup
        (stock_elsanta, stock_mashala, …) without repeating credentials."""
        block = dict(_data.get("estock_source", {}))
        if database:
            block["database"] = database
        return _odbc_url(block)

    @staticmethod
    def estock_store_branch_map() -> dict | None:
        """Optional eStock store_id -> ProCare branch CODE/id map for the mirror.

        Configured under ``estock_source.store_branch_map`` (e.g.
        ``{"1": "ELSANTA", "2": "MASHALA"}``). None lets the ETL use its default.
        """
        return _data.get("estock_source", {}).get("store_branch_map")

    @staticmethod
    def ai_api_key():
        """The AI provider's API key from the configured env var, or None if unset."""
        import os

        return os.environ.get(Settings.ai_api_key_env)

    @staticmethod
    def ai_is_configured() -> bool:
        """True when the active provider can actually run: a keyless local
        provider (Ollama / Claude CLI) is always considered configured; hosted
        providers (Anthropic / Gemini) need their API key present."""
        if Settings.ai_provider in _KEYLESS_PROVIDERS:
            return True
        return bool(Settings.ai_api_key())

    @staticmethod
    def branch_list() -> list:
        out = []
        for code, b in _branches.items():
            out.append(
                {
                    "code": code,
                    "name_ar": b.get("name_ar", code),
                    "name_en": b.get("name_en", code),
                    "pilot": bool(b.get("pilot", False)),
                }
            )
        return out


settings = Settings()
