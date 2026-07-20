"""Test fixtures: an isolated, freshly-seeded in-process database + API client."""
from __future__ import annotations

import os
from pathlib import Path

# HARD ISOLATION — must be set BEFORE any app import builds the engine. Tests
# drop and reseed their database; without this override a configured production
# SQL Server (config/connections.json:procare_database) would be wiped by pytest.
_TEST_DB = Path(__file__).resolve().parents[2] / "data" / "procare_test.db"
os.environ["PROCARE_DB_URL"] = f"sqlite:///{_TEST_DB}"
# Pin config to the committed example file: tests must never see the operator's
# real connections.json (live eStock servers, production SQL Server).
_EXAMPLE_CFG = Path(__file__).resolve().parents[4] / "config" / "connections.example.json"
os.environ["PROCARE_CONFIG_FILE"] = str(_EXAMPLE_CFG)
# And tests must never start the live eStock sync thread — sync tests pass
# their own in-memory source engines instead.
os.environ["SYNC_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.seed import reset_and_seed


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    """Seed the dev database once for the whole test session."""
    reset_and_seed()
    yield


@pytest.fixture
def session() -> Session:
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client(seeded_db):
    from app.main import app

    with TestClient(app) as c:
        yield c
