"""API tests for assistant-driven bulk asset create/delete."""

from __future__ import annotations


async def _login(client, email: str, password: str = "Secret123!") -> dict:
    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_bulk_create_and_skip_existing(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/assets/bulk-create",
        json={
            "items": [
                {"ip": "10.1.0.1", "hostname": "a"},
                {"ip": "10.1.0.2", "criticality": "high"},
            ]
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2 and body["succeeded"] == 2 and body["skipped"] == 0

    # Re-running skips the IPs that already exist.
    resp = await client.post(
        "/api/v1/assets/bulk-create",
        json={"items": [{"ip": "10.1.0.1"}, {"ip": "10.1.0.3"}]},
        headers=admin_headers,
    )
    body = resp.json()
    assert body["succeeded"] == 1 and body["skipped"] == 1

    listed = (await client.get("/api/v1/assets", headers=admin_headers)).json()
    ips = {a["ip"] for a in listed}
    assert {"10.1.0.1", "10.1.0.2", "10.1.0.3"} <= ips
    high = next(a for a in listed if a["ip"] == "10.1.0.2")
    assert high["criticality"] == "high"


async def test_bulk_create_reports_invalid_ip(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/assets/bulk-create",
        json={"items": [{"ip": "not-an-ip"}, {"ip": "10.1.0.9"}]},
        headers=admin_headers,
    )
    body = resp.json()
    assert body["succeeded"] == 1 and body["errors"] == 1
    assert "Invalid IP" in body["errors_detail"][0]


async def test_bulk_delete_and_not_found(client, admin_headers) -> None:
    await client.post(
        "/api/v1/assets/bulk-create",
        json={"items": [{"ip": "10.2.0.1"}, {"ip": "10.2.0.2"}]},
        headers=admin_headers,
    )
    resp = await client.post(
        "/api/v1/assets/bulk-delete",
        json={"ips": ["10.2.0.1", "10.2.0.2", "10.2.0.9"]},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["succeeded"] == 2 and body["skipped"] == 1
    assert "10.2.0.9" in body["errors_detail"]

    listed = (await client.get("/api/v1/assets", headers=admin_headers)).json()
    assert not any(a["ip"] in ("10.2.0.1", "10.2.0.2") for a in listed)


async def test_bulk_requires_write_role(client, admin_headers) -> None:
    await client.post(
        "/api/v1/users",
        json={"email": "aud-bulk@test.local", "password": "Secret123!", "role": "auditor"},
        headers=admin_headers,
    )
    aud = await _login(client, "aud-bulk@test.local")
    create = await client.post(
        "/api/v1/assets/bulk-create", json={"items": [{"ip": "10.3.0.1"}]}, headers=aud
    )
    delete = await client.post(
        "/api/v1/assets/bulk-delete", json={"ips": ["10.3.0.1"]}, headers=aud
    )
    assert create.status_code == 403
    assert delete.status_code == 403


async def test_bulk_operations_are_audited(client, admin_headers) -> None:
    await client.post(
        "/api/v1/assets/bulk-create", json={"items": [{"ip": "10.4.0.1"}]}, headers=admin_headers
    )
    await client.post(
        "/api/v1/assets/bulk-delete", json={"ips": ["10.4.0.1"]}, headers=admin_headers
    )
    audit = (await client.get("/api/v1/audit", headers=admin_headers)).json()
    actions = {e["action"] for e in audit["events"]}
    assert "asset.bulk_created" in actions
    assert "asset.bulk_deleted" in actions
