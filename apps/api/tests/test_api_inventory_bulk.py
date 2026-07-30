"""API tests for assistant-driven bulk VLAN and IP range create/delete."""

from __future__ import annotations


async def _login(client, email: str, password: str = "Secret123!") -> dict:
    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# --- VLANs ---


async def test_vlan_bulk_create_and_skip(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/vlans/bulk-create",
        json={"items": [{"name": "DMZ", "vlan_tag": 10}, {"name": "Servers"}]},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2 and body["succeeded"] == 2

    again = await client.post(
        "/api/v1/vlans/bulk-create",
        json={"items": [{"name": "DMZ"}, {"name": "Guest"}]},
        headers=admin_headers,
    )
    b = again.json()
    assert b["succeeded"] == 1 and b["skipped"] == 1


async def test_vlan_bulk_create_reports_bad_tag(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/vlans/bulk-create",
        json={"items": [{"name": "Ok"}, {"name": "Bad", "vlan_tag": 99999}]},
        headers=admin_headers,
    )
    b = resp.json()
    assert b["succeeded"] == 1 and b["errors"] == 1


async def test_vlan_bulk_delete_and_not_found(client, admin_headers) -> None:
    await client.post(
        "/api/v1/vlans/bulk-create",
        json={"items": [{"name": "A"}, {"name": "B"}]},
        headers=admin_headers,
    )
    resp = await client.post(
        "/api/v1/vlans/bulk-delete",
        json={"names": ["A", "B", "Ghost"]},
        headers=admin_headers,
    )
    b = resp.json()
    assert b["succeeded"] == 2 and b["skipped"] == 1
    assert "Ghost" in b["errors_detail"]
    listed = (await client.get("/api/v1/vlans", headers=admin_headers)).json()
    assert not any(v["name"] in ("A", "B") for v in listed)


# --- IP ranges ---


async def test_iprange_bulk_create_with_vlan_and_skip(client, admin_headers) -> None:
    vlan = (
        await client.post("/api/v1/vlans", json={"name": "prod"}, headers=admin_headers)
    ).json()
    resp = await client.post(
        "/api/v1/ip-ranges/bulk-create",
        json={
            "items": [
                {"cidr": "10.0.0.0/24", "vlan_name": "prod"},
                {"cidr": "10.0.1.5/24"},
            ]
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["succeeded"] == 2

    ranges = (await client.get("/api/v1/ip-ranges", headers=admin_headers)).json()
    cidrs = {r["cidr"] for r in ranges}
    assert "10.0.0.0/24" in cidrs and "10.0.1.0/24" in cidrs  # normalised
    prod_range = next(r for r in ranges if r["cidr"] == "10.0.0.0/24")
    assert prod_range["vlan_id"] == vlan["id"]

    again = await client.post(
        "/api/v1/ip-ranges/bulk-create",
        json={"items": [{"cidr": "10.0.0.0/24"}]},
        headers=admin_headers,
    )
    assert again.json()["skipped"] == 1


async def test_iprange_bulk_create_reports_bad(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/ip-ranges/bulk-create",
        json={
            "items": [
                {"cidr": "not-a-cidr"},
                {"cidr": "10.5.0.0/24", "vlan_name": "ghost"},
                {"cidr": "10.6.0.0/24"},
            ]
        },
        headers=admin_headers,
    )
    b = resp.json()
    assert b["succeeded"] == 1 and b["errors"] == 2


async def test_iprange_bulk_delete_and_not_found(client, admin_headers) -> None:
    await client.post(
        "/api/v1/ip-ranges/bulk-create",
        json={"items": [{"cidr": "10.2.0.0/24"}, {"cidr": "10.3.0.0/24"}]},
        headers=admin_headers,
    )
    resp = await client.post(
        "/api/v1/ip-ranges/bulk-delete",
        # first is a host-bit form that normalises to the stored range.
        json={"cidrs": ["10.2.0.9/24", "10.3.0.0/24", "10.9.9.0/24"]},
        headers=admin_headers,
    )
    b = resp.json()
    assert b["succeeded"] == 2 and b["skipped"] == 1
    assert "10.9.9.0/24" in b["errors_detail"]


async def test_bulk_requires_write_role(client, admin_headers) -> None:
    await client.post(
        "/api/v1/users",
        json={"email": "aud-inv@test.local", "password": "Secret123!", "role": "auditor"},
        headers=admin_headers,
    )
    aud = await _login(client, "aud-inv@test.local")
    v = await client.post(
        "/api/v1/vlans/bulk-create", json={"items": [{"name": "X"}]}, headers=aud
    )
    r = await client.post(
        "/api/v1/ip-ranges/bulk-delete", json={"cidrs": ["10.0.0.0/24"]}, headers=aud
    )
    assert v.status_code == 403
    assert r.status_code == 403


async def test_bulk_operations_are_audited(client, admin_headers) -> None:
    await client.post(
        "/api/v1/vlans/bulk-create", json={"items": [{"name": "AudV"}]}, headers=admin_headers
    )
    await client.post(
        "/api/v1/vlans/bulk-delete", json={"names": ["AudV"]}, headers=admin_headers
    )
    await client.post(
        "/api/v1/ip-ranges/bulk-create",
        json={"items": [{"cidr": "10.7.0.0/24"}]},
        headers=admin_headers,
    )
    await client.post(
        "/api/v1/ip-ranges/bulk-delete",
        json={"cidrs": ["10.7.0.0/24"]},
        headers=admin_headers,
    )
    audit = (await client.get("/api/v1/audit", headers=admin_headers)).json()
    actions = {e["action"] for e in audit["events"]}
    assert {
        "vlan.bulk_created",
        "vlan.bulk_deleted",
        "ip_range.bulk_created",
        "ip_range.bulk_deleted",
    } <= actions
