"""Port false-positive suppression: change-detection skip, CRUD API, ports filter."""

from __future__ import annotations

import datetime as dt
import uuid

from portwiz_api.core.change_detection import detect_changes
from portwiz_api.models.change import ChangeEvent, PortState, PortSuppression
from portwiz_api.models.scan import (
    Observation,
    ScanProfile,
    ScanRun,
    ScanRunStatus,
    ScanSource,
)

_NOW = dt.datetime(2026, 8, 5, 12, 0, tzinfo=dt.timezone.utc)


async def _profile(session) -> uuid.UUID:
    p = ScanProfile(
        name="fp-prof",
        targets=["10.0.0.1"],
        ports="22,139",
        scan_source=ScanSource.internal_unauthenticated,
        created_at=_NOW,
        updated_at=_NOW,
    )
    session.add(p)
    await session.commit()
    return p.id


async def _run_with_ports(session, pid, ports, ts) -> ScanRun:
    run = ScanRun(
        scan_profile_id=pid,
        scan_source=ScanSource.internal_unauthenticated,
        status=ScanRunStatus.completed,
    )
    session.add(run)
    await session.commit()
    for port in ports:
        session.add(
            Observation(
                ts=ts,
                scan_run_id=run.id,
                ip="10.0.0.1",
                port=port,
                protocol="tcp",
                state="open",
            )
        )
    await session.commit()
    return run


async def _confirmations_one(session) -> None:
    from portwiz_api.core.app_settings import set_overrides

    await set_overrides(
        session, {"change_confirmations": 1}, actor_id=None, actor_email="t"
    )


async def test_suppressed_port_raises_no_change(db) -> None:
    async with db() as session:
        pid = await _profile(session)
        await _confirmations_one(session)
        # Baseline run establishes port 22 silently.
        run1 = await _run_with_ports(session, pid, [22], _NOW)
        await detect_changes(session, run1)
        await session.commit()
        # Mark port 139 a false positive before it is ever seen.
        session.add(PortSuppression(ip="10.0.0.1", port=139, protocol="tcp"))
        await session.commit()
        # Second run: 139 now open, but suppressed -> no event.
        run2 = await _run_with_ports(
            session, pid, [22, 139], _NOW + dt.timedelta(minutes=5)
        )
        events = await detect_changes(session, run2)
        await session.commit()

    assert events == []
    async with db() as session:
        from sqlalchemy import select

        rows = (
            await session.execute(
                select(ChangeEvent).where(ChangeEvent.port == 139)
            )
        ).scalars().all()
        assert rows == []


async def test_unsuppressed_port_raises_change(db) -> None:
    async with db() as session:
        pid = await _profile(session)
        await _confirmations_one(session)
        run1 = await _run_with_ports(session, pid, [22], _NOW)
        await detect_changes(session, run1)
        await session.commit()
        run2 = await _run_with_ports(
            session, pid, [22, 139], _NOW + dt.timedelta(minutes=5)
        )
        events = await detect_changes(session, run2)
        await session.commit()

    opened = [e for e in events if e.port == 139 and e.change_type == "opened"]
    assert len(opened) == 1


async def test_suppression_crud(client, admin_headers) -> None:
    body = {"ip": "10.9.9.9", "port": 445, "protocol": "tcp", "reason": "test box"}
    resp = await client.post("/api/v1/suppressions", json=body, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["ip"] == "10.9.9.9" and created["port"] == 445
    sid = created["id"]

    # Idempotent: marking the same port again returns the existing row.
    resp2 = await client.post("/api/v1/suppressions", json=body, headers=admin_headers)
    assert resp2.status_code == 201, resp2.text
    assert resp2.json()["id"] == sid

    listed = await client.get("/api/v1/suppressions", headers=admin_headers)
    assert listed.status_code == 200
    assert any(s["id"] == sid for s in listed.json())

    deleted = await client.delete(f"/api/v1/suppressions/{sid}", headers=admin_headers)
    assert deleted.status_code == 204
    listed2 = await client.get("/api/v1/suppressions", headers=admin_headers)
    assert listed2.json() == []


async def test_ports_view_hides_suppressed(client, admin_headers, db) -> None:
    async with db() as session:
        pid = await _profile(session)
        session.add(
            PortState(
                scan_profile_id=pid,
                ip="10.9.9.10",
                port=139,
                protocol="tcp",
                confirmed_state="open",
                last_seen_open_at=_NOW,
                updated_at=_NOW,
            )
        )
        session.add(PortSuppression(ip="10.9.9.10", port=139, protocol="tcp"))
        await session.commit()

    # Default: the suppressed port is hidden.
    resp = await client.get("/api/v1/ports", params={"ip": "10.9.9.10"}, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == []

    # include_suppressed surfaces it, flagged.
    resp2 = await client.get(
        "/api/v1/ports",
        params={"ip": "10.9.9.10", "include_suppressed": "true"},
        headers=admin_headers,
    )
    data = resp2.json()
    assert len(data) == 1
    assert data[0]["port"] == 139 and data[0]["suppressed"] is True
