"""API integration tests for tasks (auto-created and manual)."""

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


async def _ingest(client, admin_headers, token, profile_id, ip, open_ports) -> None:
    run = (
        await client.post(f"/api/v1/scan-profiles/{profile_id}/run", headers=admin_headers)
    ).json()
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
        "started_at": "2026-06-13T10:00:00Z",
        "finished_at": "2026-06-13T10:05:00Z",
        "status": "completed",
        "hosts": hosts,
    }
    resp = await client.post(
        "/api/v1/ingest/scan-results",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202, resp.text


async def _login(client, email, password) -> dict:
    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_confirmed_change_creates_tasks(client, admin_headers) -> None:
    token = await _enroll(client, admin_headers, "task-agent")
    profile = await _profile(client, admin_headers, "task-profile", "10.0.0.5", "22,80,443")
    pid, ip = profile["id"], "10.0.0.5"

    await _ingest(client, admin_headers, token, pid, ip, [22, 80])
    await _ingest(client, admin_headers, token, pid, ip, [22, 80])
    await _ingest(client, admin_headers, token, pid, ip, [22, 443])
    await _ingest(client, admin_headers, token, pid, ip, [22, 443])

    resp = await client.get("/api/v1/tasks", headers=admin_headers)
    assert resp.status_code == 200
    auto = [t for t in resp.json() if t["change_event_id"]]
    assert len(auto) == 2
    assert all(t["status"] == "open" for t in auto)
    assert all(t["title"].startswith("Review ") for t in auto)


async def test_manual_task_crud(client, admin_headers) -> None:
    created_user = (
        await client.post(
            "/api/v1/users",
            json={"email": "assignee@test.local", "password": "Secret123!", "role": "operator"},
            headers=admin_headers,
        )
    ).json()

    resp = await client.post(
        "/api/v1/tasks",
        json={"title": "Patch firewall", "description": "close 23"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    task = resp.json()
    assert task["status"] == "open"
    assert task["created_by"] is not None

    resp = await client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"status": "in_progress", "assignee_id": created_user["id"]},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
    assert resp.json()["assignee_id"] == created_user["id"]

    resp = await client.get("/api/v1/tasks?task_status=in_progress", headers=admin_headers)
    assert any(t["id"] == task["id"] for t in resp.json())

    resp = await client.delete(f"/api/v1/tasks/{task['id']}", headers=admin_headers)
    assert resp.status_code == 204


async def test_task_rejects_unknown_assignee(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/tasks",
        json={"title": "x", "assignee_id": str(uuid.uuid4())},
        headers=admin_headers,
    )
    assert resp.status_code == 400


async def test_task_rbac(client, admin_headers) -> None:
    await client.post(
        "/api/v1/users",
        json={"email": "audtask@test.local", "password": "Secret123!", "role": "auditor"},
        headers=admin_headers,
    )
    auditor_headers = await _login(client, "audtask@test.local", "Secret123!")

    resp = await client.post("/api/v1/tasks", json={"title": "nope"}, headers=auditor_headers)
    assert resp.status_code == 403

    resp = await client.get("/api/v1/tasks", headers=auditor_headers)
    assert resp.status_code == 200
