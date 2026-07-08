"""Automatic CVE re-check scheduling: gating, cadence cursor, and idempotence.

The re-check logic itself is covered elsewhere; here we pin the scheduler that
decides *when* it runs: it is off unless enabled with a positive cadence, it
claims a cursor when it runs, and it does not run again within the interval.
"""

from __future__ import annotations

import datetime as dt


class _FakeCVESource:
    name = "fake"

    async def lookup(self, product: str, version: str | None):
        from portwiz_api.core.cve import CVE

        return [CVE("CVE-2024-0001", 7.5, "high", f"flaw in {product}", "https://x")]

    async def verify(self):
        return True, "ok"


def _settings(**over):
    from portwiz_api.core.config import get_settings

    return get_settings().model_copy(update=over)


async def _seed_open_observation(db, ip: str = "10.0.0.30", port: int = 80) -> None:
    from portwiz_api.models.scan import Observation, ScanRun, ScanRunStatus

    async with db() as session:
        run = ScanRun(status=ScanRunStatus.completed)
        session.add(run)
        await session.flush()
        session.add(
            Observation(
                ts=dt.datetime.now(tz=dt.timezone.utc),
                scan_run_id=run.id,
                ip=ip,
                port=port,
                protocol="tcp",
                state="open",
                service="http",
                product="nginx",
                version="1.24.0",
            )
        )
        await session.commit()


async def test_recheck_skipped_when_disabled(db) -> None:
    from portwiz_api.core.scheduler import run_due_cve_recheck

    async with db() as session:
        result = await run_due_cve_recheck(
            session, _settings(cve_enabled=False, cve_recheck_hours=6)
        )
    assert result is None


async def test_recheck_skipped_when_hours_zero(db) -> None:
    from portwiz_api.core.scheduler import run_due_cve_recheck

    async with db() as session:
        result = await run_due_cve_recheck(
            session, _settings(cve_enabled=True, cve_recheck_hours=0)
        )
    assert result is None


async def test_recheck_runs_and_sets_cursor(db, monkeypatch) -> None:
    import portwiz_api.core.cve as cve_mod
    from portwiz_api.core.scheduler import _CVE_CURSOR_KEY, _get_cursor, run_due_cve_recheck

    monkeypatch.setattr(cve_mod, "build_cve_source", lambda s: _FakeCVESource())
    await _seed_open_observation(db)

    async with db() as session:
        result = await run_due_cve_recheck(
            session, _settings(cve_enabled=True, cve_recheck_hours=6)
        )
        assert result is not None
        assert result["findings"] == 1

        assert await _get_cursor(session, _CVE_CURSOR_KEY) is not None

        from sqlalchemy import func, select

        from portwiz_api.models.cve import CVEFinding

        count = (
            await session.execute(select(func.count()).select_from(CVEFinding))
        ).scalar_one()
        assert count == 1


async def test_recheck_not_due_within_interval(db, monkeypatch) -> None:
    import portwiz_api.core.cve as cve_mod
    from portwiz_api.core.scheduler import run_due_cve_recheck

    monkeypatch.setattr(cve_mod, "build_cve_source", lambda s: _FakeCVESource())
    await _seed_open_observation(db)
    settings = _settings(cve_enabled=True, cve_recheck_hours=6)

    async with db() as session:
        first = await run_due_cve_recheck(session, settings)
        assert first is not None
        # Immediately again: the cursor is fresh, so it is not yet due.
        second = await run_due_cve_recheck(session, settings)
        assert second is None
