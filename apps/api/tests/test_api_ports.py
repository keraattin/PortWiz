"""API tests for the open-ports observability endpoint."""

from __future__ import annotations

import datetime as dt


async def _seed(db) -> None:
    from portwiz_api.models.asset import Asset
    from portwiz_api.models.change import PortState
    from portwiz_api.models.scan import ScanProfile, ScanSource

    now = dt.datetime.now(dt.timezone.utc)
    async with db() as s:
        prof = ScanProfile(
            name="p", targets=["10.0.0.5"], ports="22,443",
            scan_source=ScanSource.internal_unauthenticated,
        )
        s.add(prof)
        await s.flush()
        s.add(Asset(ip="10.0.0.5", hostname="web01"))
        s.add(PortState(
            scan_profile_id=prof.id, ip="10.0.0.5", port=443, protocol="tcp",
            confirmed_state="open", confirmed_service="https",
            confirmed_version="nginx 1.25", last_seen_open_at=now,
        ))
        # A confirmed-closed port must not appear in the open-ports view.
        s.add(PortState(
            scan_profile_id=prof.id, ip="10.0.0.5", port=22, protocol="tcp",
            confirmed_state="closed",
        ))
        await s.commit()


async def test_open_ports_lists_confirmed_open_with_asset(client, admin_headers, db) -> None:
    await _seed(db)
    r = await client.get("/api/v1/ports", headers=admin_headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    hit = [x for x in rows if x["ip"] == "10.0.0.5" and x["port"] == 443]
    assert len(hit) == 1
    row = hit[0]
    assert row["protocol"] == "tcp"
    assert row["service"] == "https"
    assert row["version"] == "nginx 1.25"
    assert row["hostname"] == "web01"
    assert row["criticality"] == "medium"
    # the closed port 22 is not listed
    assert not any(x["ip"] == "10.0.0.5" and x["port"] == 22 for x in rows)


async def test_open_ports_requires_auth(client) -> None:
    r = await client.get("/api/v1/ports")
    assert r.status_code == 401


async def test_open_ports_filter_by_port(client, admin_headers, db) -> None:
    await _seed(db)
    r = await client.get("/api/v1/ports?port=443", headers=admin_headers)
    assert r.status_code == 200
    assert [x["port"] for x in r.json()] == [443]
