"""API tests for segment-based scan-job routing."""

from __future__ import annotations


async def _enroll(client, admin_headers, name, segment=None) -> str:
    body = {"name": name}
    if segment is not None:
        body["segment"] = segment
    resp = await client.post("/api/v1/agents", json=body, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


async def _profile(client, admin_headers, name, segment=None) -> str:
    body = {"name": name, "targets": ["10.0.0.0/30"]}
    if segment is not None:
        body["segment"] = segment
    resp = await client.post("/api/v1/scan-profiles", json=body, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _trigger(client, admin_headers, profile_id) -> str:
    resp = await client.post(
        f"/api/v1/scan-profiles/{profile_id}/run", headers=admin_headers
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


async def _poll(client, token):
    return await client.get(
        "/api/v1/agents/jobs", headers={"Authorization": f"Bearer {token}"}
    )


async def test_jobs_routed_by_segment(client, admin_headers) -> None:
    dmz_token = await _enroll(client, admin_headers, "dmz-agent", "dmz")
    core_token = await _enroll(client, admin_headers, "core-agent")  # no segment

    p_dmz = await _profile(client, admin_headers, "dmz-profile", "dmz")
    p_core = await _profile(client, admin_headers, "core-profile")  # no segment
    run_dmz = await _trigger(client, admin_headers, p_dmz)
    run_core = await _trigger(client, admin_headers, p_core)

    # The unsegmented agent claims the unsegmented run, not the dmz one,
    # even though the dmz run was created first.
    resp = await _poll(client, core_token)
    assert resp.status_code == 200, resp.text
    assert resp.json()["scan_run_id"] == run_core

    # The dmz agent claims the dmz run.
    resp = await _poll(client, dmz_token)
    assert resp.status_code == 200
    assert resp.json()["scan_run_id"] == run_dmz


async def test_agent_skips_other_segment_runs(client, admin_headers) -> None:
    dmz_token = await _enroll(client, admin_headers, "dmz-only", "dmz")
    p_core = await _profile(client, admin_headers, "core")  # no segment
    await _trigger(client, admin_headers, p_core)

    # The only pending run is unsegmented, so the dmz agent has no work.
    resp = await _poll(client, dmz_token)
    assert resp.status_code == 204


async def test_segment_persisted_on_enroll(client, admin_headers) -> None:
    await _enroll(client, admin_headers, "vlan10", "vlan10")
    agents = (await client.get("/api/v1/agents", headers=admin_headers)).json()
    agent = next(a for a in agents if a["name"] == "vlan10")
    assert agent["segment"] == "vlan10"


async def _agent_id(client, admin_headers, name) -> str:
    agents = (await client.get("/api/v1/agents", headers=admin_headers)).json()
    return next(a for a in agents if a["name"] == name)["id"]


async def test_update_agent_segment(client, admin_headers) -> None:
    await _enroll(client, admin_headers, "movable")  # no segment
    aid = await _agent_id(client, admin_headers, "movable")
    resp = await client.patch(
        f"/api/v1/agents/{aid}", json={"segment": "dmz"}, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["segment"] == "dmz"


async def test_disable_agent_blocks_polling(client, admin_headers) -> None:
    token = await _enroll(client, admin_headers, "toggle")
    aid = await _agent_id(client, admin_headers, "toggle")
    # Disable, then the agent token can no longer authenticate.
    resp = await client.patch(
        f"/api/v1/agents/{aid}", json={"enabled": False}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert (await _poll(client, token)).status_code == 401


async def test_update_agent_requires_admin(client, admin_headers) -> None:
    await _enroll(client, admin_headers, "target-agent")
    aid = await _agent_id(client, admin_headers, "target-agent")
    # Reuse the db via a second login: create an operator and try the PATCH.
    resp = await client.post(
        "/api/v1/users",
        json={"email": "op2@test.local", "password": "Secret123!", "role": "operator"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    login = await client.post(
        "/api/v1/auth/login", data={"username": "op2@test.local", "password": "Secret123!"}
    )
    op_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.patch(
        f"/api/v1/agents/{aid}", json={"segment": "x"}, headers=op_headers
    )
    assert resp.status_code == 403


async def test_agent_rate_cap_only_lowers_dispatched_rate(client, admin_headers) -> None:
    token = await _enroll(client, admin_headers, "capped")
    aid = await _agent_id(client, admin_headers, "capped")
    # Profile keeps the configured default rate (1000 pps); the agent caps at 200.
    await client.patch(
        f"/api/v1/agents/{aid}", json={"rate_limit_pps_override": 200}, headers=admin_headers
    )
    pid = await _profile(client, admin_headers, "fast-profile")
    await _trigger(client, admin_headers, pid)
    job = (await _poll(client, token)).json()
    assert job["rate_limit_pps"] == 200  # min(1000, 200)


async def test_agent_rate_cap_never_raises_rate(client, admin_headers) -> None:
    token = await _enroll(client, admin_headers, "generous")
    aid = await _agent_id(client, admin_headers, "generous")
    await client.patch(
        f"/api/v1/agents/{aid}", json={"rate_limit_pps_override": 5000}, headers=admin_headers
    )
    pid = await _profile(client, admin_headers, "normal-profile")
    await _trigger(client, admin_headers, pid)
    job = (await _poll(client, token)).json()
    assert job["rate_limit_pps"] == 1000  # min(1000, 5000)


async def test_update_agent_404(client, admin_headers) -> None:
    import uuid

    resp = await client.patch(
        f"/api/v1/agents/{uuid.uuid4()}", json={"segment": "x"}, headers=admin_headers
    )
    assert resp.status_code == 404
