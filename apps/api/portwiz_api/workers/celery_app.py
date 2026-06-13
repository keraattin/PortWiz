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
def schedule_due_scans() -> int:
    """Beat tick: trigger scan profiles whose cron schedule is due."""
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from ..core.scheduler import run_due_scans

    async def _run() -> int:
        # Use a fresh engine per tick to avoid cross-event-loop connection reuse.
        engine = create_async_engine(settings.database_url)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as session:
                created = await run_due_scans(session)
                return len(created)
        finally:
            await engine.dispose()

    return asyncio.run(_run())


celery_app.conf.beat_schedule = {
    "schedule-due-scans": {
        "task": "portwiz.schedule_due_scans",
        "schedule": 60.0,
    },
}
