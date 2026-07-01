"""API tests for the dashboard stats endpoint."""

from __future__ import annotations


async def test_stats_requires_auth(client) -> None:
    resp = await client.get("/api/v1/stats")
    assert resp.status_code == 401


async def test_stats_empty(client, admin_headers) -> None:
    resp = await client.get("/api/v1/stats", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "assets": 0,
        "vlans": 0,
        "agents_total": 0,
        "agents_online": 0,
        "agents_offline": 0,
        "agents_never_seen": 0,
        "agents_disabled": 0,
        "open_changes": 0,
        "open_tasks": 0,
        "pending_runs": 0,
        "last_scan_at": None,
    }


async def test_stats_counts_reflect_data(client, admin_headers) -> None:
    await client.post("/api/v1/vlans", json={"name": "dmz"}, headers=admin_headers)
    await client.post("/api/v1/assets", json={"ip": "10.0.0.5"}, headers=admin_headers)
    await client.post("/api/v1/assets", json={"ip": "10.0.0.6"}, headers=admin_headers)
    await client.post("/api/v1/agents", json={"name": "a1"}, headers=admin_headers)
    await client.post("/api/v1/tasks", json={"title": "manual"}, headers=admin_headers)

    body = (await client.get("/api/v1/stats", headers=admin_headers)).json()
    assert body["vlans"] == 1
    assert body["assets"] == 2
    assert body["agents_total"] == 1
    assert body["agents_online"] == 0  # never heartbeat
    assert body["agents_never_seen"] == 1
    assert body["open_tasks"] == 1


async def test_stats_agent_health_breakdown(client, admin_headers) -> None:
    # Online: enrolled and just heartbeat.
    online = await client.post("/api/v1/agents", json={"name": "online-a"}, headers=admin_headers)
    await client.post(
        "/api/v1/agents/heartbeat",
        headers={"Authorization": f"Bearer {online.json()['token']}"},
    )
    # Never seen: enrolled, no heartbeat.
    await client.post("/api/v1/agents", json={"name": "never-a"}, headers=admin_headers)
    # Disabled: enrolled then disabled.
    disabled = await client.post("/api/v1/agents", json={"name": "off-a"}, headers=admin_headers)
    await client.patch(
        f"/api/v1/agents/{disabled.json()['id']}",
        json={"enabled": False},
        headers=admin_headers,
    )

    body = (await client.get("/api/v1/stats", headers=admin_headers)).json()
    assert body["agents_total"] == 3
    assert body["agents_online"] == 1
    assert body["agents_never_seen"] == 1
    assert body["agents_disabled"] == 1
    assert body["agents_offline"] == 0


async def test_charts_requires_auth(client) -> None:
    assert (await client.get("/api/v1/stats/charts")).status_code == 401


async def test_charts_empty_is_zero_filled(client, admin_headers) -> None:
    body = (await client.get("/api/v1/stats/charts", headers=admin_headers)).json()
    assert len(body["changes_by_day"]) == 30
    assert all(point["count"] == 0 for point in body["changes_by_day"])
    # Dates are sorted ascending and unique.
    dates = [point["date"] for point in body["changes_by_day"]]
    assert dates == sorted(dates)
    assert len(set(dates)) == 30

    assert [s["name"] for s in body["changes_by_type"]] == [
        "opened",
        "closed",
        "service_changed",
        "version_changed",
    ]
    assert [s["name"] for s in body["assets_by_criticality"]] == [
        "low",
        "medium",
        "high",
        "critical",
    ]
    assert [s["name"] for s in body["compliance_by_status"]] == [
        "compliant",
        "due_soon",
        "overdue",
        "never",
    ]
    for key in ("changes_by_type", "assets_by_criticality", "runs_by_status"):
        assert all(s["value"] == 0 for s in body[key])


async def test_charts_assets_by_criticality(client, admin_headers) -> None:
    await client.post(
        "/api/v1/assets",
        json={"ip": "10.0.0.10", "criticality": "high"},
        headers=admin_headers,
    )
    await client.post(
        "/api/v1/assets",
        json={"ip": "10.0.0.11", "criticality": "high"},
        headers=admin_headers,
    )
    body = (await client.get("/api/v1/stats/charts", headers=admin_headers)).json()
    by_crit = {s["name"]: s["value"] for s in body["assets_by_criticality"]}
    assert by_crit["high"] == 2
    assert sum(s["value"] for s in body["assets_by_criticality"]) == 2
