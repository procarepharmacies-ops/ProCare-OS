"""Shared test fixtures — point ProCare at a throwaway seeded SQLite DB."""
import os
import tempfile

import pytest

# Use a dedicated demo DB for the whole test session, created BEFORE app import.
_TMP = os.path.join(tempfile.gettempdir(), "procare_test.sqlite")
os.environ["PROCARE_DEMO_DB"] = _TMP
# Ensure no stray AI key flips the assistant into network mode during tests.
os.environ.pop("ANTHROPIC_API_KEY", None)


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    if os.path.exists(_TMP):
        os.remove(_TMP)
    from app.db import reset_db_for_tests
    from app.seed import seed

    reset_db_for_tests(_TMP)
    seed(reset=True)
    yield
    if os.path.exists(_TMP):
        os.remove(_TMP)
