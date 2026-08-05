"""Automation scheduler status + on-demand job runs (management only).

Read-only visibility into the in-process scheduler (``services.scheduler``):
which jobs are registered, when they next run, and their last computed results.
``POST /run/{job}`` fires a job once on demand — useful for testing the shadow-
safe automation without waiting for its cron time. Jobs never send or mutate;
they compute and log.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import auth_guard
from app.services import db_health, scheduler

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/status")
def status(_auth=Depends(auth_guard(("ceo", "manager")))):
    return scheduler.jobs_overview()


@router.get("/db-health")
def db_health_status(_auth=Depends(auth_guard(("ceo", "manager")))):
    """DB size vs the SQL Server Express cap + disk free space, graded to a
    severity. Powers the ops dashboard tile and the hourly WhatsApp alert."""
    return db_health.check()


@router.post("/run/{job}")
def run(job: str, _auth=Depends(auth_guard(("ceo", "manager")))):
    result = scheduler.run_now(job)
    if not result.get("ran"):
        raise HTTPException(status_code=404, detail=result.get("error", "unknown job"))
    return result
