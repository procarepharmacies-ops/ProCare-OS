"""ProCare OS — FastAPI backend (Phase 0 skeleton).

Runs standalone with NO database connection required: it reports configuration
status and serves stub endpoints so the frontend has a live API to talk to.
Real ETL, AI and POS endpoints arrive per docs/06-roadmap.md.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router

app = FastAPI(
    title="ProCare OS API",
    version="0.0.1",
    description="Independent pharmacy OS backend — Phase 0 skeleton.",
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
        "phase": "0 — skeleton (no DB wired yet)",
    }
