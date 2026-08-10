"""Teams: CRUD, membership, asset assignment, delete-detach, and admin-only guard."""

from __future__ import annotations

import uuid


async def _make_user(client, admin_headers, email: str, role: str = "auditor") -> str:
    resp = await client.post(
        "/api/v1/users",
        json={"email": email, "password": "Secret123!", "full_name": email, "role": role},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _login(client, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "Secret123!"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_team_crud_and_members(client, admin_headers) -> None:
    t = await client.post(
        "/api/v1/teams", json={"name": "Blue", "description": "SOC"}, headers=admin_headers
    )
    assert t.status_code == 201, t.text
    tid = t.json()["id"]
    assert t.json()["member_count"] == 0

    # Duplicate name is rejected.
    dup = await client.post("/api/v1/teams", json={"name": "Blue"}, headers=admin_headers)
    assert dup.status_code == 409

    uid = await _make_user(client, admin_headers, "m1@test.local")
    add = await client.post(
        f"/api/v1/teams/{tid}/members", json={"user_id": uid}, headers=admin_headers
    )
    assert add.status_code == 201, add.text
    assert add.json()["email"] == "m1@test.local"

    # Idempotent add.
    add2 = await client.post(
        f"/api/v1/teams/{tid}/members", json={"user_id": uid}, headers=admin_headers
    )
    assert add2.status_code == 201

    detail = await client.get(f"/api/v1/teams/{tid}", headers=admin_headers)
    assert detail.json()["member_count"] == 1
    assert len(detail.json()["members"]) == 1

    listed = await client.get("/api/v1/teams", headers=admin_headers)
    assert next(x for x in listed.json() if x["id"] == tid)["member_count"] == 1

    rem = await client.delete(
        f"/api/v1/teams/{tid}/members/{uid}", headers=admin_headers
    )
    assert rem.status_code == 204
    detail2 = await client.get(f"/api/v1/teams/{tid}", headers=admin_headers)
    assert detail2.json()["member_count"] == 0


async def test_asset_owner_team_and_delete_detaches(client, admin_headers) -> None:
    t = await client.post("/api/v1/teams", json={"name": "Green"}, headers=admin_headers)
    tid = t.json()["id"]

    a = await client.post(
        "/api/v1/assets",
        json={"ip": "10.2.2.2", "owner_team_id": tid},
        headers=admin_headers,
    )
    assert a.status_code == 201, a.text
    assert a.json()["owner_team_id"] == tid
    aid = a.json()["id"]

    # An unknown team is rejected.
    bad = await client.post(
        "/api/v1/assets",
        json={"ip": "10.2.2.3", "owner_team_id": str(uuid.uuid4())},
        headers=admin_headers,
    )
    assert bad.status_code == 400

    # Deleting the team detaches the asset (does not delete it).
    d = await client.delete(f"/api/v1/teams/{tid}", headers=admin_headers)
    assert d.status_code == 204
    got = await client.get(f"/api/v1/assets/{aid}", headers=admin_headers)
    assert got.status_code == 200
    assert got.json()["owner_team_id"] is None


async def test_team_management_is_admin_only(client, admin_headers) -> None:
    await _make_user(client, admin_headers, "op@test.local", role="operator")
    op = await _login(client, "op@test.local")

    forbidden = await client.post("/api/v1/teams", json={"name": "NoOp"}, headers=op)
    assert forbidden.status_code == 403

    # Listing stays open (the owner-team picker needs it).
    listed = await client.get("/api/v1/teams", headers=op)
    assert listed.status_code == 200
