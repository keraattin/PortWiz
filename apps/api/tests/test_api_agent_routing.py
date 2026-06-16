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
