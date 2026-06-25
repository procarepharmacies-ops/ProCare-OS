"""PharmacyAutomation — scheduled jobs (APScheduler).

Phase-1 behaviour is shadow-safe: jobs COMPUTE and LOG, they never send a
WhatsApp/email or mutate stock. The cron cadence is the source of truth
(docs/04 §4.2):

  * expiry_alerts        — daily 09:00 (90/30/7-day horizons)
  * auto_purchase_order  — hourly (reorder DRAFTS, human approves in Phase 2)
  * auto_reports         — daily 08:00, weekly Sun 08:00, monthly 1st 08:00

The scheduler is optional: if APScheduler is not installed the app still runs;
the API simply reports the scheduler as unavailable.
"""
from __future__ import annotations

import logging

log = logging.getLogger("procare.automation")

_scheduler = None
_last_results: dict = {}


def _run_expiry_alerts():
    from app import alerts

    out = alerts.expiry_alerts("ALL")
    _last_results["expiry_alerts"] = out["counts"]
    log.info("expiry_alerts: %s (expected loss at risk %.2f)",
             out["counts"], out["expected_loss_at_risk"])


def _run_auto_purchase_order():
    from app import alerts

    out = alerts.reorder_drafts("ALL")
    _last_results["auto_purchase_order"] = {"drafts": out["count"]}
    log.info("auto_purchase_order: %s reorder drafts (not sent)", out["count"])


def _run_auto_reports():
    from app import queries

    summary = queries.dashboard_summary("ALL")["kpis"]
    _last_results["auto_reports"] = {
        "sales_today": summary["sales_today"],
        "sales_month": summary["sales_month"],
        "expiring_30": summary["expiring_30_days"],
        "low_stock": summary["low_stock_items"],
    }
    log.info("auto_reports KPI pack: %s", _last_results["auto_reports"])


def build_scheduler():
    """Return a started BackgroundScheduler, or None if APScheduler is missing."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except Exception:
        log.warning("APScheduler not installed — automation disabled.")
        return None

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(_run_expiry_alerts, CronTrigger(hour=9, minute=0),
                  id="expiry_alerts", replace_existing=True)
    sched.add_job(_run_auto_purchase_order, IntervalTrigger(hours=1),
                  id="auto_purchase_order", replace_existing=True)
    sched.add_job(_run_auto_reports, CronTrigger(hour=8, minute=0),
                  id="auto_reports_daily", replace_existing=True)
    sched.add_job(_run_auto_reports, CronTrigger(day_of_week="sun", hour=8, minute=0),
                  id="auto_reports_weekly", replace_existing=True)
    sched.add_job(_run_auto_reports, CronTrigger(day=1, hour=8, minute=0),
                  id="auto_reports_monthly", replace_existing=True)
    try:
        sched.start()
        _scheduler = sched
        log.info("Automation scheduler started with %d jobs.", len(sched.get_jobs()))
    except Exception as exc:
        log.warning("Scheduler failed to start: %s", exc)
        return None
    return _scheduler


def shutdown():
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None


def jobs_overview() -> dict:
    if _scheduler is None:
        return {"running": False, "available": _apscheduler_available(),
                "jobs": [], "last_results": _last_results}
    jobs = []
    for j in _scheduler.get_jobs():
        jobs.append({
            "id": j.id,
            "trigger": str(j.trigger),
            "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
        })
    return {"running": True, "available": True, "jobs": jobs, "last_results": _last_results}


def run_now(job: str) -> dict:
    """Manually fire a job once (for testing / on-demand)."""
    mapping = {
        "expiry_alerts": _run_expiry_alerts,
        "auto_purchase_order": _run_auto_purchase_order,
        "auto_reports": _run_auto_reports,
    }
    fn = mapping.get(job)
    if not fn:
        return {"ran": False, "error": f"unknown job '{job}'"}
    fn()
    return {"ran": True, "job": job, "result": _last_results.get(job)}


def _apscheduler_available() -> bool:
    try:
        import apscheduler  # noqa: F401
        return True
    except Exception:
        return False
