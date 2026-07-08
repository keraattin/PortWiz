"""API tests for CVE enrichment: re-check and list findings.

A fake CVE source is injected via dependency override, so these run with no
network and no NVD access.
"""

from __future__ import annotations

import uuid


class FakeCVESource:
    name = "fake"

    async def lookup(self, product: str, version: str | None):
        from portwiz_api.core.cve import CVE

        return [
            CVE(
                cve_id="CVE-2024-0001",
                cvss=7.5,
                severity="high",
                summary=f"A flaw in {product} {version}",
                url="https://nvd.nist.gov/vuln/detail/CVE-2024-0001",
            )
        ]

    async def verify(self):
        return True, "fake ok"


def _use_fake_cve_source() -> FakeCVESource:
    from portwiz_api.core.cve import get_cve_source
    from portwiz_api.main import app

    fake = FakeCVESource()
    app.dependency_overrides[get_cve_source] = lambda: fake
    return fake


async def _ingest_versioned_service(client, admin_headers) -> None:
    """Enroll an agent, run a profile and ingest one host with a versioned port,
    so there's an open observation carrying a service+version to CVE-check."""
    token = (
        await client.post("/api/v1/agents", json={"name": "cve-agent"}, headers=admin_headers)
    ).json()["token"]
    profile = (
        await client.post(
            "/api/v1/scan-profiles",
            json={"name": "cve-profile", "targets": ["10.0.0.7"], "ports": "80"},
            headers=admin_headers,
        )
    ).json()
    run = (
        await client.post(
            f"/api/v1/scan-profiles/{profile['id']}/run", headers=admin_headers
        )
    ).json()
    payload = {
        "version": 1,
        "job_id": str(uuid.uuid4()),
        "scan_run_id": run["id"],
        "agent_id": "cve-agent",
        "started_at": "2026-07-07T10:00:00Z",
        "finished_at": "2026-07-07T10:05:00Z",
        "status": "completed",
        "hosts": [
            {
                "ip": "10.0.0.7",
                "ports": [
                    {
                        "port": 80,
                        "protocol": "tcp",
                        "state": "open",
                        "service": "http",
                        "product": "nginx",
                        "version": "1.24.0",
                    }
                ],
            }
        ],
    }
    resp = await client.post(
        "/api/v1/ingest/scan-results",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202, resp.text


async def test_recheck_populates_findings(client, admin_headers) -> None:
    _use_fake_cve_source()
    await _ingest_versioned_service(client, admin_headers)

    resp = await client.post("/api/v1/cve/recheck", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checked"] == 1
    assert body["findings"] == 1

    findings = (await client.get("/api/v1/cve/findings", headers=admin_headers)).json()
    assert len(findings) == 1
    f = findings[0]
    assert f["cve_id"] == "CVE-2024-0001"
    assert f["severity"] == "high"
    assert f["port"] == 80
    assert f["ip"] == "10.0.0.7"


async def test_recheck_is_idempotent(client, admin_headers) -> None:
    _use_fake_cve_source()
    await _ingest_versioned_service(client, admin_headers)
    await client.post("/api/v1/cve/recheck", headers=admin_headers)
    # A second re-check replaces findings for the port rather than duplicating.
    await client.post("/api/v1/cve/recheck", headers=admin_headers)
    findings = (await client.get("/api/v1/cve/findings", headers=admin_headers)).json()
    assert len(findings) == 1


async def test_recheck_400_when_disabled(client, admin_headers) -> None:
    # No override: the real source is a NullCVESource (CVE enrichment disabled).
    resp = await client.post("/api/v1/cve/recheck", headers=admin_headers)
    assert resp.status_code == 400


async def test_findings_requires_auth(client) -> None:
    assert (await client.get("/api/v1/cve/findings")).status_code == 401


async def test_recheck_requires_write_role(client, admin_headers) -> None:
    await client.post(
        "/api/v1/users",
        json={"email": "ro-cve@test.local", "password": "Secret123!", "role": "auditor"},
        headers=admin_headers,
    )
    login = await client.post(
        "/api/v1/auth/login", data={"username": "ro-cve@test.local", "password": "Secret123!"}
    )
    hdr = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.post("/api/v1/cve/recheck", headers=hdr)).status_code == 403


class _FakeAI:
    name = "fake"

    async def complete(self, system: str, user: str) -> str:
        # References the real finding and a hallucinated id that must be scrubbed.
        return "Address CVE-2024-0001 first (high). Also unrelated CVE-9999-9999."


def _use_fake_ai() -> _FakeAI:
    from portwiz_api.core.ai import get_ai_provider
    from portwiz_api.main import app

    fake = _FakeAI()
    app.dependency_overrides[get_ai_provider] = lambda: fake
    return fake


async def test_summary_grounds_and_scrubs(client, admin_headers) -> None:
    _use_fake_cve_source()
    _use_fake_ai()
    await _ingest_versioned_service(client, admin_headers)
    await client.post("/api/v1/cve/recheck", headers=admin_headers)

    resp = await client.post("/api/v1/cve/summary", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1
    assert "CVE-2024-0001" in body["summary"]  # real finding is kept
    assert "CVE-9999-9999" not in body["summary"]  # hallucination is scrubbed


async def test_summary_400_when_ai_disabled(client, admin_headers) -> None:
    # When AI is explicitly not configured, the brief is refused (not attempted).
    from portwiz_api.core.ai import NullProvider, get_ai_provider
    from portwiz_api.main import app

    app.dependency_overrides[get_ai_provider] = lambda: NullProvider()
    resp = await client.post("/api/v1/cve/summary", headers=admin_headers)
    assert resp.status_code == 400


async def test_summary_empty_when_no_findings(client, admin_headers) -> None:
    _use_fake_ai()  # AI configured, but there are no findings to brief.
    resp = await client.post("/api/v1/cve/summary", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 0
    assert body["summary"] == ""


async def test_summary_requires_auth(client) -> None:
    assert (await client.post("/api/v1/cve/summary")).status_code == 401
