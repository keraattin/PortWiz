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
    from ..core.scheduler import requeue_stale_runs, run_due_scans

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
                return {"scheduled": len(created), **stale}
        finally:
            await engine.dispose()

    return asyncio.run(_run())


celery_app.conf.beat_schedule = {
    "schedule-due-scans": {
        "task": "portwiz.schedule_due_scans",
        "schedule": 60.0,
    },
}
