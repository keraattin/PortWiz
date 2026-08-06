"""TLS certificate expiry monitoring: current-cert view + scheduler cadence."""

from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace

from portwiz_api.core import scheduler
from portwiz_api.core.cert_monitor import current_certificates, expiring_certificates
from portwiz_api.models.scan import Observation, ScanRun, ScanSource

_NOW = dt.datetime(2026, 8, 5, 12, 0, tzinfo=dt.timezone.utc)


async def _make_run(session) -> uuid.UUID:
    r = ScanRun(scan_source=ScanSource.internal_unauthenticated)
    session.add(r)
    await session.commit()
    return r.id


def _obs(run_id, ip, port, not_after, ts, subject="example.com"):
    return Observation(
        ts=ts,
        scan_run_id=run_id,
        ip=ip,
        port=port,
        protocol="tcp",
        state="open",
        cert_subject_cn=subject,
        cert_issuer="Test CA",
        cert_not_after=not_after,
        cert_self_signed=False,
    )


def _settings(**over):
    base = dict(cert_expiry_recheck_hours=24, cert_expiry_warn_days=30)
    base.update(over)
    return SimpleNamespace(**base)


async def test_current_certificates_classifies_expiry(db) -> None:
    async with db() as session:
        run_id = await _make_run(session)
        session.add(_obs(run_id, "10.0.0.1", 443, _NOW - dt.timedelta(days=2), _NOW))
        session.add(_obs(run_id, "10.0.0.2", 8443, _NOW + dt.timedelta(days=10), _NOW))
        session.add(_obs(run_id, "10.0.0.3", 993, _NOW + dt.timedelta(days=200), _NOW))
        await session.commit()

    async with db() as session:
        certs = await current_certificates(session, now=_NOW, warn_days=30)
    by_ip = {c.ip: c for c in certs}
    assert by_ip["10.0.0.1"].status == "expired"
    assert by_ip["10.0.0.2"].status == "expiring"
    assert by_ip["10.0.0.3"].status == "valid"
    assert len(expiring_certificates(certs)) == 2
    # Soonest-expiry first.
    assert certs[0].ip == "10.0.0.1"


async def test_current_certificates_uses_latest_observation(db) -> None:
    async with db() as session:
        run_id = await _make_run(session)
        # Old observation: already expired.
        session.add(
            _obs(run_id, "10.0.0.9", 443, _NOW - dt.timedelta(days=1), _NOW - dt.timedelta(days=5))
        )
        # Newer observation: renewed certificate, valid.
        session.add(_obs(run_id, "10.0.0.9", 443, _NOW + dt.timedelta(days=90), _NOW))
        await session.commit()

    async with db() as session:
        certs = await current_certificates(session, now=_NOW, warn_days=30)
    assert len(certs) == 1
    assert certs[0].status == "valid"


async def test_cert_expiry_check_cadence(db, monkeypatch) -> None:
    import portwiz_api.core.cert_monitor as cm

    sent: list = []

    async def fake_notify(certs, settings):
        sent.append(list(certs))
        return 1

    monkeypatch.setattr(cm, "notify_cert_expiry", fake_notify)

    async with db() as session:
        run_id = await _make_run(session)
        session.add(_obs(run_id, "10.0.0.1", 443, _NOW - dt.timedelta(days=1), _NOW))
        await session.commit()

    # Disabled when the cadence is 0.
    async with db() as session:
        assert (
            await scheduler.run_due_cert_expiry_check(
                session, _settings(cert_expiry_recheck_hours=0), now=_NOW
            )
            is None
        )

    # First due run alerts on the expired cert and claims the cursor.
    async with db() as session:
        res = await scheduler.run_due_cert_expiry_check(session, _settings(), now=_NOW)
    assert res == {"expiring": 1, "expired": 1, "notified": 1}
    assert len(sent) == 1

    # A second run inside the interval is skipped (cursor claimed).
    async with db() as session:
        assert (
            await scheduler.run_due_cert_expiry_check(
                session, _settings(), now=_NOW + dt.timedelta(hours=1)
            )
            is None
        )
    assert len(sent) == 1


async def test_cert_expiry_check_nothing_expiring(db, monkeypatch) -> None:
    import portwiz_api.core.cert_monitor as cm

    sent: list = []

    async def fake_notify(certs, settings):
        sent.append(certs)
        return 0

    monkeypatch.setattr(cm, "notify_cert_expiry", fake_notify)

    async with db() as session:
        run_id = await _make_run(session)
        session.add(_obs(run_id, "10.0.0.5", 443, _NOW + dt.timedelta(days=200), _NOW))
        await session.commit()

    async with db() as session:
        res = await scheduler.run_due_cert_expiry_check(session, _settings(), now=_NOW)
    assert res == {"expiring": 0, "expired": 0, "notified": 0}
    assert sent == []  # notify is not called when nothing is expiring
