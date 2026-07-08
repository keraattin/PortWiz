"""API integration tests for the evidence package."""

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


async def _login(client, email, password) -> dict:
    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_evidence_package_contents_and_custody(client, admin_headers) -> None:
    token = await _enroll(client, admin_headers, "ev-agent")
    profile = await _profile(client, admin_headers, "ev-profile", "10.0.0.5", "22,80,443")
    pid, ip = profile["id"], "10.0.0.5"

    # Produce a confirmed change: 443 opens, 80 closes.
    await _ingest(client, admin_headers, token, pid, ip, [22, 80])
    await _ingest(client, admin_headers, token, pid, ip, [22, 80])
    await _ingest(client, admin_headers, token, pid, ip, [22, 443])
    await _ingest(client, admin_headers, token, pid, ip, [22, 443])

    resp = await client.get(f"/api/v1/evidence/scan-profiles/{pid}", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    pkg = resp.json()

    assert pkg["profile"]["id"] == pid
    assert pkg["generated_by"] == "admin@test.local"
    assert pkg["chain_verification"]["ok"] is True

    open_ports = {o["port"] for o in pkg["current_open_ports"]}
    assert 22 in open_ports
    assert 443 in open_ports
    assert 80 not in open_ports  # closed, so not in current exposure

    assert len(pkg["scan_runs"]) == 4
    assert len(pkg["changes"]) == 2

    audit_actions = {e["action"] for e in pkg["audit_slice"]}
    assert "scan_profile.created" in audit_actions
    assert any(a.startswith("scan_run.") for a in audit_actions)

    # The export itself was recorded for chain of custody.
    resp = await client.get("/api/v1/audit?action=evidence.exported", headers=admin_headers)
    assert resp.json()["total"] >= 1


async def test_evidence_includes_cve_findings_for_open_ports(
    client, admin_headers, db
) -> None:
    from portwiz_api.models.cve import CVEFinding

    token = await _enroll(client, admin_headers, "cve-ev-agent")
    profile = await _profile(client, admin_headers, "cve-ev", "10.0.0.15", "22,443")
    pid, ip = profile["id"], "10.0.0.15"
    # Two consistent observations confirm 22 and 443 as open exposure.
    await _ingest(client, admin_headers, token, pid, ip, [22, 443])
    await _ingest(client, admin_headers, token, pid, ip, [22, 443])

    async with db() as session:
        session.add_all(
            [
                CVEFinding(
                    ip=ip, port=443, protocol="tcp", service="https", version="1.1",
                    cve_id="CVE-2024-9999", cvss=9.8, severity="critical",
                    summary="Critical flaw", url="https://x", source="nvd",
                ),
                # A finding on a port that is not confirmed-open is excluded.
                CVEFinding(
                    ip=ip, port=8080, protocol="tcp", service="http", version="1",
                    cve_id="CVE-2024-1111", cvss=5.0, severity="medium",
                    summary="Other", url="https://y", source="nvd",
                ),
            ]
        )
        await session.commit()

    resp = await client.get(f"/api/v1/evidence/scan-profiles/{pid}", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    pkg = resp.json()
    cve_ids = {c["cve_id"] for c in pkg["cve_findings"]}
    assert "CVE-2024-9999" in cve_ids  # matched to open port 443
    assert "CVE-2024-1111" not in cve_ids  # port 8080 not part of exposure

    # The export records how many CVEs were bundled (chain of custody).
    audit = await client.get(
        "/api/v1/audit?action=evidence.exported", headers=admin_headers
    )
    assert audit.json()["total"] >= 1


async def test_evidence_rbac(client, admin_headers) -> None:
    profile = await _profile(client, admin_headers, "rbac-ev", "10.0.0.9", "22")
    pid = profile["id"]

    await client.post(
        "/api/v1/users",
        json={"email": "opev@test.local", "password": "Secret123!", "role": "operator"},
        headers=admin_headers,
    )
    operator_headers = await _login(client, "opev@test.local", "Secret123!")
    resp = await client.get(f"/api/v1/evidence/scan-profiles/{pid}", headers=operator_headers)
    assert resp.status_code == 403

    await client.post(
        "/api/v1/users",
        json={"email": "audev@test.local", "password": "Secret123!", "role": "auditor"},
        headers=admin_headers,
    )
    auditor_headers = await _login(client, "audev@test.local", "Secret123!")
    resp = await client.get(f"/api/v1/evidence/scan-profiles/{pid}", headers=auditor_headers)
    assert resp.status_code == 200


async def test_evidence_unknown_profile_404(client, admin_headers) -> None:
    resp = await client.get(
        f"/api/v1/evidence/scan-profiles/{uuid.uuid4()}", headers=admin_headers
    )
    assert resp.status_code == 404


async def test_evidence_pdf_export(client, admin_headers) -> None:
    profile = await _profile(client, admin_headers, "pdf-ev", "10.0.0.8", "22")
    resp = await client.get(
        f"/api/v1/evidence/scan-profiles/{profile['id']}/pdf", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    assert len(resp.content) > 800
    assert "attachment" in resp.headers.get("content-disposition", "")
