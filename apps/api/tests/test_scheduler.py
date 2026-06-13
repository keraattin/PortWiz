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
