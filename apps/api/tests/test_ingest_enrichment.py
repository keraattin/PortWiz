"""AI fingerprint enrichment during scan ingest.

A low-confidence banner is refined by the configured AI provider before change
detection; if no provider is configured the observation is stored unchanged.
"""

from __future__ import annotations

import uuid


class _FakeProvider:
    name = "fake"

    async def complete(self, system: str, user: str) -> str:
        return "Service: ssh\nVersion: OpenSSH 9.6\nSummary: secure shell"


async def _enroll(client, admin_headers) -> str:
    resp = await client.post(
        "/api/v1/agents", json={"name": "enrich-agent"}, headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


async def _run(client, admin_headers, ip: str) -> str:
    prof = await client.post(
        "/api/v1/scan-profiles",
        json={"name": "enrich-prof", "targets": [ip], "ports": "22"},
        headers=admin_headers,
    )
    pid = prof.json()["id"]
    run = await client.post(f"/api/v1/scan-profiles/{pid}/run", headers=admin_headers)
    return run.json()["id"]


def _payload(run_id: str, ip: str) -> dict:
    return {
        "version": 1,
        "job_id": str(uuid.uuid4()),
        "scan_run_id": run_id,
        "agent_id": "a",
        "started_at": "2026-06-18T10:00:00Z",
        "finished_at": "2026-06-18T10:05:00Z",
        "status": "completed",
        "hosts": [
            {
                "ip": ip,
                "ports": [
                    {
                        "port": 22,
                        "protocol": "tcp",
                        "state": "open",
                        "banner": "SSH-2.0-OpenSSH_9.6",
                        "fingerprint_confidence": 0.2,
                    }
                ],
            }
        ],
    }


async def _observation(db, run_id: str):
    from sqlalchemy import select

    from portwiz_api.models.scan import Observation

    async with db() as session:
        return (
            await session.execute(
                select(Observation).where(Observation.scan_run_id == uuid.UUID(run_id))
            )
        ).scalars().first()


async def test_ingest_enriches_low_confidence_banner(client, admin_headers, db) -> None:
    from portwiz_api.core.ai import get_ai_provider
    from portwiz_api.main import app

    app.dependency_overrides[get_ai_provider] = lambda: _FakeProvider()
    try:
        token = await _enroll(client, admin_headers)
        ip = "10.0.0.50"
        run_id = await _run(client, admin_headers, ip)
        resp = await client.post(
            "/api/v1/ingest/scan-results",
            json=_payload(run_id, ip),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 202, resp.text
    finally:
        del app.dependency_overrides[get_ai_provider]

    obs = await _observation(db, run_id)
    assert obs is not None
    assert obs.service == "ssh"
    assert obs.version == "OpenSSH 9.6"


def _payload_host(run_id: str, ip: str, hostname: str | None) -> dict:
    host: dict = {"ip": ip, "ports": [{"port": 80, "protocol": "tcp", "state": "open"}]}
    if hostname is not None:
        host["hostname"] = hostname
    return {
        "version": 1,
        "job_id": str(uuid.uuid4()),
        "scan_run_id": run_id,
        "agent_id": "a",
        "started_at": "2026-06-19T10:00:00Z",
        "finished_at": "2026-06-19T10:05:00Z",
        "status": "completed",
        "hosts": [host],
    }


async def test_ingest_auto_creates_discovered_asset(client, admin_headers, db) -> None:
    from sqlalchemy import select

    from portwiz_api.models.asset import Asset

    token = await _enroll(client, admin_headers)
    ip = "10.0.0.77"
    run_id = await _run(client, admin_headers, ip)
    resp = await client.post(
        "/api/v1/ingest/scan-results",
        json=_payload_host(run_id, ip, "web-77"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["discovered_assets"] == 1

    async with db() as session:
        asset = (
            await session.execute(select(Asset).where(Asset.ip == ip))
        ).scalars().first()
    assert asset is not None
    assert asset.hostname == "web-77"
    assert asset.criticality == "low"
    assert asset.discovered is True


async def test_ingest_keeps_known_asset(client, admin_headers, db) -> None:
    from sqlalchemy import func, select

    from portwiz_api.models.asset import Asset

    ip = "10.0.0.78"
    created = await client.post(
        "/api/v1/assets", json={"ip": ip, "criticality": "high"}, headers=admin_headers
    )
    assert created.status_code == 201, created.text

    token = await _enroll(client, admin_headers)
    run_id = await _run(client, admin_headers, ip)
    resp = await client.post(
        "/api/v1/ingest/scan-results",
        json=_payload_host(run_id, ip, "should-not-overwrite"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["discovered_assets"] == 0  # already known

    async with db() as session:
        count = (
            await session.execute(
                select(func.count()).select_from(Asset).where(Asset.ip == ip)
            )
        ).scalar_one()
        asset = (
            await session.execute(select(Asset).where(Asset.ip == ip))
        ).scalars().first()
    assert count == 1  # not duplicated
    assert asset.criticality == "high"  # scan did not change it
    assert asset.hostname is None  # scan did not overwrite
    assert asset.discovered is False  # manually created, not discovered


async def test_ingest_without_ai_keeps_raw(client, admin_headers, db) -> None:
    # With no AI provider configured, enrichment is skipped and the banner is
    # stored as-is (no network call attempted).
    from portwiz_api.core.ai import NullProvider, get_ai_provider
    from portwiz_api.main import app

    app.dependency_overrides[get_ai_provider] = lambda: NullProvider()
    try:
        token = await _enroll(client, admin_headers)
        ip = "10.0.0.51"
        run_id = await _run(client, admin_headers, ip)
        resp = await client.post(
            "/api/v1/ingest/scan-results",
            json=_payload(run_id, ip),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 202, resp.text
    finally:
        del app.dependency_overrides[get_ai_provider]

    obs = await _observation(db, run_id)
    assert obs is not None
    assert obs.service is None  # not enriched


class _FakeSource:
    name = "netbox"

    def __init__(self) -> None:
        self.pushed: list[str] = []

    async def push_assets(self, assets):
        from portwiz_api.core.inventory_source import PushResult

        self.pushed = [a.ip for a in assets]
        return PushResult(created=len(assets))


async def test_ingest_auto_writeback_when_enabled(client, admin_headers, db) -> None:
    from portwiz_api.core.app_settings import set_overrides
    from portwiz_api.core.inventory_source import get_inventory_source
    from portwiz_api.main import app

    fake = _FakeSource()
    app.dependency_overrides[get_inventory_source] = lambda: fake
    async with db() as session:
        await set_overrides(
            session, {"netbox_writeback_enabled": True}, actor_id=None, actor_email="t"
        )

    token = await _enroll(client, admin_headers)
    ip = "10.0.0.88"
    run_id = await _run(client, admin_headers, ip)
    resp = await client.post(
        "/api/v1/ingest/scan-results",
        json=_payload(run_id, ip),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202, resp.text
    # The just-discovered host is written back to NetBox.
    assert fake.pushed == [ip]


async def test_ingest_no_writeback_when_disabled(client, admin_headers) -> None:
    from portwiz_api.core.inventory_source import get_inventory_source
    from portwiz_api.main import app

    fake = _FakeSource()
    app.dependency_overrides[get_inventory_source] = lambda: fake  # writeback off by default

    token = await _enroll(client, admin_headers)
    ip = "10.0.0.89"
    run_id = await _run(client, admin_headers, ip)
    resp = await client.post(
        "/api/v1/ingest/scan-results",
        json=_payload(run_id, ip),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202, resp.text
    assert fake.pushed == []
