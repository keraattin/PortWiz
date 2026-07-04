"""API integration tests for scan profiles, triggering, and agent job poll."""

from __future__ import annotations


async def _enroll_agent(client, admin_headers, name: str) -> str:
    resp = await client.post("/api/v1/agents", json={"name": name}, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


async def _create_profile(client, admin_headers, **overrides) -> dict:
    payload = {"name": "weekly", "targets": ["10.0.0.0/30"], "ports": "22,80"}
    payload.update(overrides)
    resp = await client.post("/api/v1/scan-profiles", json=payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_uses_configured_scan_defaults(client, admin_headers) -> None:
    # Admin sets scan defaults; a create that omits those fields inherits them.
    await client.patch(
        "/api/v1/settings/config",
        json={
            "default_scan_ports": "1-1024",
            "default_scan_type": "syn",
            "default_service_detection": False,
            "default_scan_rate_limit_pps": 250,
        },
        headers=admin_headers,
    )
    resp = await client.post(
        "/api/v1/scan-profiles",
        json={"name": "defaults-profile", "targets": ["10.0.0.0/30"]},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["ports"] == "1-1024"
    assert body["scan_type"] == "syn"
    assert body["service_detection"] is False
    assert body["rate_limit_pps"] == 250

    # An explicit value still wins over the default.
    resp = await client.post(
        "/api/v1/scan-profiles",
        json={"name": "explicit-profile", "targets": ["10.0.0.1"], "ports": "443"},
        headers=admin_headers,
    )
    assert resp.json()["ports"] == "443"


async def test_profile_crud_and_trigger(client, admin_headers) -> None:
    profile = await _create_profile(client, admin_headers)
    assert profile["targets"] == ["10.0.0.0/30"]

    resp = await client.get("/api/v1/scan-profiles", headers=admin_headers)
    assert any(p["id"] == profile["id"] for p in resp.json())

    resp = await client.patch(
        f"/api/v1/scan-profiles/{profile['id']}",
        json={"ports": "443"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["ports"] == "443"

    resp = await client.post(
        f"/api/v1/scan-profiles/{profile['id']}/run", headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert run["status"] == "pending"
    assert run["scan_profile_id"] == profile["id"]

    resp = await client.get("/api/v1/scan-runs", headers=admin_headers)
    assert any(r["id"] == run["id"] for r in resp.json())


async def test_scan_runs_limit_bounds(client, admin_headers) -> None:
    # A negative/zero limit is a clean 422, not a 500 (Postgres LIMIT -1 crash).
    assert (await client.get("/api/v1/scan-runs?limit=-1", headers=admin_headers)).status_code == 422
    assert (await client.get("/api/v1/scan-runs?limit=0", headers=admin_headers)).status_code == 422
    assert (await client.get("/api/v1/scan-runs?limit=5", headers=admin_headers)).status_code == 200


async def test_profile_rejects_invalid_targets(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/scan-profiles",
        json={"name": "bad", "targets": ["nope"]},
        headers=admin_headers,
    )
    assert resp.status_code == 422


async def test_agent_poll_claims_pending_run(client, admin_headers) -> None:
    token = await _enroll_agent(client, admin_headers, "poller")
    profile = await _create_profile(
        client, admin_headers, name="poll-profile", targets=["127.0.0.1"], ports="80"
    )
    resp = await client.post(
        f"/api/v1/scan-profiles/{profile['id']}/run", headers=admin_headers
    )
    run = resp.json()

    agent_headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get("/api/v1/agents/jobs", headers=agent_headers)
    assert resp.status_code == 200, resp.text
    job = resp.json()
    assert job["scan_run_id"] == run["id"]
    assert job["targets"] == ["127.0.0.1"]
    assert job["ports"] == "80"
    assert job["scan_type"] == "connect"
    assert job["scan_source"] == "internal-unauthenticated"

    resp = await client.get(f"/api/v1/scan-runs/{run['id']}", headers=admin_headers)
    assert resp.json()["status"] == "running"

    # No more pending work.
    resp = await client.get("/api/v1/agents/jobs", headers=agent_headers)
    assert resp.status_code == 204


async def test_poll_without_work_returns_204(client, admin_headers) -> None:
    token = await _enroll_agent(client, admin_headers, "idle-poller")
    resp = await client.get(
        "/api/v1/agents/jobs", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204
