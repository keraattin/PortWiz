"""API tests for user management (create, list, update)."""

from __future__ import annotations


async def _make_user(client, admin_headers, email, role="operator") -> dict:
    resp = await client.post(
        "/api/v1/users",
        json={"email": email, "password": "Secret123!", "role": role},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _login(client, email) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login", data={"username": email, "password": "Secret123!"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_update_user_fields(client, admin_headers) -> None:
    user = await _make_user(client, admin_headers, "u1@test.local")
    resp = await client.patch(
        f"/api/v1/users/{user['id']}",
        json={"role": "auditor", "full_name": "Renamed", "is_active": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["role"] == "auditor"
    assert body["full_name"] == "Renamed"
    assert body["is_active"] is False


async def test_admin_cannot_self_demote(client, admin_headers, db) -> None:
    # Find the admin's own id via /users.
    users = (await client.get("/api/v1/users", headers=admin_headers)).json()
    me = next(u for u in users if u["email"] == "admin@test.local")
    resp = await client.patch(
        f"/api/v1/users/{me['id']}", json={"role": "operator"}, headers=admin_headers
    )
    assert resp.status_code == 400


async def test_admin_cannot_self_deactivate(client, admin_headers) -> None:
    users = (await client.get("/api/v1/users", headers=admin_headers)).json()
    me = next(u for u in users if u["email"] == "admin@test.local")
    resp = await client.patch(
        f"/api/v1/users/{me['id']}", json={"is_active": False}, headers=admin_headers
    )
    assert resp.status_code == 400


async def test_update_requires_admin(client, admin_headers) -> None:
    target = await _make_user(client, admin_headers, "target@test.local")
    await _make_user(client, admin_headers, "op@test.local", role="operator")
    op_headers = await _login(client, "op@test.local")
    resp = await client.patch(
        f"/api/v1/users/{target['id']}", json={"role": "auditor"}, headers=op_headers
    )
    assert resp.status_code == 403


async def test_update_missing_user_404(client, admin_headers) -> None:
    import uuid

    resp = await client.patch(
        f"/api/v1/users/{uuid.uuid4()}", json={"role": "auditor"}, headers=admin_headers
    )
    assert resp.status_code == 404


async def test_get_user_by_id(client, admin_headers) -> None:
    import uuid

    user = await _make_user(client, admin_headers, "detail@test.local", role="auditor")
    got = await client.get(f"/api/v1/users/{user['id']}", headers=admin_headers)
    assert got.status_code == 200, got.text
    assert got.json()["email"] == "detail@test.local"
    assert got.json()["role"] == "auditor"

    # Unknown id is a clean 404; the endpoint is admin-only.
    assert (
        await client.get(f"/api/v1/users/{uuid.uuid4()}", headers=admin_headers)
    ).status_code == 404
    await _make_user(client, admin_headers, "op2@test.local", role="operator")
    op = await _login(client, "op2@test.local")
    assert (await client.get(f"/api/v1/users/{user['id']}", headers=op)).status_code == 403
