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
