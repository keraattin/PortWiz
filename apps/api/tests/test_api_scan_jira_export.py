"""API tests for exporting a scan run's changes to Jira (POST /scan-runs/{id}/jira).

A fake tracker is injected via dependency override, so these run with no Jira.
"""

from __future__ import annotations

import uuid


class FakeTracker:
    name = "jira"

    def __init__(self) -> None:
        self.created = 0

    async def create_issue(self, summary, description, *, severity=None):
        self.created += 1
        return f"PORT-{self.created}"

    async def verify(self):
        return True, "ok"


def _use_tracker(tracker) -> None:
    from portwiz_api.core.issue_tracker import get_issue_tracker
    from portwiz_api.main import app

    app.dependency_overrides[get_issue_tracker] = lambda: tracker


async def _enroll(client, admin_headers, name) -> str:
    resp = await client.post("/api/v1/agents", json={"name": name}, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


async def _profile(client, admin_headers, name, ip, ports) -> dict:
    resp = await client.post(
        "/api/v1/scan-profiles",
        json={"name": name, "targets": [ip], "ports": ports},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _ingest(client, admin_headers, token, pid, ip, open_ports) -> tuple[str, dict]:
    run = (
        await client.post(f"/api/v1/scan-profiles/{pid}/run", headers=admin_headers)
    ).json()
    hosts = (
        [
            {
                "ip": ip,
                "ports": [
                    {"port": p, "protocol": "tcp", "state": "open"} for p in open_ports
                ],
            }
        ]
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
    return run["id"], resp.json()


async def _run_with_changes(client, admin_headers) -> str:
    # Confirm on first appearance so a single follow-up run raises the changes.
    await client.patch(
        "/api/v1/settings/config", json={"change_confirmations": 1}, headers=admin_headers
    )
    token = await _enroll(client, admin_headers, "jira-agent")
    profile = await _profile(client, admin_headers, "jira-profile", "10.0.0.20", "22,80,443")
    pid, ip = profile["id"], "10.0.0.20"
    await _ingest(client, admin_headers, token, pid, ip, [22])  # baseline
    run_id, body = await _ingest(client, admin_headers, token, pid, ip, [22, 80, 443])
    assert body["changes"] == 2  # 80 and 443 opened
    return run_id


async def test_export_requires_auth(client) -> None:
    assert (await client.post(f"/api/v1/scan-runs/{uuid.uuid4()}/jira")).status_code == 401


async def test_export_missing_run_404(client, admin_headers) -> None:
    _use_tracker(FakeTracker())
    resp = await client.post(f"/api/v1/scan-runs/{uuid.uuid4()}/jira", headers=admin_headers)
    assert resp.status_code == 404


async def test_export_not_configured_returns_400(client, admin_headers) -> None:
    # No tracker override: the hermetic env disables Jira, so the dependency
    # yields a NullTracker and the endpoint refuses with a clear 400.
    run_id = await _run_with_changes(client, admin_headers)
    resp = await client.post(f"/api/v1/scan-runs/{run_id}/jira", headers=admin_headers)
    assert resp.status_code == 400


async def test_export_creates_issues_then_skips(client, admin_headers) -> None:
    run_id = await _run_with_changes(client, admin_headers)
    _use_tracker(FakeTracker())
    resp = await client.post(f"/api/v1/scan-runs/{run_id}/jira", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert body["exported"] == 2
    assert body["already_linked"] == 0

    # Re-export: the two changes are already linked, so nothing new is created.
    resp = await client.post(f"/api/v1/scan-runs/{run_id}/jira", headers=admin_headers)
    body = resp.json()
    assert body["exported"] == 0
    assert body["already_linked"] == 2


async def test_export_is_audited(client, admin_headers) -> None:
    run_id = await _run_with_changes(client, admin_headers)
    _use_tracker(FakeTracker())
    await client.post(f"/api/v1/scan-runs/{run_id}/jira", headers=admin_headers)
    audit = (await client.get("/api/v1/audit", headers=admin_headers)).json()
    assert any(e["action"] == "scan_run.jira_exported" for e in audit["events"])
