"""API integration tests for the audit log and chain verification."""

from __future__ import annotations


async def _login(client, email: str, password: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_audit_list_and_verify(client, admin_headers) -> None:
    # Generate an auditable action.
    resp = await client.post("/api/v1/assets", json={"ip": "10.0.0.5"}, headers=admin_headers)
    assert resp.status_code == 201

    resp = await client.get("/api/v1/audit", headers=admin_headers)
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] >= 2  # login + asset.created
    actions = {e["action"] for e in page["events"]}
    assert "asset.created" in actions
    assert all(e["hash"] and e["prev_hash"] for e in page["events"])

    resp = await client.get("/api/v1/audit/verify", headers=admin_headers)
    assert resp.status_code == 200
    verification = resp.json()
    assert verification["ok"] is True
    assert verification["broken_seq"] is None
    assert verification["total"] >= 2


async def test_audit_filter_by_action(client, admin_headers) -> None:
    await client.post("/api/v1/assets", json={"ip": "10.0.0.6"}, headers=admin_headers)
    resp = await client.get("/api/v1/audit?action=asset.created", headers=admin_headers)
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] >= 1
    assert all(e["action"] == "asset.created" for e in page["events"])


async def test_audit_requires_privileged_role(client, admin_headers) -> None:
    await client.post(
        "/api/v1/users",
        json={"email": "op@test.local", "password": "Secret123!", "role": "operator"},
        headers=admin_headers,
    )
    operator_headers = await _login(client, "op@test.local", "Secret123!")
    resp = await client.get("/api/v1/audit", headers=operator_headers)
    assert resp.status_code == 403

    await client.post(
        "/api/v1/users",
        json={"email": "aud@test.local", "password": "Secret123!", "role": "auditor"},
        headers=admin_headers,
    )
    auditor_headers = await _login(client, "aud@test.local", "Secret123!")
    resp = await client.get("/api/v1/audit", headers=auditor_headers)
    assert resp.status_code == 200
