"""The eStock demo seed must never drop a real-sized eStock database."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.db import estock_seed


def test_seed_refuses_real_sized_source():
    eng = create_engine("sqlite://")
    try:
        with eng.begin() as c:
            c.execute(text("CREATE TABLE Products (product_id INTEGER PRIMARY KEY, product_name_ar TEXT)"))
            c.execute(
                text("INSERT INTO Products (product_id, product_name_ar) VALUES (:i, 'x')"),
                [{"i": i} for i in range(estock_seed.REAL_SOURCE_PRODUCTS)],
            )
        with pytest.raises(RuntimeError, match="refusing"):
            estock_seed.seed_estock_source(eng, days=1)
        with eng.connect() as c:
            assert c.execute(text("SELECT COUNT(*) FROM Products")).scalar() == estock_seed.REAL_SOURCE_PRODUCTS
    finally:
        eng.dispose()


def test_seed_still_builds_an_empty_demo_source():
    eng = create_engine("sqlite://")
    try:
        estock_seed.seed_estock_source(eng, days=1)
        with eng.connect() as c:
            assert c.execute(text("SELECT COUNT(*) FROM Products")).scalar() > 0
    finally:
        eng.dispose()


def test_cli_engine_refuses_configured_live_source(monkeypatch):
    monkeypatch.delenv("ESTOCK_SEED_URL", raising=False)
    monkeypatch.delenv("ESTOCK_ENSURE_DB", raising=False)
    with pytest.raises(SystemExit):
        estock_seed._engine_from_env()
