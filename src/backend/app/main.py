"""ProCare OS — FastAPI backend.

ProCare's own, independent system of record. It runs standalone on its own
database (SQLite in dev, SQL Server in production) and exposes the dashboard,
inventory, customers/vendors, POS write-path, automation alerts and the Arabic
AI assistant.

eStock and Titan/Drug-Eye are read-only *sources* reached only by the
``app.services.etl`` adapter (Phase 1 mirror) — never written to. When no live
eStock login is configured the system runs on its own seeded demo data so the
whole stack is runnable offline.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.db.seed import ensure_seeded


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Create the schema and seed demo data on first run (idempotent). In
    # production with a live eStock login this is replaced by the read-only ETL.
    ensure_seeded()
    yield


app = FastAPI(
    title="ProCare OS API",
    version="1.0.0",
    description="Independent pharmacy OS backend — dashboard, POS, automation, Arabic AI assistant.",
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
    return {
        "app": "ProCare OS API",
        "version": app.version,
        "status": "ok",
        "docs": "/docs",
        "phase": "1–2 — dashboard, POS, automation, AI assistant on ProCare's own DB",
    }
