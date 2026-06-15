"""API integration tests for bulk asset import (POST /assets/import)."""

from __future__ import annotations

CSV = b"ip,hostname,criticality\n10.0.0.5,web01,high\n10.0.0.6,db01,critical\n"


def _file(content: bytes, name: str = "assets.csv", mime: str = "text/csv"):
    return {"file": (name, content, mime)}


async def _auditor_headers(client, db) -> dict[str, str]:
    from portwiz_api.core.security import hash_password
    from portwiz_api.models.user import User, UserRole

    async with db() as session:
        session.add(
            User(
                email="auditor@test.local",
                hashed_password=hash_password("Secret123!"),
                full_name="Read Only",
                role=UserRole.auditor,
            )
        )
        await session.commit()
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "auditor@test.local", "password": "Secret123!"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_import_requires_auth(client) -> None:
    resp = await client.post("/api/v1/assets/import", files=_file(b"ip\n10.0.0.5\n"))
    assert resp.status_code == 401


async def test_auditor_cannot_import(client, db) -> None:
    headers = await _auditor_headers(client, db)
    resp = await client.post(
        "/api/v1/assets/import", files=_file(b"ip\n10.0.0.5\n"), headers=headers
    )
    assert resp.status_code == 403


async def test_import_creates_assets(client, admin_headers) -> None:
    resp = await client.post("/api/v1/assets/import", files=_file(CSV), headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert body["created"] == 2
    assert body["errors"] == 0

    listed = (await client.get("/api/v1/assets", headers=admin_headers)).json()
    assert {a["ip"] for a in listed} == {"10.0.0.5", "10.0.0.6"}
    assert any(a["criticality"] == "critical" for a in listed)


async def test_reimport_updates_in_place(client, admin_headers) -> None:
    await client.post("/api/v1/assets/import", files=_file(CSV), headers=admin_headers)
    resp = await client.post(
        "/api/v1/assets/import",
        files=_file(b"ip,criticality\n10.0.0.5,low\n"),
        headers=admin_headers,
    )
    body = resp.json()
    assert body["created"] == 0
    assert body["updated"] == 1

    listed = (await client.get("/api/v1/assets", headers=admin_headers)).json()
    asset = next(a for a in listed if a["ip"] == "10.0.0.5")
    assert asset["criticality"] == "low"
    assert len(listed) == 2  # no duplicate created


async def test_skip_mode_leaves_existing(client, admin_headers) -> None:
    await client.post("/api/v1/assets/import", files=_file(CSV), headers=admin_headers)
    resp = await client.post(
        "/api/v1/assets/import?on_conflict=skip",
        files=_file(b"ip,criticality\n10.0.0.5,low\n"),
        headers=admin_headers,
    )
    body = resp.json()
    assert body["skipped"] == 1
    assert body["updated"] == 0

    listed = (await client.get("/api/v1/assets", headers=admin_headers)).json()
    asset = next(a for a in listed if a["ip"] == "10.0.0.5")
    assert asset["criticality"] == "high"  # unchanged


async def test_vlan_and_owner_resolution(client, admin_headers) -> None:
    vlan = (
        await client.post("/api/v1/vlans", json={"name": "prod"}, headers=admin_headers)
    ).json()
    csv = b"ip,vlan,owner\n10.0.0.9,prod,admin@test.local\n"
    resp = await client.post("/api/v1/assets/import", files=_file(csv), headers=admin_headers)
    assert resp.json()["created"] == 1

    asset = (await client.get("/api/v1/assets", headers=admin_headers)).json()[0]
    assert asset["vlan_id"] == vlan["id"]
    assert asset["owner_id"] is not None


async def test_unknown_vlan_is_row_error(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/assets/import",
        files=_file(b"ip,vlan\n10.0.0.5,ghost\n"),
        headers=admin_headers,
    )
    body = resp.json()
    assert body["created"] == 0
    assert body["errors"] == 1
    assert "Unknown VLAN" in body["results"][0]["error"]


async def test_mixed_valid_and_invalid_rows(client, admin_headers) -> None:
    csv = b"ip,criticality\n10.0.0.5,high\nbad-ip,low\n10.0.0.7,nope\n"
    resp = await client.post("/api/v1/assets/import", files=_file(csv), headers=admin_headers)
    body = resp.json()
    assert body["created"] == 1
    assert body["errors"] == 2
    statuses = {r["row"]: r["status"] for r in body["results"]}
    assert statuses == {2: "created", 3: "error", 4: "error"}


async def test_unsupported_filetype_400(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/assets/import", files=_file(b"x", "a.txt", "text/plain"), headers=admin_headers
    )
    assert resp.status_code == 400


async def test_missing_ip_column_400(client, admin_headers) -> None:
    resp = await client.post(
        "/api/v1/assets/import", files=_file(b"hostname\nweb01\n"), headers=admin_headers
    )
    assert resp.status_code == 400


async def test_import_is_audited(client, admin_headers) -> None:
    await client.post("/api/v1/assets/import", files=_file(CSV), headers=admin_headers)
    audit = (await client.get("/api/v1/audit", headers=admin_headers)).json()
    assert any(e["action"] == "asset.imported" for e in audit["events"])
