"""Tests for cron-based scan scheduling."""

from __future__ import annotations

import datetime as dt

import pytest

pytest.importorskip("croniter")

from portwiz_api.core.scheduler import cron_due  # noqa: E402

_NOW = dt.datetime(2026, 6, 13, 12, 0, 30, tzinfo=dt.timezone.utc)


def test_cron_due_minutely() -> None:
    assert cron_due("* * * * *", _NOW - dt.timedelta(minutes=5), _NOW) is True


def test_cron_due_not_yet() -> None:
    # No minute boundary has passed since the baseline (= now).
    assert cron_due("* * * * *", _NOW, _NOW) is False


def test_cron_due_invalid_or_missing() -> None:
    assert cron_due("not a cron", _NOW - dt.timedelta(days=1), _NOW) is False
    assert cron_due(None, _NOW - dt.timedelta(days=1), _NOW) is False


def test_cron_due_daily() -> None:
    # Daily midnight; baseline yesterday noon; midnight fired since -> due.
    assert cron_due("0 0 * * *", _NOW - dt.timedelta(days=1), _NOW) is True


async def test_run_due_scans_triggers_then_dedups(db) -> None:
    from portwiz_api.core.scheduler import run_due_scans
    from portwiz_api.models.scan import ScanProfile, ScanSource

    async with db() as session:
        session.add(
            ScanProfile(
                name="sched",
                targets=["10.0.0.1"],
                ports="22",
                scan_source=ScanSource.internal_unauthenticated,
                cron="* * * * *",
                created_at=_NOW - dt.timedelta(minutes=5),
                updated_at=_NOW,
            )
        )
        await session.commit()

    async with db() as session:
        created = await run_due_scans(session, now=_NOW)
        assert len(created) == 1

    # Same instant: already scheduled, so nothing new.
    async with db() as session:
        created_again = await run_due_scans(session, now=_NOW)
        assert len(created_again) == 0


async def _add_run(db, *, status, started_at, attempts):
    from portwiz_api.models.scan import ScanRun, ScanSource

    async with db() as session:
        run = ScanRun(
            scan_source=ScanSource.internal_unauthenticated,
            status=status,
            agent_id="agent-x",
            started_at=started_at,
            attempts=attempts,
        )
        session.add(run)
        await session.commit()
        return run.id


async def test_requeue_stale_run_back_to_pending(db) -> None:
    from portwiz_api.core.scheduler import requeue_stale_runs
    from portwiz_api.models.scan import ScanRun, ScanRunStatus

    rid = await _add_run(
        db,
        status=ScanRunStatus.running,
        started_at=_NOW - dt.timedelta(minutes=45),
        attempts=1,
    )
    async with db() as session:
        result = await requeue_stale_runs(session, now=_NOW, timeout_minutes=30, max_attempts=3)
        assert result == {"requeued": 1, "failed": 0}
    async with db() as session:
        run = await session.get(ScanRun, rid)
        assert run.status == ScanRunStatus.pending
        assert run.agent_id is None
        assert run.started_at is None


async def test_requeue_fails_after_max_attempts(db) -> None:
    from portwiz_api.core.scheduler import requeue_stale_runs
    from portwiz_api.models.scan import ScanRun, ScanRunStatus

    rid = await _add_run(
        db,
        status=ScanRunStatus.running,
        started_at=_NOW - dt.timedelta(minutes=45),
        attempts=3,
    )
    async with db() as session:
        result = await requeue_stale_runs(session, now=_NOW, timeout_minutes=30, max_attempts=3)
        assert result == {"requeued": 0, "failed": 1}
    async with db() as session:
        run = await session.get(ScanRun, rid)
        assert run.status == ScanRunStatus.failed
        assert run.error is not None


async def test_requeue_ignores_recent_run(db) -> None:
    from portwiz_api.core.scheduler import requeue_stale_runs
    from portwiz_api.models.scan import ScanRun, ScanRunStatus

    rid = await _add_run(
        db,
        status=ScanRunStatus.running,
        started_at=_NOW - dt.timedelta(minutes=5),  # not stale
        attempts=1,
    )
    async with db() as session:
        result = await requeue_stale_runs(session, now=_NOW, timeout_minutes=30, max_attempts=3)
        assert result == {"requeued": 0, "failed": 0}
    async with db() as session:
        run = await session.get(ScanRun, rid)
        assert run.status == ScanRunStatus.running
