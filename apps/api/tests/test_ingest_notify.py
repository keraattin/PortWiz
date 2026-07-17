"""The per-profile notify_enabled flag gates change notifications at ingest.

detect_changes and notify_changes are stubbed so the test targets only the
ingest-level gate, not the (separately unit-tested) change detection or the
notifier fan-out.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

_FAKE_CHANGE = SimpleNamespace(
    change_type="opened", ip="10.0.0.60", port=22, protocol="tcp", severity="high"
)


async def _enroll(client, admin_headers) -> str:
    resp = await client.post(
        "/api/v1/agents", json={"name": "notify-agent"}, headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


async def _profile_run(client, admin_headers, ip: str, notify: bool) -> str:
    prof = await client.post(
        "/api/v1/scan-profiles",
        json={
            "name": f"notify-{notify}",
            "targets": [ip],
            "ports": "22",
            "notify_enabled": notify,
        },
        headers=admin_headers,
    )
    assert prof.status_code == 201, prof.text
    assert prof.json()["notify_enabled"] is notify
    pid = prof.json()["id"]
    run = await client.post(f"/api/v1/scan-profiles/{pid}/run", headers=admin_headers)
    return run.json()["id"]


def _payload(run_id: str, ip: str) -> dict:
    return {
        "version": 1,
        "job_id": str(uuid.uuid4()),
        "scan_run_id": run_id,
        "agent_id": "a",
        "started_at": "2026-06-18T10:00:00Z",
        "finished_at": "2026-06-18T10:05:00Z",
        "status": "completed",
        "hosts": [{"ip": ip, "ports": [{"port": 22, "protocol": "tcp", "state": "open"}]}],
    }


async def _ingest_with_fake_change(client, admin_headers, monkeypatch, notify: bool) -> list:
    from portwiz_api.api.routes import ingest

    sent: list = []

    async def _fake_detect(session, run):
        return [_FAKE_CHANGE]

    async def _fake_notify(summaries, settings):
        sent.append(summaries)
        return len(summaries)

    monkeypatch.setattr(ingest, "detect_changes", _fake_detect)
    monkeypatch.setattr(ingest, "notify_changes", _fake_notify)

    token = await _enroll(client, admin_headers)
    ip = "10.0.0.60"
    run_id = await _profile_run(client, admin_headers, ip, notify)
    resp = await client.post(
        "/api/v1/ingest/scan-results",
        json=_payload(run_id, ip),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202, resp.text
    return sent


async def test_notify_fires_when_profile_enabled(client, admin_headers, monkeypatch) -> None:
    sent = await _ingest_with_fake_change(client, admin_headers, monkeypatch, notify=True)
    assert len(sent) == 1


async def test_notify_suppressed_when_profile_disabled(
    client, admin_headers, monkeypatch
) -> None:
    sent = await _ingest_with_fake_change(client, admin_headers, monkeypatch, notify=False)
    assert sent == []
