"""flush_due_notifications: digest cadence, quiet-hours holds, and marking.

notify_changes is stubbed (imported lazily inside the flush), so these tests
target the scheduler's queue/cadence logic, not the notifier fan-out.
"""

from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace

from sqlalchemy import select

from portwiz_api.core import scheduler
from portwiz_api.models.change import ChangeEvent
from portwiz_api.models.scan import ScanProfile, ScanSource

_NOW = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone.utc)


def _settings(**over):
    base = dict(
        notify_mode="hourly",
        notify_quiet_hours_enabled=False,
        notify_quiet_start="22:00",
        notify_quiet_end="07:00",
    )
    base.update(over)
    return SimpleNamespace(**base)


async def _make_profile(session) -> uuid.UUID:
    p = ScanProfile(
        name="np",
        targets=["10.0.0.1"],
        ports="22",
        scan_source=ScanSource.internal_unauthenticated,
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add(p)
    await session.commit()
    return p.id


def _change(pid, detected_at, notified_at=None):
    return ChangeEvent(
        scan_profile_id=pid,
        ip="10.0.0.1",
        port=22,
        protocol="tcp",
        change_type="opened",
        severity="high",
        detected_at=detected_at,
        notified_at=notified_at,
    )


def _patch_notify(monkeypatch):
    import portwiz_api.core.notifications as notif

    sent: list = []

    async def fake(summaries, settings):
        sent.append(summaries)
        return len(summaries)

    monkeypatch.setattr(notif, "notify_changes", fake)
    return sent


async def test_flush_nothing_pending_returns_none(db, monkeypatch) -> None:
    _patch_notify(monkeypatch)
    async with db() as session:
        assert await scheduler.flush_due_notifications(session, _settings(), now=_NOW) is None


async def test_flush_sends_and_marks_pending(db, monkeypatch) -> None:
    sent = _patch_notify(monkeypatch)
    async with db() as session:
        pid = await _make_profile(session)
        session.add(_change(pid, _NOW - dt.timedelta(minutes=5)))
        await session.commit()

    async with db() as session:
        n = await scheduler.flush_due_notifications(session, _settings(), now=_NOW)
    assert n == 1
    # The change was passed to notify_changes, tagged with its profile.
    assert len(sent) == 1 and sent[0][0]["scan_profile_id"] == str(pid)

    async with db() as session:
        rows = (await session.execute(select(ChangeEvent))).scalars().all()
        assert all(r.notified_at is not None for r in rows)  # marked processed


async def test_flush_hourly_respects_interval(db, monkeypatch) -> None:
    """After a flush claims the cursor, a change arriving inside the interval is
    not sent until the interval elapses."""
    sent = _patch_notify(monkeypatch)
    async with db() as session:
        pid = await _make_profile(session)
        session.add(_change(pid, _NOW - dt.timedelta(minutes=1)))
        await session.commit()

    async with db() as session:
        assert await scheduler.flush_due_notifications(session, _settings(), now=_NOW) == 1

    # New change 30 min later, still within the 1h window -> held.
    async with db() as session:
        session.add(_change(pid, _NOW + dt.timedelta(minutes=30)))
        await session.commit()
    async with db() as session:
        held = await scheduler.flush_due_notifications(
            session, _settings(), now=_NOW + dt.timedelta(minutes=30)
        )
    assert held is None
    assert len(sent) == 1  # no second send yet

    # Past the interval -> the held change goes out.
    async with db() as session:
        n = await scheduler.flush_due_notifications(
            session, _settings(), now=_NOW + dt.timedelta(hours=1, minutes=1)
        )
    assert n == 1
    assert len(sent) == 2


async def test_flush_holds_during_quiet_hours(db, monkeypatch) -> None:
    sent = _patch_notify(monkeypatch)
    quiet = _settings(
        notify_mode="immediate",
        notify_quiet_hours_enabled=True,
        notify_quiet_start="09:00",
        notify_quiet_end="17:00",
    )
    async with db() as session:
        pid = await _make_profile(session)
        session.add(_change(pid, _NOW - dt.timedelta(minutes=5)))
        await session.commit()

    # _NOW is 12:00, inside 09:00-17:00 quiet window -> held.
    async with db() as session:
        assert await scheduler.flush_due_notifications(session, quiet, now=_NOW) is None
    assert sent == []

    # After the window (18:00) immediate mode flushes the hold with no interval.
    async with db() as session:
        after = _NOW.replace(hour=18)
        n = await scheduler.flush_due_notifications(session, quiet, now=after)
    assert n == 1
    assert len(sent) == 1
