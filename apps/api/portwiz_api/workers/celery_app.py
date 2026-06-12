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
