"""API integration tests for the asset inventory (VLAN/Asset CRUD and RBAC)."""

from __future__ import annotations


async def test_vlan_and_asset_crud(client, admin_headers) -> None:
    # Create a VLAN.
    resp = await client.post(
        "/api/v1/vlans",
        json={"name": "DMZ", "vlan_tag": 10, "description": "Perimeter"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    vlan = resp.json()

    # Create an asset in that VLAN with a compliance classification.
    resp = await client.post(
        "/api/v1/assets",
        json={
            "ip": "10.0.0.5",
            "hostname": "web01",
            "vlan_id": vlan["id"],
            "criticality": "high",
            "data_sensitivity": "cde",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    asset = resp.json()
    assert asset["criticality"] == "high"
    assert asset["data_sensitivity"] == "cde"

    # List, filtered by VLAN.
    resp = await client.get(f"/api/v1/assets?vlan_id={vlan['id']}", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Patch criticality.
    resp = await client.patch(
        f"/api/v1/assets/{asset['id']}",
        json={"criticality": "critical"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["criticality"] == "critical"

    # Delete.
    resp = await client.delete(f"/api/v1/assets/{asset['id']}", headers=admin_headers)
    assert resp.status_code == 204


async def test_asset_rejects_invalid_ip(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/assets", json={"ip": "not-an-ip"}, headers=admin_headers
    )
    assert resp.status_code == 422


async def test_asset_rejects_unknown_vlan(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/assets",
        json={"ip": "10.0.0.9", "vlan_id": "00000000-0000-0000-0000-000000000000"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


async def test_auditor_cannot_write_but_can_read(client, admin_headers) -> None:
    # Admin provisions an auditor.
    resp = await client.post(
        "/api/v1/users",
        json={"email": "auditor@test.local", "password": "Secret123!", "role": "auditor"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text

    # Auditor logs in.
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "auditor@test.local", "password": "Secret123!"},
    )
    auditor_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # Auditor cannot create an asset.
    resp = await client.post(
        "/api/v1/assets", json={"ip": "10.0.0.20"}, headers=auditor_headers
    )
    assert resp.status_code == 403

    # But can read.
    resp = await client.get("/api/v1/assets", headers=auditor_headers)
    assert resp.status_code == 200
