"""Integration tests for flapping-aware change detection.

These exercise the core differentiator: a change is only reported after it
persists for CONFIRMATIONS consecutive runs, and a flapping port produces no
change at all.
"""

from __future__ import annotations

import uuid


async def _enroll(client, admin_headers, name: str) -> str:
    resp = await client.post("/api/v1/agents", json={"name": name}, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


async def _profile(client, admin_headers, name: str, ip: str, ports: str) -> dict:
    resp = await client.post(
        "/api/v1/scan-profiles",
        json={"name": name, "targets": [ip], "ports": ports},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _ingest(client, admin_headers, token, profile_id, ip, open_ports) -> dict:
    resp = await client.post(
        f"/api/v1/scan-profiles/{profile_id}/run", headers=admin_headers
    )
    run = resp.json()
    hosts = (
        [{"ip": ip, "ports": [{"port": p, "protocol": "tcp", "state": "open"} for p in open_ports]}]
        if open_ports
        else []
    )
    payload = {
        "version": 1,
        "job_id": str(uuid.uuid4()),
        "scan_run_id": run["id"],
        "agent_id": "a",
        "started_at": "2026-06-12T10:00:00Z",
        "finished_at": "2026-06-12T10:05:00Z",
        "status": "completed",
        "hosts": hosts,
    }
    resp = await client.post(
        "/api/v1/ingest/scan-results",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202, resp.text
    return resp.json()


async def test_change_confirmed_after_threshold(client, admin_headers) -> None:
    token = await _enroll(client, admin_headers, "cd-agent")
    profile = await _profile(client, admin_headers, "cd-profile", "10.0.0.5", "22,80,443")
    pid, ip = profile["id"], "10.0.0.5"

    assert (await _ingest(client, admin_headers, token, pid, ip, [22, 80]))["changes"] == 0  # baseline
    assert (await _ingest(client, admin_headers, token, pid, ip, [22, 80]))["changes"] == 0  # stable
    assert (await _ingest(client, admin_headers, token, pid, ip, [22, 443]))["changes"] == 0  # candidate
    assert (await _ingest(client, admin_headers, token, pid, ip, [22, 443]))["changes"] == 2  # confirmed

    resp = await client.get(f"/api/v1/changes?scan_profile_id={pid}", headers=admin_headers)
    assert resp.status_code == 200
    by_type = {c["change_type"]: c for c in resp.json()}
    assert set(by_type) == {"opened", "closed"}
    assert by_type["opened"]["port"] == 443
    assert by_type["opened"]["after"]["state"] == "open"
    assert by_type["opened"]["severity"] == "high"
    assert by_type["closed"]["port"] == 80
    assert by_type["closed"]["before"]["state"] == "open"


async def test_changes_ip_port_filters(client, admin_headers) -> None:
    # The per-host and per-port timelines rely on ip/port scoping.
    token = await _enroll(client, admin_headers, "hist-agent")
    profile = await _profile(client, admin_headers, "hist-profile", "10.0.0.5", "22,80,443")
    pid, ip = profile["id"], "10.0.0.5"
    await _ingest(client, admin_headers, token, pid, ip, [22, 80])
    await _ingest(client, admin_headers, token, pid, ip, [22, 80])
    await _ingest(client, admin_headers, token, pid, ip, [22, 443])
    await _ingest(client, admin_headers, token, pid, ip, [22, 443])

    by_ip = (await client.get(f"/api/v1/changes?ip={ip}", headers=admin_headers)).json()
    assert {c["change_type"] for c in by_ip} == {"opened", "closed"}
    assert all(c["ip"] == ip for c in by_ip)

    by_port = (
        await client.get(f"/api/v1/changes?ip={ip}&port=443", headers=admin_headers)
    ).json()
    assert len(by_port) == 1
    assert by_port[0]["port"] == 443 and by_port[0]["change_type"] == "opened"

    # A port that never changed has no history.
    quiet = (await client.get(f"/api/v1/changes?ip={ip}&port=22", headers=admin_headers)).json()
    assert quiet == []


async def test_changes_limit_bounds(client, admin_headers) -> None:
    # A negative/zero limit is a clean 422, not a 500 (Postgres LIMIT -1 crash).
    assert (await client.get("/api/v1/changes?limit=-1", headers=admin_headers)).status_code == 422
    assert (await client.get("/api/v1/changes?limit=0", headers=admin_headers)).status_code == 422
    assert (await client.get("/api/v1/changes?limit=10", headers=admin_headers)).status_code == 200


async def test_change_confirmations_setting(client, admin_headers) -> None:
    # With the admin-tunable confirmations lowered to 1, a candidate confirms on
    # its first appearance instead of needing a second consecutive run.
    await client.patch(
        "/api/v1/settings/config", json={"change_confirmations": 1}, headers=admin_headers
    )
    token = await _enroll(client, admin_headers, "cd1-agent")
    profile = await _profile(client, admin_headers, "cd1-profile", "10.0.0.6", "22,80,443")
    pid, ip = profile["id"], "10.0.0.6"

    assert (await _ingest(client, admin_headers, token, pid, ip, [22, 80]))["changes"] == 0  # baseline
    assert (await _ingest(client, admin_headers, token, pid, ip, [22, 443]))["changes"] == 2  # confirmed now


async def test_flapping_produces_no_change(client, admin_headers) -> None:
    token = await _enroll(client, admin_headers, "flap-agent")
    profile = await _profile(client, admin_headers, "flap-profile", "10.0.0.6", "22")
    pid, ip = profile["id"], "10.0.0.6"

    assert (await _ingest(client, admin_headers, token, pid, ip, [22]))["changes"] == 0  # baseline
    assert (await _ingest(client, admin_headers, token, pid, ip, []))["changes"] == 0  # disappears
    assert (await _ingest(client, admin_headers, token, pid, ip, [22]))["changes"] == 0  # back: no real change

    resp = await client.get(f"/api/v1/changes?scan_profile_id={pid}", headers=admin_headers)
    assert resp.json() == []


async def test_acknowledge_change(client, admin_headers) -> None:
    token = await _enroll(client, admin_headers, "ack-agent")
    profile = await _profile(client, admin_headers, "ack-profile", "10.0.0.7", "22")
    pid, ip = profile["id"], "10.0.0.7"

    await _ingest(client, admin_headers, token, pid, ip, [22])  # baseline
    await _ingest(client, admin_headers, token, pid, ip, [])  # candidate close
    assert (await _ingest(client, admin_headers, token, pid, ip, []))["changes"] == 1  # confirmed close

    resp = await client.get(f"/api/v1/changes?scan_profile_id={pid}", headers=admin_headers)
    change = resp.json()[0]
    assert change["change_type"] == "closed"
    assert change["status"] == "open"

    resp = await client.patch(
        f"/api/v1/changes/{change['id']}",
        json={"status": "acknowledged"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"


async def test_known_port_recurrence_is_auto_acknowledged(client, admin_headers) -> None:
    # Once a port's change is acknowledged, an identical change recurring later is
    # recorded but auto-acknowledged and not re-alarmed, so a flapping-but-known
    # port stops paging the team on every transition.
    await client.patch(
        "/api/v1/settings/config", json={"change_confirmations": 1}, headers=admin_headers
    )
    token = await _enroll(client, admin_headers, "known-agent")
    profile = await _profile(client, admin_headers, "known-profile", "10.0.0.8", "22,80")
    pid, ip = profile["id"], "10.0.0.8"

    await _ingest(client, admin_headers, token, pid, ip, [22])  # baseline: 80 closed
    opened = await _ingest(client, admin_headers, token, pid, ip, [22, 80])  # 80 opens
    assert opened["changes"] == 1 and opened["suppressed"] == 0

    port80 = (
        await client.get(f"/api/v1/changes?ip={ip}&port=80", headers=admin_headers)
    ).json()
    first = port80[0]
    assert first["change_type"] == "opened" and first["status"] == "open"

    # The team accepts this port as known.
    ack = await client.patch(
        f"/api/v1/changes/{first['id']}",
        json={"status": "acknowledged"},
        headers=admin_headers,
    )
    assert ack.status_code == 200

    await _ingest(client, admin_headers, token, pid, ip, [22])  # 80 closes
    reopened = await _ingest(client, admin_headers, token, pid, ip, [22, 80])  # opens again
    # The recurrence is counted but suppressed: no new open alarm.
    assert reopened["changes"] == 1 and reopened["suppressed"] == 1

    opens = [
        c
        for c in (
            await client.get(f"/api/v1/changes?ip={ip}&port=80", headers=admin_headers)
        ).json()
        if c["change_type"] == "opened"
    ]
    assert len(opens) == 2
    assert all(c["status"] == "acknowledged" for c in opens)
