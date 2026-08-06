"""Connection-string building: Windows auth and named SQL Server instances.

A dev laptop running SQL Server Express installs a NAMED instance
(``host\\SQLEXPRESS``) and, by default, Windows-authentication-only. Both
differ from the production branch server (default instance, SQL logins), and
both used to leave the app silently on SQLite: ``_source_configured`` demanded
a username/password pair that Windows auth does not have.

These assert the connection string itself rather than a live connection, so
they run anywhere — no SQL Server, no ODBC driver.
"""
from __future__ import annotations

from urllib.parse import unquote_plus

from app.config import _is_trusted, _odbc_url, _source_configured


def _odbc(block: dict) -> str:
    """The decoded ODBC string a block produces."""
    url = _odbc_url(block)
    assert url is not None, "block should have been considered configured"
    return unquote_plus(url.split("odbc_connect=", 1)[1])


_TRUSTED = {
    "driver": "ODBC Driver 18 for SQL Server",
    "server": "localhost\\SQLEXPRESS",
    "database": "ProCare",
    "trusted_connection": True,
}

_SQL_LOGIN = {
    "driver": "ODBC Driver 18 for SQL Server",
    "server": "localhost",
    "port": 1433,
    "database": "ProCare",
    "username": "procare_app",
    "password": "a-real-password",
}


# --- _is_trusted -------------------------------------------------------------
def test_trusted_accepts_bool_and_common_strings():
    for value in (True, "true", "yes", "1", "on", "TRUE", " Yes "):
        assert _is_trusted({"trusted_connection": value}) is True, value


def test_trusted_rejects_falsey_and_absent():
    for value in (False, "false", "no", "0", "", None):
        assert _is_trusted({"trusted_connection": value}) is False, value
    assert _is_trusted({}) is False
    assert _is_trusted("not a dict") is False


# --- _source_configured ------------------------------------------------------
def test_trusted_block_is_configured_without_credentials():
    """The regression: Windows auth has no username/password to offer."""
    assert _source_configured(_TRUSTED) is True


def test_trusted_block_still_needs_server_and_database():
    """A stray flag alone must not read as configured — stay on SQLite."""
    assert _source_configured({"trusted_connection": True}) is False
    assert _source_configured({"trusted_connection": True, "server": "x"}) is False
    assert _source_configured({"trusted_connection": True, "database": "y"}) is False


def test_placeholder_server_is_not_configured():
    assert (
        _source_configured(
            {"trusted_connection": True, "server": "REPLACE_ME", "database": "ProCare"}
        )
        is False
    )


def test_sql_login_path_is_unchanged():
    assert _source_configured(_SQL_LOGIN) is True
    assert _source_configured({"username": "u", "password": "REPLACE_ME"}) is False
    assert _source_configured({}) is False


# --- _odbc_url: Windows auth -------------------------------------------------
def test_trusted_emits_trusted_connection_and_no_credentials():
    s = _odbc(_TRUSTED)
    assert "Trusted_Connection=yes" in s
    # Blank UID/PWD are not harmless: some drivers read an empty UID as an
    # attempted SQL login and fail before trying integrated auth.
    assert "UID=" not in s
    assert "PWD=" not in s


def test_trusted_keeps_driver_server_and_database():
    s = _odbc(_TRUSTED)
    assert "DRIVER={ODBC Driver 18 for SQL Server}" in s
    assert "SERVER=localhost\\SQLEXPRESS" in s
    assert "DATABASE=ProCare" in s


# --- _odbc_url: SQL login (unchanged behaviour) ------------------------------
def test_sql_login_emits_credentials_and_not_trusted():
    s = _odbc(_SQL_LOGIN)
    assert "UID=procare_app" in s
    assert "PWD=a-real-password" in s
    assert "Trusted_Connection" not in s


def test_sql_login_appends_the_port():
    assert "SERVER=localhost,1433" in _odbc(_SQL_LOGIN)


# --- named instances ---------------------------------------------------------
def test_named_instance_does_not_get_a_port_appended():
    """SQL Browser resolves a named instance; a port would override the name."""
    block = dict(_SQL_LOGIN, server="localhost\\SQLEXPRESS", port=1433)
    s = _odbc(block)
    assert "SERVER=localhost\\SQLEXPRESS" in s
    assert "SERVER=localhost\\SQLEXPRESS,1433" not in s


def test_server_with_a_baked_in_port_is_left_alone():
    block = dict(_SQL_LOGIN, server="192.168.1.2,1433", port=1433)
    s = _odbc(block)
    assert "SERVER=192.168.1.2,1433" in s
    assert ",1433,1433" not in s


def test_encrypt_defaults_are_applied_on_both_auth_paths():
    for block in (_TRUSTED, _SQL_LOGIN):
        s = _odbc(block)
        assert "Encrypt=yes" in s
        assert "TrustServerCertificate=yes" in s


def test_encrypt_can_be_overridden():
    s = _odbc(dict(_TRUSTED, encrypt="no", trust_server_certificate="no"))
    assert "Encrypt=no" in s
    assert "TrustServerCertificate=no" in s


def test_unconfigured_block_returns_none():
    assert _odbc_url({}) is None
    assert _odbc_url({"username": "u", "password": "REPLACE_ME"}) is None
