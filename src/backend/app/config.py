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
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={block.get('server', '')}",
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

    # AI assistant (Claude). The key itself is read from the environment, never
    # from git — config only names which env var holds it.
    ai_provider: str = _ai.get("provider", "anthropic")
    ai_model: str = _ai.get("model", "claude-sonnet-4-6")
    ai_api_key_env: str = _ai.get("api_key_env", "ANTHROPIC_API_KEY")

    @staticmethod
    def procare_sqlalchemy_url() -> str | None:
        """SQL Server URL for ProCare's own DB, or None to use SQLite dev DB."""
        return _odbc_url(_data.get("procare_database", {}))

    @staticmethod
    def estock_sqlalchemy_url() -> str | None:
        """Read-only SQL Server URL for the eStock mirror source, or None."""
        return _odbc_url(_data.get("estock_source", {}))

    @staticmethod
    def ai_api_key():
        """The Claude API key from the configured env var, or None if unset."""
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
