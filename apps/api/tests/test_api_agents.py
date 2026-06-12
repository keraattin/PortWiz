"""API integration tests for agent enrollment and scan-result ingest."""

from __future__ import annotations

import uuid


async def _make_scan_run(db) -> str:
    from portwiz_api.models.scan import ScanRun, ScanSource

    async with db() as session:
        run = ScanRun(scan_source=ScanSource.internal_unauthenticated)
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return str(run.id)


async def _enroll_agent(client, admin_headers, name: str) -> str:
    resp = await client.post("/api/v1/agents", json={"name": name}, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


async def test_enroll_returns_token_once_and_list_hides_it(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/agents", json={"name": "vlan10-agent"}, headers=admin_headers
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["token"]) > 20

    resp = await client.get("/api/v1/agents", headers=admin_headers)
    assert resp.status_code == 200
    agents = resp.json()
    assert any(a["name"] == "vlan10-agent" for a in agents)
    assert all("token" not in a for a in agents)


async def test_heartbeat_with_agent_token(client, admin_headers) -> None:
    token = await _enroll_agent(client, admin_headers, "hb-agent")
    resp = await client.post(
        "/api/v1/agents/heartbeat", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_ingest_creates_observations_and_finalizes_run(client, admin_headers, db) -> None:
    token = await _enroll_agent(client, admin_headers, "ingest-agent")
    run_id = await _make_scan_run(db)
    payload = {
        "version": 1,
        "job_id": str(uuid.uuid4()),
        "scan_run_id": run_id,
        "agent_id": "ingest-agent",
        "started_at": "2026-06-12T10:00:00Z",
        "finished_at": "2026-06-12T10:05:00Z",
        "status": "completed",
        "hosts": [
            {
                "ip": "10.0.0.5",
                "ports": [
                    {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
                    {
                        "port": 443,
                        "protocol": "tcp",
                        "state": "open",
                        "service": "https",
                        "banner": "nginx/1.25",
                    },
                ],
            }
        ],
    }
    resp = await client.post(
        "/api/v1/ingest/scan-results",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["observations"] == 2

    from sqlalchemy import func, select

    from portwiz_api.models.scan import Observation, ScanRun

    async with db() as session:
        count = (
            await session.execute(
                select(func.count())
                .select_from(Observation)
                .where(Observation.scan_run_id == uuid.UUID(run_id))
            )
        ).scalar_one()
        assert count == 2
        run = await session.get(ScanRun, uuid.UUID(run_id))
        assert run.status == "completed"
        assert run.finished_at is not None


async def test_ingest_requires_agent_token(client, db) -> None:
    run_id = await _make_scan_run(db)
    payload = {
        "version": 1,
        "job_id": str(uuid.uuid4()),
        "scan_run_id": run_id,
        "agent_id": "x",
        "started_at": "2026-06-12T10:00:00Z",
        "finished_at": "2026-06-12T10:05:00Z",
        "hosts": [],
    }
    resp = await client.post("/api/v1/ingest/scan-results", json=payload)
    assert resp.status_code == 401


async def test_ingest_unknown_run_is_404(client, admin_headers) -> None:
    token = await _enroll_agent(client, admin_headers, "unknown-run-agent")
    payload = {
        "version": 1,
        "job_id": str(uuid.uuid4()),
        "scan_run_id": str(uuid.uuid4()),
        "agent_id": "x",
        "started_at": "2026-06-12T10:00:00Z",
        "finished_at": "2026-06-12T10:05:00Z",
        "hosts": [],
    }
    resp = await client.post(
        "/api/v1/ingest/scan-results",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
