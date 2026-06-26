"""Test fixtures: an isolated, freshly-seeded in-process database + API client."""
from __future__ import annotations

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
