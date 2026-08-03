"""API integration tests for bulk VLAN import (POST /vlans/import)."""

from __future__ import annotations

CSV = b"name,tag,description\nDMZ,10,edge\nServers,20,\n"


def _file(content: bytes, name: str = "vlans.csv", mime: str = "text/csv"):
    return {"file": (name, content, mime)}


async def _auditor_headers(client, db) -> dict[str, str]:
    from portwiz_api.core.security import hash_password
    from portwiz_api.models.user import User, UserRole

    async with db() as session:
        session.add(
            User(
                email="vaud@test.local",
                hashed_password=hash_password("Secret123!"),
                full_name="Read Only",
                role=UserRole.auditor,
            )
        )
        await session.commit()
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "vaud@test.local", "password": "Secret123!"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_vlan_import_creates_then_updates(client, admin_headers) -> None:
    resp = await client.post("/api/v1/vlans/import", files=_file(CSV), headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert body["created"] == 2
    assert body["errors"] == 0

    # Re-importing the same names updates (default on_conflict=update).
    again = await client.post("/api/v1/vlans/import", files=_file(CSV), headers=admin_headers)
    assert again.json()["updated"] == 2

    # The VLANs are now listed.
    listed = (await client.get("/api/v1/vlans", headers=admin_headers)).json()
    assert {v["name"] for v in listed} >= {"DMZ", "Servers"}


async def test_vlan_import_bad_tag_is_reported(client, admin_headers) -> None:
    bad = b"name,tag\nOK,10\nBadTag,99999\n"
    resp = await client.post("/api/v1/vlans/import", files=_file(bad), headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["errors"] == 1


async def test_vlan_import_attaches_ranges(client, admin_headers) -> None:
    # A VLAN with two ranges (name repeated) plus a VLAN with none, in one file.
    csv = b"name,tag,cidr\nDMZ,10,10.0.0.0/24\nDMZ,,10.0.1.0/24\nServers,20,\n"
    resp = await client.post("/api/v1/vlans/import", files=_file(csv), headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 2  # DMZ + Servers (the second DMZ row updates it)
    assert body["ranges_created"] == 2

    ranges = (await client.get("/api/v1/ip-ranges", headers=admin_headers)).json()
    cidrs = {r["cidr"] for r in ranges}
    assert {"10.0.0.0/24", "10.0.1.0/24"} <= cidrs
    vlans = (await client.get("/api/v1/vlans", headers=admin_headers)).json()
    dmz = next(v for v in vlans if v["name"] == "DMZ")
    assert all(
        r["vlan_id"] == dmz["id"]
        for r in ranges
        if r["cidr"] in ("10.0.0.0/24", "10.0.1.0/24")
    )

    # Re-importing does not duplicate ranges: existing CIDRs are skipped.
    again = (
        await client.post("/api/v1/vlans/import", files=_file(csv), headers=admin_headers)
    ).json()
    assert again["ranges_created"] == 0
    assert again["ranges_skipped"] == 2


async def test_vlan_import_template(client, admin_headers) -> None:
    resp = await client.get("/api/v1/vlans/import-template", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers["content-type"]
    header = resp.text.splitlines()[0]
    for col in ("name", "tag", "description", "cidr"):
        assert col in header


async def test_vlan_import_requires_write(client, db) -> None:
    headers = await _auditor_headers(client, db)
    resp = await client.post("/api/v1/vlans/import", files=_file(CSV), headers=headers)
    assert resp.status_code == 403


# --- interactive import (preview + apply) ---


async def test_vlan_import_preview_flags_and_parses(client, admin_headers) -> None:
    await client.post("/api/v1/vlans", json={"name": "DMZ"}, headers=admin_headers)
    csv = b"name,tag,cidr\nDMZ,10,10.0.0.0/24\nServers,20,\n"
    resp = await client.post(
        "/api/v1/vlans/import/preview", files=_file(csv), headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    by_name = {r["name"]: r for r in resp.json()}
    assert by_name["DMZ"]["exists"] is True
    assert by_name["DMZ"]["cidr"] == "10.0.0.0/24"
    assert by_name["Servers"]["exists"] is False
    assert by_name["Servers"]["vlan_tag"] == 20


async def test_vlan_import_apply_creates_with_ranges(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/vlans/import/apply",
        json={
            "items": [
                {"name": "DMZ", "vlan_tag": 10, "cidr": "10.0.0.0/24"},
                {"name": "DMZ", "cidr": "10.0.1.0/24"},
                {"name": "Servers", "vlan_tag": 20},
            ]
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 2  # DMZ + Servers
    assert body["ranges_created"] == 2
    ranges = (await client.get("/api/v1/ip-ranges", headers=admin_headers)).json()
    vlans = (await client.get("/api/v1/vlans", headers=admin_headers)).json()
    dmz = next(v for v in vlans if v["name"] == "DMZ")
    for r in ranges:
        if r["cidr"] in ("10.0.0.0/24", "10.0.1.0/24"):
            assert r["vlan_id"] == dmz["id"]


async def test_vlan_import_apply_bad_tag_errors_row(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/vlans/import/apply",
        json={"items": [{"name": "Ok"}, {"name": "Bad", "vlan_tag": 99999}]},
        headers=admin_headers,
    )
    body = resp.json()
    assert body["created"] == 1 and body["errors"] == 1


async def test_vlan_import_preview_requires_write(client, db) -> None:
    headers = await _auditor_headers(client, db)
    csv = b"name\nX\n"
    resp = await client.post(
        "/api/v1/vlans/import/preview", files=_file(csv), headers=headers
    )
    assert resp.status_code == 403
