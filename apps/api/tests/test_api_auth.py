"""API integration tests for authentication."""

from __future__ import annotations


async def test_me_returns_current_admin(client, admin_headers) -> None:
    resp = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "admin@test.local"
    assert body["role"] == "admin"


async def test_me_requires_authentication(client) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_login_rejects_wrong_password(client, admin_headers) -> None:
    # admin_headers fixture already created the admin user.
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "wrong-password"},
    )
    assert resp.status_code == 401


async def test_health_is_public(client) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
