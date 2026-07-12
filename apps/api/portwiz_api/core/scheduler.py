"""Cron-based scan scheduling.

A Celery beat tick calls :func:`run_due_scans` periodically. For each enabled
profile with a cron expression, it triggers a scan run when a cron fire time has
passed since the profile was last scheduled (``last_scheduled_at``), which
guards against duplicate triggers.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.app_setting import AppSetting
from ..models.scan import Observation, ScanProfile, ScanRun, ScanRunStatus, ScanSource
from .audit import append_audit

# Internal state cursor: when the last automatic CVE re-check ran. Stored in
# app_settings (not an EDITABLE_KEYS entry), so it is scheduler state, never
# user-settable, and effective_settings ignores it.
_CVE_CURSOR_KEY = "cve_last_recheck_at"


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

    # Profiles that already have an unclaimed pending run: don't stack another.
    # This bounds the queue to one waiting run per profile, so a segment with no
    # online agent doesn't accumulate an unbounded backlog of scheduled runs.
    pending_profile_ids = set(
        (
            await session.execute(
                select(ScanRun.scan_profile_id).where(
                    ScanRun.status == ScanRunStatus.pending,
                    ScanRun.scan_profile_id.is_not(None),
                )
            )
        ).scalars().all()
    )

    created: list[ScanRun] = []
    touched = False
    for profile in profiles:
        baseline = profile.last_scheduled_at or profile.created_at
        if not cron_due(profile.cron, baseline, now):
            continue
        if profile.id in pending_profile_ids:
            # A prior run is still waiting to be claimed; advance the cursor so we
            # don't re-evaluate this fire every tick, but skip creating a duplicate.
            profile.last_scheduled_at = now
            touched = True
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

    if created or touched:
        await session.commit()
    return created


async def requeue_stale_runs(
    session: AsyncSession,
    now: dt.datetime | None = None,
    timeout_minutes: int = 30,
    max_attempts: int = 3,
) -> dict[str, int]:
    """Recover runs an agent claimed but never finished.

    A run that has been ``running`` longer than ``timeout_minutes`` is put back
    to ``pending`` for another agent to claim, unless it has already been tried
    ``max_attempts`` times, in which case it is marked ``failed``.
    """
    now = _utcnow() if now is None else _aware(now)
    cutoff = now - dt.timedelta(minutes=timeout_minutes)

    running = (
        await session.execute(
            select(ScanRun).where(
                ScanRun.status == ScanRunStatus.running,
                ScanRun.started_at.is_not(None),
            )
        )
    ).scalars().all()

    requeued = failed = 0
    for run in running:
        if run.started_at is None or _aware(run.started_at) >= cutoff:
            continue  # not stale yet
        if run.attempts >= max_attempts:
            run.status = ScanRunStatus.failed
            run.error = f"Agent did not return results after {run.attempts} attempts"
            run.finished_at = now
            failed += 1
            action = "scan_run.failed"
        else:
            run.status = ScanRunStatus.pending
            run.agent_id = None
            run.started_at = None
            requeued += 1
            action = "scan_run.requeued"
        await append_audit(
            session,
            action=action,
            actor_email="system:scheduler",
            target_type="scan_run",
            target_id=str(run.id),
            payload={"attempts": run.attempts},
        )

    if requeued or failed:
        await session.commit()
    return {"requeued": requeued, "failed": failed}


async def _get_cursor(session: AsyncSession, key: str) -> dt.datetime | None:
    row = await session.get(AppSetting, key)
    if row is None or not row.value:
        return None
    try:
        return _aware(dt.datetime.fromisoformat(row.value))
    except ValueError:
        return None


async def _set_cursor(session: AsyncSession, key: str, value: dt.datetime) -> None:
    row = await session.get(AppSetting, key)
    iso = value.isoformat()
    if row is None:
        session.add(AppSetting(key=key, value=iso, updated_at=value))
    else:
        row.value = iso
        row.updated_at = value


async def run_due_cve_recheck(
    session: AsyncSession,
    settings,
    now: dt.datetime | None = None,
) -> dict[str, int] | None:
    """Run a bounded CVE re-check when enabled and its interval has elapsed.

    Returns the re-check result, or ``None`` when skipped: CVE enrichment is off,
    ``cve_recheck_hours`` is 0 (manual only), the source is not configured, or the
    interval has not passed yet. A global cursor in ``app_settings`` paces it
    independently of the beat poll, and is claimed *before* the (rate-limited)
    lookups run so overlapping ticks never double-check.
    """
    from .cve import NullCVESource, build_cve_source, recheck_cves

    hours = settings.cve_recheck_hours
    if not settings.cve_enabled or hours <= 0:
        return None
    source = build_cve_source(settings, session)
    if isinstance(source, NullCVESource):
        return None

    now = _utcnow() if now is None else _aware(now)
    last = await _get_cursor(session, _CVE_CURSOR_KEY)
    if last is not None and now - last < dt.timedelta(hours=hours):
        return None

    # Claim the slot first so a later tick, arriving while the rate-limited
    # lookups are still running, sees the advanced cursor and skips.
    await _set_cursor(session, _CVE_CURSOR_KEY, now)
    await session.commit()

    result = await recheck_cves(session, source)
    await append_audit(
        session,
        action="cve.rechecked",
        actor_email="system:scheduler",
        target_type="cve",
        target_id="*",
        payload={"source": source.name, **result},
    )
    await session.commit()
    return result


async def prune_observations(
    session: AsyncSession,
    retention_days: int,
    now: dt.datetime | None = None,
) -> int:
    """Delete raw observations older than ``retention_days`` (0 = keep forever).

    Only the high-volume time-series is pruned. Scan runs, change events and the
    immutable hash-chained audit log are deliberately never deleted, so the
    compliance record stays intact. A single audit event records how many rows
    were removed (not which), preserving the chain without unbounded growth.
    """
    if retention_days <= 0:
        return 0
    now = _utcnow() if now is None else _aware(now)
    cutoff = now - dt.timedelta(days=retention_days)

    count = (
        await session.execute(
            select(func.count()).select_from(Observation).where(Observation.ts < cutoff)
        )
    ).scalar_one()
    if not count:
        return 0

    await session.execute(delete(Observation).where(Observation.ts < cutoff))
    await append_audit(
        session,
        action="observations.pruned",
        actor_email="system:retention",
        target_type="observation",
        target_id="*",
        payload={"deleted": int(count), "retention_days": retention_days},
    )
    await session.commit()
    return int(count)
