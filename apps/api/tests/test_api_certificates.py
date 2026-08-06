"""GET /certificates: current TLS certs with expiry status + hostname enrichment."""

from __future__ import annotations

import datetime as dt


async def _seed(db) -> None:
    from portwiz_api.models.asset import Asset
    from portwiz_api.models.scan import Observation, ScanRun, ScanSource

    now = dt.datetime.now(tz=dt.timezone.utc)
    async with db() as session:
        run = ScanRun(scan_source=ScanSource.internal_unauthenticated)
        session.add(run)
        session.add(Asset(ip="10.9.0.1", hostname="web-1"))
        await session.commit()
        session.add(
            Observation(
                ts=now,
                scan_run_id=run.id,
                ip="10.9.0.1",
                port=443,
                protocol="tcp",
                state="open",
                cert_subject_cn="web-1.example.com",
                cert_issuer="Test CA",
                cert_not_after=now - dt.timedelta(days=3),
                cert_self_signed=True,
            )
        )
        session.add(
            Observation(
                ts=now,
                scan_run_id=run.id,
                ip="10.9.0.2",
                port=8443,
                protocol="tcp",
                state="open",
                cert_subject_cn="api.example.com",
                cert_issuer="Test CA",
                cert_not_after=now + dt.timedelta(days=400),
                cert_self_signed=False,
            )
        )
        await session.commit()


async def test_list_certificates(client, admin_headers, db) -> None:
    await _seed(db)
    resp = await client.get("/api/v1/certificates", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 2
    by_ip = {c["ip"]: c for c in data}
    assert by_ip["10.9.0.1"]["status"] == "expired"
    assert by_ip["10.9.0.1"]["hostname"] == "web-1"  # enriched from the asset
    assert by_ip["10.9.0.1"]["self_signed"] is True
    assert by_ip["10.9.0.2"]["status"] == "valid"
    # Soonest expiry first.
    assert data[0]["ip"] == "10.9.0.1"


async def test_list_certificates_status_filter(client, admin_headers, db) -> None:
    await _seed(db)
    resp = await client.get(
        "/api/v1/certificates", params={"status": "expired"}, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 1
    assert data[0]["ip"] == "10.9.0.1"
