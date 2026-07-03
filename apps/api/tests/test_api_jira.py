"""API integration tests for the Jira issue-tracker integration.

A fake tracker is injected via FastAPI dependency override, so these run with
no real Jira instance.
"""

from __future__ import annotations

import uuid


class FakeTracker:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.last_severity: str | None = None

    async def create_issue(
        self, summary: str, description: str, *, severity: str | None = None
    ) -> str:
        key = f"PORT-{len(self.created) + 1}"
        self.created.append(key)
        self.last_severity = severity
        return key

    async def get_status(self, key: str) -> str:
        return "In Progress"

    async def list_priorities(self) -> list[str]:
        return ["Highest", "High", "Medium", "Low"]


def _use_fake_tracker() -> FakeTracker:
    from portwiz_api.core.issue_tracker import get_issue_tracker
    from portwiz_api.main import app

    fake = FakeTracker()
    app.dependency_overrides[get_issue_tracker] = lambda: fake
    return fake


async def _enroll(client, admin_headers, name: str) -> str:
    resp = await client.post("/api/v1/agents", json={"name": name}, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


async def _ingest(client, admin_headers, token, profile_id, ip, open_ports) -> None:
    run = (
        await client.post(f"/api/v1/scan-profiles/{profile_id}/run", headers=admin_headers)
    ).json()
    hosts = [{"ip": ip, "ports": [{"port": p, "protocol": "tcp", "state": "open"} for p in open_ports]}]
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


async def test_jira_disabled_returns_400(client, admin_headers) -> None:
    task = (
        await client.post("/api/v1/tasks", json={"title": "manual"}, headers=admin_headers)
    ).json()
    resp = await client.post(f"/api/v1/tasks/{task['id']}/jira", headers=admin_headers)
    assert resp.status_code == 400


async def test_priorities_route_lists_names(client, admin_headers) -> None:
    _use_fake_tracker()
    resp = await client.get("/api/v1/settings/jira/priorities", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == ["Highest", "High", "Medium", "Low"]


async def test_priorities_route_400_when_jira_disabled(client, admin_headers) -> None:
    # No fake override: the real tracker is a NullTracker (Jira not configured).
    resp = await client.get("/api/v1/settings/jira/priorities", headers=admin_headers)
    assert resp.status_code == 400


async def test_manual_link_and_sync(client, admin_headers) -> None:
    _use_fake_tracker()
    task = (
        await client.post("/api/v1/tasks", json={"title": "patch host"}, headers=admin_headers)
    ).json()

    resp = await client.post(f"/api/v1/tasks/{task['id']}/jira", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["jira_key"] == "PORT-1"

    # Linking twice is a conflict.
    resp = await client.post(f"/api/v1/tasks/{task['id']}/jira", headers=admin_headers)
    assert resp.status_code == 409

    resp = await client.post(f"/api/v1/tasks/{task['id']}/jira/sync", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"  # mapped from "In Progress"


async def test_auto_link_on_confirmed_change(client, admin_headers) -> None:
    fake = _use_fake_tracker()
    token = await _enroll(client, admin_headers, "jira-agent")
    profile = (
        await client.post(
            "/api/v1/scan-profiles",
            json={"name": "jira-profile", "targets": ["10.0.0.5"], "ports": "22,80,443"},
            headers=admin_headers,
        )
    ).json()
    pid, ip = profile["id"], "10.0.0.5"

    await _ingest(client, admin_headers, token, pid, ip, [22, 80])
    await _ingest(client, admin_headers, token, pid, ip, [22, 80])
    await _ingest(client, admin_headers, token, pid, ip, [22, 443])
    await _ingest(client, admin_headers, token, pid, ip, [22, 443])

    resp = await client.get("/api/v1/tasks", headers=admin_headers)
    auto = [t for t in resp.json() if t["change_event_id"]]
    assert len(auto) == 2
    assert all(t["jira_key"] for t in auto)
    assert len(fake.created) == 2
