"""Celery application.

Scheduling and scan-dispatch tasks land here in later milestones (M5). For now
it exposes a ping task so the worker container has something to run and proves
the broker connection.
"""

from __future__ import annotations

from celery import Celery

from ..core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "portwiz",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


@celery_app.task(name="portwiz.ping")
def ping() -> str:
    """Trivial health task."""
    return "pong"


@celery_app.task(name="portwiz.schedule_due_scans")
def schedule_due_scans() -> dict[str, int]:
    """Beat tick: trigger due cron scans and requeue runs that went stale."""
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from ..core.app_settings import effective_settings
    from ..core.scheduler import prune_observations, requeue_stale_runs, run_due_scans

    async def _run() -> dict[str, int]:
        # Use a fresh engine per tick to avoid cross-event-loop connection reuse.
        engine = create_async_engine(settings.database_url)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as session:
                # Honour admin-edited values (DB overrides), not just env.
                eff = await effective_settings(session)
                created = await run_due_scans(session)
                stale = await requeue_stale_runs(
                    session,
                    timeout_minutes=eff.scan_stale_minutes,
                    max_attempts=eff.scan_max_attempts,
                )
                pruned = await prune_observations(session, eff.retention_observation_days)
                return {"scheduled": len(created), **stale, "pruned": pruned}
        finally:
            await engine.dispose()

    return asyncio.run(_run())


@celery_app.task(name="portwiz.recheck_cves_due")
def recheck_cves_due() -> dict[str, int] | None:
    """Beat tick: run an automatic CVE re-check when its cadence is due.

    Kept off the 60s scan tick because a rate-limited lookup sweep can take
    minutes; a DB cursor (not this poll interval) sets the real cadence.
    """
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from ..core.app_settings import effective_settings
    from ..core.scheduler import run_due_cve_recheck

    async def _run() -> dict[str, int] | None:
        engine = create_async_engine(settings.database_url)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as session:
                eff = await effective_settings(session)
                return await run_due_cve_recheck(session, eff)
        finally:
            await engine.dispose()

    return asyncio.run(_run())


celery_app.conf.beat_schedule = {
    "schedule-due-scans": {
        "task": "portwiz.schedule_due_scans",
        "schedule": 60.0,
    },
    "recheck-cves-due": {
        "task": "portwiz.recheck_cves_due",
        "schedule": 600.0,  # poll every 10 min; cve_recheck_hours sets the cadence
    },
}
