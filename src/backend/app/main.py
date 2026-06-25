"""ProCare OS — FastAPI backend (Phase 1: mirror & read / shadow mode).

Runs out of the box with NO external database: on startup it seeds a local
SQLite "shadow" database with realistic synthetic data, so the dashboard,
Arabic AI assistant, expiry/low-stock alerts, drug-interaction lookup and
reconciliation all work immediately. When ``config/connections.json`` carries
real ``procare_database`` credentials (and the ODBC driver is present), the
same code reads ProCare's SQL Server system of record instead.

Guardrails (docs/01): ProCare never writes to eStock; the AI is read-only; the
clinical output is advisory; no secrets are exposed by the API.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("procare")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed the demo shadow DB if needed, then start the automation scheduler.
    try:
        from app.seed import ensure_seeded

        result = ensure_seeded()
        log.info("Data backend ready: %s", result)
    except Exception as exc:  # never block startup on demo seeding
        log.warning("Demo seed skipped: %s", exc)
    try:
        from app.scheduler import build_scheduler, shutdown

        build_scheduler()
    except Exception as exc:
        log.warning("Scheduler not started: %s", exc)
        shutdown = None  # type: ignore
    yield
    if shutdown:
        shutdown()


app = FastAPI(
    title="ProCare OS API",
    version="1.0.0",
    description="Independent pharmacy OS backend — Phase 1 (mirror & read, shadow mode).",
    lifespan=lifespan,
)

# The Next.js dev server runs on :3000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/", tags=["meta"])
def root():
    from app.db import get_db

    return {
        "app": "ProCare OS API",
        "version": app.version,
        "status": "ok",
        "docs": "/docs",
        "phase": "1 — mirror & read (shadow mode)",
        "data_backend": get_db().mode,
    }
