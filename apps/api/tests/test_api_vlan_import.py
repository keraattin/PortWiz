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


async def test_vlan_import_template(client, admin_headers) -> None:
    resp = await client.get("/api/v1/vlans/import-template", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers["content-type"]
    header = resp.text.splitlines()[0]
    for col in ("name", "tag", "description"):
        assert col in header


async def test_vlan_import_requires_write(client, db) -> None:
    headers = await _auditor_headers(client, db)
    resp = await client.post("/api/v1/vlans/import", files=_file(CSV), headers=headers)
    assert resp.status_code == 403
