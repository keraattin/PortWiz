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
    assert body["open_tasks"] == 1
