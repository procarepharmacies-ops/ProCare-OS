"""Configuration loader.

Reads ``config/connections.json`` (git-ignored) and falls back to
``config/connections.example.json`` so the skeleton runs out of the box.

Security: this module NEVER exposes secrets. The API only ever reports *whether*
a data source is configured with a real (non-placeholder) credential — never the
credential itself.
"""
from __future__ import annotations

import json
from pathlib import Path

# config.py -> app -> backend -> src -> <repo root>
ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "config"

# Tokens used in the committed example file; treated as "not configured".
_PLACEHOLDER_MARKERS = ("REPLACE_ME", "REPLACE_WITH", "TBD")


def _load() -> tuple[dict, str]:
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
_AI_PROVIDER_DEFAULTS = {
    "anthropic": {"model": "claude-sonnet-4-6", "key_env": "ANTHROPIC_API_KEY"},
    "gemini": {"model": "gemini-2.0-flash", "key_env": "GEMINI_API_KEY"},
}


def _norm_provider(p: str) -> str:
    p = (p or "").strip().lower()
    return "gemini" if p in ("gemini", "google") else p


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
    estock_configured: bool = _source_configured(_data.get("estock_source", {}))
    titan_configured: bool = _source_configured(_data.get("titan_drugeye_source", {}))
    procare_configured: bool = _source_configured(_data.get("procare_database", {}))

    # AI assistant. Supports Anthropic (Claude) and Google (Gemini). The key is
    # read from the environment, never from git — config only names which env var
    # holds it. Provider/model/key-env can be set in the config "ai" block OR via
    # environment (AI_PROVIDER / AI_MODEL), which is how the Docker stack sets it.
    # If nothing is set, we auto-detect from whichever API key is present.
    ai_provider: str = _detect_ai_provider()
    ai_model: str = _ai_model_for(ai_provider)
    ai_api_key_env: str = _ai_key_env_for(ai_provider)

    @staticmethod
    def procare_sqlalchemy_url() -> str | None:
        """SQL Server URL for ProCare's own DB, or None to use SQLite dev DB."""
        return _odbc_url(_data.get("procare_database", {}))

    @staticmethod
    def estock_sqlalchemy_url() -> str | None:
        """Read-only SQL Server URL for the eStock mirror source, or None."""
        return _odbc_url(_data.get("estock_source", {}))

    @staticmethod
    def titan_sqlalchemy_url() -> str | None:
        """Read-only URL for the Titan / Drug-Eye clinical source, or None.

        The Titan schema/engine under ``D:\\Labirdo`` is still TBD (docs/03), so
        this only builds a SQL Server URL when a real login is configured; the
        clinical service falls back to its curated advisory rules otherwise.
        """
        return _odbc_url(_data.get("titan_drugeye_source", {}))

    @staticmethod
    def estock_store_branch_map() -> dict | None:
        """Optional eStock store_id -> ProCare branch CODE/id map for the mirror.

        Configured under ``estock_source.store_branch_map`` (e.g.
        ``{"1": "MAIN", "2": "ELSANTA"}``). None lets the ETL use its default.
        """
        return _data.get("estock_source", {}).get("store_branch_map")

    @staticmethod
    def ai_api_key():
        """The AI provider's API key from the configured env var, or None if unset."""
        import os

        return os.environ.get(Settings.ai_api_key_env)

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
