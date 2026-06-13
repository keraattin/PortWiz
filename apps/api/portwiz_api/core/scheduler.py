"""Cron-based scan scheduling.

A Celery beat tick calls :func:`run_due_scans` periodically. For each enabled
profile with a cron expression, it triggers a scan run when a cron fire time has
passed since the profile was last scheduled (``last_scheduled_at``), which
guards against duplicate triggers.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .audit import append_audit
from ..models.scan import ScanProfile, ScanRun, ScanRunStatus, ScanSource


def _utcnow() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _aware(value: dt.datetime) -> dt.datetime:
    # SQLite drops tzinfo on DateTime(timezone=True); assume UTC for naive values.
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


def cron_due(cron_expr: str | None, baseline: dt.datetime, now: dt.datetime) -> bool:
    """True if a cron fire time falls after ``baseline`` and at/before ``now``."""
    from croniter import croniter

    if not cron_expr or not croniter.is_valid(cron_expr):
        return False
    now = _aware(now)
    baseline = _aware(baseline)
    previous_fire = _aware(croniter(cron_expr, now).get_prev(dt.datetime))
    return previous_fire > baseline


async def run_due_scans(session: AsyncSession, now: dt.datetime | None = None) -> list[ScanRun]:
    """Trigger a pending ScanRun for every profile whose cron is due."""
    now = now or _utcnow()
    profiles = (
        await session.execute(
            select(ScanProfile).where(
                ScanProfile.enabled.is_(True), ScanProfile.cron.is_not(None)
            )
        )
    ).scalars().all()

    created: list[ScanRun] = []
    for profile in profiles:
        baseline = profile.last_scheduled_at or profile.created_at
        if not cron_due(profile.cron, baseline, now):
            continue
        run = ScanRun(
            scan_profile_id=profile.id,
            scan_source=ScanSource(profile.scan_source),
            status=ScanRunStatus.pending,
        )
        session.add(run)
        profile.last_scheduled_at = now
        await session.flush()
        await append_audit(
            session,
            action="scan_run.scheduled",
            actor_email="system:scheduler",
            target_type="scan_run",
            target_id=str(run.id),
            payload={"scan_profile_id": str(profile.id), "cron": profile.cron},
        )
        created.append(run)

    if created:
        await session.commit()
    return created
