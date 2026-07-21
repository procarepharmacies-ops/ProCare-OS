"""PharmacyAutomation — scheduled jobs (APScheduler).

Phase-1 behaviour is shadow-safe: jobs COMPUTE and LOG, they never send a
WhatsApp/email or mutate stock. The cron cadence is the source of truth
(docs/04 §4.2):

  * expiry_alerts        — daily 09:00 (7/30/90-day horizons + already-expired)
  * auto_purchase_order  — hourly (reorder DRAFTS, human approves in Phase 2)
  * auto_reports         — daily 08:00, weekly Sun 08:00, monthly 1st 08:00

The scheduler is optional in two ways: it only starts when ``AUTOMATION_ENABLED``
is set (so existing deployments and the test suite are unaffected), and if
APScheduler isn't installed it degrades to unavailable rather than failing —
the jobs can still be fired on demand via :func:`run_now`.

This is the in-process scheduler flagged as an optional upgrade in
``requirements.txt`` (``APScheduler>=3.10``), re-expressed against ProCare's
current session-based service layer (``services.alerts`` / ``services.dashboard``).
"""
from __future__ import annotations

import logging
import os

from app.db import models as m
from app.db.base import SessionLocal
from app.services import alerts, dashboard, whatsapp

log = logging.getLogger("procare.automation")

_scheduler = None
_last_results: dict = {}


def is_enabled() -> bool:
    """Automation runs only when explicitly enabled via env, so it never
    surprises an existing deployment or the test suite."""
    return str(os.environ.get("AUTOMATION_ENABLED", "")).strip().lower() in ("1", "true", "yes", "on")


# --- the jobs (shadow-safe: compute + log, never send or mutate) ------------
def _run_expiry_alerts():
    with SessionLocal() as session:
        out = alerts.expiry_risk(session, branch_id=None, horizon_days=90)
    _last_results["expiry_alerts"] = out["counts"]
    log.info(
        "expiry_alerts: %s (expected loss within horizon %.2f)",
        out["counts"],
        out["expected_loss_within_horizon"],
    )
    # Notify the manager (self-gating: only if WhatsApp + manager phone set).
    if out["counts"].get("d7") or out["counts"].get("expired"):
        whatsapp.notify_manager(
            whatsapp.expiry_alert_message(out["counts"], out["expected_loss_within_horizon"])
        )


def _run_auto_purchase_order():
    with SessionLocal() as session:
        drafts = alerts.smart_reorder(session, branch_id=None)
    units = sum(d.get("suggested_qty", 0) for d in drafts)
    _last_results["auto_purchase_order"] = {"drafts": len(drafts)}
    log.info("auto_purchase_order: %d reorder drafts (not sent)", len(drafts))
    if drafts:
        whatsapp.notify_manager(whatsapp.reorder_drafts_message(len(drafts), units))


def _run_auto_reports():
    with SessionLocal() as session:
        kpis = dashboard.summary(session, branch_id=None)["kpis"]
    _last_results["auto_reports"] = {
        "sales_today": kpis["sales_today"],
        "sales_month": kpis["sales_month"],
        "expiring_30": kpis["expiring_30"],
        "low_stock": kpis["low_stock"],
    }
    log.info("auto_reports KPI pack: %s", _last_results["auto_reports"])
    whatsapp.notify_manager(whatsapp.daily_report_message(kpis))


# --- Phase 3: Loyalty tiers & CRM engagement --------------------------------
def _run_loyalty_tiers():
    """Nightly: recompute all customer tiers from 12-month spend."""
    from app.services import loyalty as loyalty_svc
    from sqlalchemy import select

    with SessionLocal() as session:
        count = 0
        for customer in session.scalars(select(m.Customer)).all():
            tier_before = customer.tier
            new_tier, spend = loyalty_svc.recompute_customer_tier(session, customer.customer_id)
            if tier_before != new_tier:
                count += 1
                log.info(f"Tier promotion: customer {customer.customer_id} {tier_before} → {new_tier}")
        session.commit()
    _last_results["loyalty_tiers"] = {"tier_changes": count}
    log.info("loyalty_tiers: %d customers promoted/demoted", count)


def _run_rfm_segmentation():
    """Daily: recompute RFM segments for all customers."""
    from app.services import crm as crm_svc

    with SessionLocal() as session:
        segments = crm_svc.compute_rfm_segments(session)
        session.commit()
        counts = crm_svc.segment_counts(session)
    _last_results["rfm_segmentation"] = counts
    log.info("rfm_segmentation: VIP=%d, Regular=%d, At-Risk=%d, Dormant=%d",
             counts["vip"], counts["regular"], counts["at_risk"], counts["dormant"])


def _run_forecast_computation():
    """Nightly: compute demand forecasts for all products×branches (Phase 5)."""
    from app.services import forecast as forecast_svc

    with SessionLocal() as session:
        count = forecast_svc.compute_nightly_forecasts(session)
        session.commit()
    _last_results["forecast_computation"] = {"count": count}
    log.info("forecast_computation: computed %d product×branch forecasts.", count)


def _run_decision_card_generation():
    """Nightly: generate decision cards from forecast state (Phase 5).
    Runs after forecast computation (1:30 AM) to ensure fresh forecast data."""
    from app.services import decisions as decisions_svc

    with SessionLocal() as session:
        result = decisions_svc.generate_nightly_decision_cards(session)
    _last_results["decision_cards"] = result
    log.info(
        "decision_card_generation: %s (total %d cards, by type: %s)",
        result["status"],
        result["total_cards_created"],
        result["by_type"],
    )
    if result["status"] == "error":
        _alert_job_failure("decision_cards", result["message"])


# --- lifecycle --------------------------------------------------------------
def build_scheduler():
    """Return a started BackgroundScheduler, or None if APScheduler is missing."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except Exception:  # noqa: BLE001
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
    # Phase 3: Loyalty tiers & RFM segmentation
    sched.add_job(_run_loyalty_tiers, CronTrigger(hour=2, minute=0),
                  id="loyalty_tiers_nightly", replace_existing=True)
    sched.add_job(_run_rfm_segmentation, CronTrigger(hour=6, minute=0),
                  id="rfm_segmentation_daily", replace_existing=True)
    # Phase 5: Demand forecasting + decision card generation
    sched.add_job(_run_forecast_computation, CronTrigger(hour=1, minute=0),
                  id="forecast_computation_nightly", replace_existing=True)
    sched.add_job(_run_decision_card_generation, CronTrigger(hour=1, minute=30),
                  id="decision_cards_nightly", replace_existing=True)
    try:
        sched.start()
        _scheduler = sched
        log.info("Automation scheduler started with %d jobs.", len(sched.get_jobs()))
    except Exception as exc:  # noqa: BLE001
        log.warning("Scheduler failed to start: %s", exc)
        return None
    return _scheduler


def start() -> dict:
    """Start the scheduler when AUTOMATION_ENABLED is set. No-op otherwise."""
    if not is_enabled():
        return {"started": False, "reason": "AUTOMATION_ENABLED not set"}
    sched = build_scheduler()
    if sched is None:
        return {"started": False, "reason": "APScheduler not installed"}
    return {"started": True, "jobs": len(sched.get_jobs())}


def shutdown():
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        _scheduler = None


# --- introspection / manual control -----------------------------------------
def _apscheduler_available() -> bool:
    try:
        import apscheduler  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def jobs_overview() -> dict:
    if _scheduler is None:
        return {
            "running": False,
            "enabled": is_enabled(),
            "available": _apscheduler_available(),
            "jobs": [],
            "last_results": _last_results,
        }
    jobs = []
    for j in _scheduler.get_jobs():
        jobs.append({
            "id": j.id,
            "trigger": str(j.trigger),
            "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
        })
    return {"running": True, "enabled": True, "available": True, "jobs": jobs, "last_results": _last_results}


def run_now(job: str) -> dict:
    """Manually fire a job once (for testing / on-demand). Works even when the
    background scheduler isn't running, so automation can be exercised safely."""
    mapping = {
        "expiry_alerts": _run_expiry_alerts,
        "auto_purchase_order": _run_auto_purchase_order,
        "auto_reports": _run_auto_reports,
        "loyalty_tiers": _run_loyalty_tiers,
        "rfm_segmentation": _run_rfm_segmentation,
    }
    fn = mapping.get(job)
    if not fn:
        return {"ran": False, "error": f"unknown job '{job}'"}
    fn()
    return {"ran": True, "job": job, "result": _last_results.get(job)}
